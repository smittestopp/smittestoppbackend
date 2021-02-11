import math
import time
import datetime
import numpy as np
import pandas as pd

from numba import jit
from collections import defaultdict
from functools import wraps
from corona import logger
from contextlib import contextmanager

@jit(nopython=True, cache=True)
def haversine_distance(lat1, lon1, lat2, lon2):
    """distance between two people at given time-step """
    R = 6371 # Earth radius in kilometers

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi       = math.radians(lat2 - lat1)
    dlambda    = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + \
        math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return (R * c) * 1000

def default_to_regular(d):
    """ Converts a (nested) defaultdict to a regular dictionary """
    if isinstance(d, defaultdict):
        d = {k: default_to_regular(v) for k, v in d.items()}
    return d


def convert_seconds(seconds):
    """ Converting seconds to (h,m,s) in a pretty string """
    days = seconds // 86400
    seconds %= 86400
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    if days == 0:
        return "%d:%02d:%02d" % (hours, minutes, seconds)
    return "%d days and %d:%02d:%02d" % (days, hours, minutes, seconds)

def numpy_to_pd_frame(data, timecol):
    """
    Converts numpy array of shape (n_timestamps, 4) to pandas frame. Columns
    will be named ['time', 'latitude', 'longitude', 'accuracy'].
    """
    if timecol:
        if len(data.shape) < 2 or data.shape[1] != 4:
            raise RuntimeError("numpy_to_pd_frame: Requires numpy array of dimensions (n_timestamps, 4)")
        pd_frame = pd.DataFrame(data=data, columns=["time", "latitude", 'longitude', 'accuracy'])
    else:
        if len(data.shape) < 2 or data.shape[1] != 3:
            raise RuntimeError("numpy_to_pd_frame: Requires numpy array of dimensions (n_timestamps, 4)")
        pd_frame = pd.DataFrame(data=data, columns=["latitude", 'longitude', 'accuracy'])
    return pd_frame


def union_of_time_stamps(ts_1, ts_2, return_as = 'np'):
    """
    Functions takes two time vectors (numpy array or pandas series)
    with unix time stamps and computes their union.

    Returns as np.array or pandas series depending on return_as option.
    """
    if isinstance(ts_1, pd.Series):
        ts_1 = ts_1.values
    if isinstance(ts_2, pd.Series):
        ts_2 = ts_2.values
    time_stamps = np.union1d(ts_1, ts_2) # Sorted unique union of both time stamp arrays
    if return_as == 'pd':
        return pd.Series({'time' : union1d})
    elif return_as == 'np':
        return time_stamps
    else:
        raise RuntimeError("corona_analysis.utils.py - union_of_time_stamps : return_as = {0} not implemented".format(return_as))

def duration_of_contact(time_stamps, indices_in_contact, threshold_duration = 120):
    """
    Takes an ordered list of unix time stamps and an ordered list of indices of contact.
    Outputs the duration of the contact. Contact is ASSUMED to be consecutive, i.e. gaps
    in indices will not result in splitting duration.
    The duration of an interval [t_i , ... , t_j] is now taken to be t_{j+1/2} - t_{i-1/2}
    t_{j+1/2} = min( (t_{j} + threshold_duration) , (t_{j} + t_{j+1})/2 )
    If (j+1) == len(time_stamps) then t_{j+1} = t_{j}
    We define t_{i-1/2} similarly
    """
    if len(time_stamps) == 0 or len(indices_in_contact) == 0:
        return 0.0

    if min(indices_in_contact) > 0 and max(indices_in_contact) < len(time_stamps) - 1:
        max_timestamp = ( time_stamps[max(indices_in_contact)] + time_stamps[max(indices_in_contact) + 1] ) / 2
        max_timestamp = min(max_timestamp, time_stamps[max(indices_in_contact)] + threshold_duration)
        min_timestamp = ( time_stamps[min(indices_in_contact)] + time_stamps[min(indices_in_contact) - 1] ) / 2
        min_timestamp = max(min_timestamp, time_stamps[min(indices_in_contact)] - threshold_duration)
        return max_timestamp - min_timestamp

    if min(indices_in_contact) == 0 and max(indices_in_contact) < len(time_stamps) - 1:
        max_timestamp = ( time_stamps[max(indices_in_contact)] + time_stamps[max(indices_in_contact) + 1] ) / 2
        max_timestamp = min(max_timestamp, time_stamps[max(indices_in_contact)] +threshold_duration)
        min_timestamp = time_stamps[0]
        return max_timestamp - min_timestamp

    if min(indices_in_contact) > 0 and max(indices_in_contact) == len(time_stamps) - 1:
        max_timestamp = time_stamps[-1]
        min_timestamp = ( time_stamps[min(indices_in_contact)] + time_stamps[min(indices_in_contact) - 1] ) / 2
        min_timestamp = max(min_timestamp, time_stamps[min(indices_in_contact)] - threshold_duration)
        return max_timestamp - min_timestamp

    elif min(indices_in_contact) == 0 and max(indices_in_contact) == len(time_stamps) - 1:
        return time_stamps[-1] - time_stamps[0]


def sparsify_mask(x, threshold, distance=lambda x, y: x-y):
    '''
    Return mask for indices of x such that every 2 consequtive elements of x[idx]
    are further than threshold.
    '''
    if isinstance(threshold, datetime.timedelta):
        assert threshold.total_seconds() > 0
    else:
        threshold > 0

    n = len(x)
    if n < 2:
        return [True]*n

    i0, i1 = 0, 1

    mask = [True]
    while i1 < n:
        delta = distance(x[i1], x[i0])
        if isinstance(delta, datetime.timedelta):
            assert not (delta.total_seconds() < 0), delta.total_seconds()
        else:
            assert not (delta < 0), delta

        if delta < threshold:
            i1 += 1
            mask.append(False)
        else:
            i0, i1 = i1, i1 + 1
            mask.append(True)
    return mask


def get_or(obj, method, default):
    '''Try calling no args method of obj returning default if not found'''
    if hasattr(obj, method):
        return getattr(obj, method)()
    return default

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

def retry(ExceptionCheck, tries=8, delay=3, backoff=2):
    def deco_retry(f):
        @wraps(f)
        def f_retry(*args, **kwargs):
            remaining_trues = tries
            current_delay = delay
            while remaining_trues > 0:
                try:
                    return f(*args, **kwargs)
                except ExceptionCheck:
                    logger.warning("Retrying in %d seconds..." % current_delay)
                    time.sleep(current_delay)
                    remaining_trues -= 1
                    current_delay *= backoff
            return f(*args, **kwargs)
        return f_retry
    return deco_retry


@contextmanager
def timer(message):
    """Context manager for reporting time measurements"""
    tic = time.perf_counter()
    extra = ""
    try:
        yield
    except Exception:
        extra = " (failed)"
        raise
    finally:
        toc = time.perf_counter()
        ms = int(1000 * (toc - tic))
        logger.info(f"{message}{extra}: {ms}ms")
