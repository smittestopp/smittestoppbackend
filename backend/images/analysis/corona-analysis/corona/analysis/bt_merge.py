import numpy as np
from corona import logger


def silent_assert(cond, description, args):
    '''Assert'''
    if not cond:
        logger.error('\033[1;37;31m%s\033[0m' % '>>>>>>> Failing Assert in', description, args)
    return cond


pandas_fields = ('uuid',
                 'paireddeviceid',
                 'encounterstarttime',
                 'duration',
                 'very_close_duration',
                 'close_duration',
                 'relatively_close_duration')

# Accessors Row in the local pandas bluetooth dataframe
e_uuid, e_pd, e_start, e_dur, e_vcd, e_cd, e_rcd = (
    lambda row, i=i: row[i] for i in range(len(pandas_fields))
)


e_end = lambda row: e_start(row) + e_dur(row)


def e_is_identical(A, B):
    '''Same time stamp event'''
    return e_start(A) == e_start(B) and e_dur(A) == e_dur(B)


def e_no_overlap(A, B):
    '''Check for <--(A)-->    <--(B)--> or <-(B)-> <--(A)-->'''
    return (e_end(A) < e_start(B)) or (e_end(B) < e_start(A))


def e_contains(A, B, tol=1):
    '''Event A encloses B
              <--------(A)---------->
                  <----(B)---->
    '''
    return (e_start(A) <= e_start(B)) and (e_end(A) >= e_end(B))


def right_overlaps(A, B, tol=1):
    '''B starts before A is done
              <--------(A)---------->
                            <----(B)---->
    '''
    return e_start(B) <= e_end(A) <= e_end(B)


def isolate_events(events, debug=False):
    '''A list of pandas row(events) is isolated to produce new events'''
    # NOTE: after the isolate the events should 'isolated'
    if len(events) == 1:
        return [events[0]]

    # This is the work horse
    A, B, rest = events[0], events[1], events[2:]

    debug and logger.info('<%g---(A)--%g>' % (e_start(A), e_end(A)))
    debug and logger.info('<%g---(B)--%g>' % (e_start(B), e_end(B)))

    if e_is_identical(A, B):
        debug and logger.info('Identity\n')
        new_event = [e_uuid(A),  # This guys are determined by the enclosing
                     e_pd(A),    # event
                     e_start(A),
                     e_dur(A),
                     # Focus on worst case scenario so we pick longest *_duration
                     max(e_vcd(A), e_vcd(B)),
                     max(e_cd(A), e_cd(B)),
                     max(e_rcd(A), e_rcd(B))]
        return isolate_events([new_event] + rest)

    if e_no_overlap(A, B):
        debug and logger.info('!Overlap\n')
        return [A] + isolate_events([B] + rest)

    if e_contains(A, B):
        debug and logger.info('Contains\n')
        new_event = [e_uuid(A),  # This guys are determined by the enclosing
                     e_pd(A),    # event
                     e_start(A),
                     e_dur(A),
                     # Focus on worst case scenario so we pick longest *_duration
                     max(e_vcd(A), e_vcd(B)),
                     max(e_cd(A), e_cd(B)),
                     max(e_rcd(A), e_rcd(B))]
        return isolate_events([new_event] + rest)

    # Join the events
    if right_overlaps(A, B):
        debug and logger.info('Overlap\n')
        # The new event has start of A and end of B
        start_A, start_B = map(e_start, (A, B))
        end_A, end_B = map(e_end, (A, B))
        dur_A, dur_B = map(e_dur, (A, B))
        # SA<------->EA
        #      SB<--------->EB
        overlap = end_A - start_B

        foo = lambda qA, qB: (qA/dur_A*(dur_A - overlap)+
                              max(qA/dur_A, qB/dur_B)*overlap+
                              qB/dur_B*(dur_B - overlap))

        event = [e_uuid(A), e_pd(A),
                 start_A, end_B - start_A,
                 foo(e_vcd(A), e_vcd(B)),
                 foo(e_cd(A), e_cd(B)),
                 foo(e_rcd(A), e_rcd(B))]

        return isolate_events([event] + rest)
    raise ValueError('This should not happen', A, B)


def are_consecutive(events):
    '''No event starts before its predecessor is finished'''
    # logger.info(f'{len(events)}')
    if len(events) == 1:
        return True

    if len(events) == 2:
        e0, e1 = events
        silent_assert(e_start(e0) < e_start(e1), 'are_consecutive', [e0, e1])

        # logger.info('<%g---(A)--%g>' % (e_start(e0), e_end(e0)))
        # logger.info('<%g---(B)--%g>' % (e_start(e1), e_end(e1)))
        # logger.info(f'Compare {e_end(e0) < e_start(e1)}')

        return e_end(e0) < e_start(e1)

    return all(are_consecutive(p) for p in zip(events[:-1], events[1:]))


def glue_events(events, distance):
    '''Merge isolated events if their distance (in time) is small'''
    if len(events) == 1:
        return events

    A, B, rest = events[0], events[1], events[2:]

    #logger.info('<%g---(A)--%g>' % (e_start(A), e_end(A)))
    #logger.info('<%g---(B)--%g>' % (e_start(B), e_end(B)))
    #logger.info(f'{e_start(B)-e_end(A)} {distance} {e_start(B) - e_end(A) > distance}')

    silent_assert(e_start(A) < e_start(B), 'glue_events', [A, B])
    # <----->  <----->
    # C0             C1
    silent_assert(e_end(A) < e_start(B), 'glue_events', [A, B])
    # Glue based on distance
    if e_start(B) - e_end(A) < distance:
        new_event = [e_uuid(A), e_pd(A),
                     e_start(A),
                     e_dur(A) + e_dur(B),
                     e_vcd(A) + e_vcd(B),  # FIXME: okay to just add them?
                     e_cd(A) + e_cd(B)]

        return glue_events([new_event] + rest, distance)
    # A is on its own and we try the rest
    return [A] + glue_events([B] + rest, distance)


def is_sane_frame(frame):
    '''Verify the assumptions on increasing time 'encounterstarttime' '''
    t = np.array(frame['encounterstarttime'])
    return all(t0 < t1 for t0, t1 in zip(t[:-1], t[1:]))


def BTMerge(events, distance, debug=False):
    '''Pandas frame to List of (isolated) events of BT record'''
    # Check that the frame is sorted in time
    assert not debug or silent_assert(is_sane_frame(events), 'frame sanity')

    # NOTE: useful for debugging - reset time so that first event starts at 0
    # events['encounterstarttime'] -= events['encounterstarttime'].min()

    # Break to list
    # This is a full frame. What only need are the time infos
    events = list(zip(*[events[field] for field in pandas_fields]))

    # We rely on int comparison so better assert types
    col_type = list(map(type, events[0]))
    assert e_start(col_type) is int and e_dur(col_type) is int, (e_start(col_type), e_dur(col_type), col_type)

    # We produce isolated events
    isolated = isolate_events(events)
    assert not debug or silent_assert(are_consecutive(isolated), 'isolated')
    # We glue them by staince
    glued = glue_events(isolated, distance)
    assert not debug or silent_assert(are_consecutive(isolated), 'glued')

    for event in glued:
        yield event
