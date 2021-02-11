#!/usr/bin/env python

# from kubernetes example documentation
# Based on http://peter-hoffmann.com/2012/python-simple-queue-redis-queue.html
# and the suggestion in the redis documentation for RPOPLPUSH, at
# http://redis.io/commands/rpoplpush, which suggests how to implement a work-queue.


import uuid
import hashlib
import json
from threading import Thread, Lock

import redis
from redlock import Redlock

from tornado.log import app_log


class RedisDistributedLock:
    # nemivir, Apache license 2.0
    def __init__(self, redis_lock: Redlock, lock_key: str, ttl: int = 30):
        """
        A context based redis distributed lock
        :param redis_lock: Redlock object
        :param lock_key: the resource key to lock
        :param ttl: timout after ttl seconds
        """
        self._rlk = redis_lock
        self._key = lock_key
        self._ttl = ttl
        self._lock = None

    def __enter__(self):
        self._lock = self._rlk.lock(self._key, self._ttl)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._rlk.unlock(self._lock)


class Lease:
    """Object encapsulating a lease held on a task

    Lease is renewed in a background thread
    to ensure that the lease is relinquished promptly
    if the worker dies.
    Renewal interval is half of the lease interval.

    This improves reclaim behavior when tasks are long.
    """

    def __init__(self, db, key, value, lease_secs=60):
        self._db = db
        self.key = key
        self.value = value
        self.lease_secs = lease_secs
        self.renewal_interval = lease_secs // 2
        self._held = False

    def _renew(self):
        """Renew our lease"""
        app_log.info(f"Holding lease on {self.key}")
        self._db.setex(self.key, self.lease_secs, self.value)

    def _keep_renewed(self):
        """Run in a background thread to keep the lease renewed"""
        while self._held:
            if self._thread_signal.acquire(timeout=self.renewal_interval):
                self._thread_signal.release()
                return
            else:
                self._renew()

    def acquire(self):
        """Acquire and hold lease on our key

        Lease is kept renewed in a background thread
        until release() is called
        """
        self._held = True
        self._thread_signal = Lock()
        self._thread_signal.acquire()

        self._renew()
        self._renewal_thread = Thread(target=self._keep_renewed, daemon=True)
        self._renewal_thread.start()

    def release(self):
        """Release the lease on our key

        Halts the renewal thread and deletes the lease key
        """
        app_log.debug(f"Releasing lease on {self.key}")
        # halt renewal thread
        self._held = False
        self._thread_signal.release()
        self._renewal_thread.join()
        # actually release the lease
        self._db.delete(self.key)
        app_log.info(f"Released lease on {self.key}")


class RedisWQ:
    """Simple Finite Work Queue with Redis Backend

    This work queue is finite: as long as no more work is added
    after workers start, the workers can detect when the queue
    is completely empty.

    The items in the work queue are assumed to have unique values.

    This object is not intended to be used by multiple threads
    concurrently.
    """

    def __init__(self, name, **redis_kwargs):
        """The default connection parameters are: host='localhost', port=6379, db=0

       The work queue is identified by "name".  The library may create other
       keys with "name" as a prefix.
       """
        self._db = redis.StrictRedis(**redis_kwargs)
        self.lock_manager = Redlock([redis_kwargs])
        # The session ID will uniquely identify this "worker".
        self._session = str(uuid.uuid4())
        # Work queue is implemented as two queues: main, and processing.
        # Work is initially in main, and moved to processing when a client picks it up.
        self._main_q_key = name
        self._processing_q_key = name + ":processing"
        self._lease_key_prefix = name + ":leased_by_session:"
        self._gc_lock_key = name + ":gc-lock"
        self._gc_lock = RedisDistributedLock(self.lock_manager, self._gc_lock_key)
        self._leases = {}

    def sessionID(self):
        """Return the ID for this session."""
        return self._session

    def _main_qsize(self):
        """Return the size of the main queue."""
        return self._db.llen(self._main_q_key)

    def _processing_qsize(self):
        """Return the size of the main queue."""
        return self._db.llen(self._processing_q_key)

    def empty(self):
        """Return True if the queue is empty, including work being done, False otherwise.

        False does not necessarily mean that there is work available to work on right now,
        """
        return self._main_qsize() == 0 and self._processing_qsize() == 0

    def gc(self):
        """Return expired leases to the work queue
        """
        # Processing list should not be _too_ long since it is approximately as long
        # as the number of active and recently active workers.
        if self._processing_qsize() == 0:
            app_log.debug("")
            return
        with self._gc_lock:
            qsize = self._processing_qsize()
            if qsize == 0:
                return

            app_log.info(f"Running garbage collection on {qsize} outstanding jobs")

            for index, item in enumerate(
                self._db.lrange(self._processing_q_key, 0, -1)
            ):
                # If the lease key is not present for an item (it expired or was
                # never created because the client crashed before creating it)
                # then move the item back to the main queue so others can work on it.
                if not self._lease_exists(item):
                    app_log.warning(
                        f"item {self._itemkey(item)}... lease expired, returning to main queue"
                    )
                    # no lease exists, move back to main
                    self._db.lpush(self._main_q_key, item)
                    self._db.lrem(self._processing_q_key, 1, item)

    def _itemkey(self, item):
        """Returns a string that uniquely identifies an item (bytes)."""
        try:
            task = json.loads(item.decode("utf8"))
            return f"{task['request_id']}:{task['device_id']}"
        except (ValueError, KeyError) as e:
            app_log.error(f"Unexpected JSON task format: {item}: {e}")
            return hashlib.sha224(item).hexdigest()

    def _lease_exists(self, item):
        """True if a lease on 'item' exists."""
        return self._db.exists(self._lease_key_prefix + self._itemkey(item))

    def lease(self, lease_secs=900, block=True, timeout=None):
        """Begin working on an item the work queue.

        Lease the item for lease_secs.  After that time, other
        workers may consider this client to have crashed or stalled
        and pick up the item instead.

        If optional args block is true and timeout is None (the default), block
        if necessary until an item is available."""
        if block:
            item = self._db.brpoplpush(
                self._main_q_key, self._processing_q_key, timeout=timeout
            )
        else:
            item = self._db.rpoplpush(self._main_q_key, self._processing_q_key)
        if item:
            # Record that we (this session id) are working on a key.  Expire that
            # note after the lease timeout.
            # Note: if we crash at this line of the program, then GC will see no lease
            # for this item a later return it to the main queue.
            itemkey = self._itemkey(item)
            app_log.info(f"Acquiring lease for {itemkey}")
            lease = self._leases[item] = Lease(
                db=self._db,
                key=self._lease_key_prefix + itemkey,
                value=self._session,
                lease_secs=lease_secs,
            )
            lease.acquire()

        return item

    def release(self, item):
        """Release the lease on an item

        allows others to claim it
        """
        app_log.debug(f"Clearing processing lease")
        lease = self._leases.pop(item)
        lease.release()

    def complete(self, item, result_key, expiry, result):
        """Complete working on the item with 'value'.

        If the lease expired, the item may not have completed, and some
        other worker may have picked it up.  There is no indication
        of what happened.
        """
        # TODO: check for lease expiry to avoid duplicate results?
        # store the result in the result set
        app_log.info(f"Storing result in {result_key} for {self._itemkey(item)}")
        self._db.setex(result_key, expiry, result)

        # indicate that we are done processing
        app_log.debug(f"Removing item from processing queue")
        self._db.lrem(self._processing_q_key, 0, item)
        # If we crash here, then the GC code will try to move the value, but it will
        # not be here, which is fine.  So this does not need to be a transaction.
        self.release(item)
        app_log.info("Completed processing")


# TODO: add functions to clean up all keys associated with "name" when
# processing is complete.

# TODO: add a function to add an item to the queue.  Atomically
# check if the queue is empty and if so fail to add the item
# since other workers might think work is done and be in the process
# of exiting.
