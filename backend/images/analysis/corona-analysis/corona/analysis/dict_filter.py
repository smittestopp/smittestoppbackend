from collections import defaultdict
from types import FunctionType
import itertools

from corona import logger


def nested_dict():
    '''Infinite dict https://stackoverflow.com/a/4178334'''
    return defaultdict(nested_dict)

# NOTE: we get the value out of a nested dictionary using tuples. It is
# convenient not to have to specify the keys individualy. Instead, we
# provide some specs for the keys to be computed for given dict
def nested_set(dictionary, key, value, debug=False):
    '''Set value of nested dictionary'''
    assert isinstance(key, tuple)

    debug and logger.info(f'Set {key} {list(dictionary.keys())}')
    key0, *keys = key
    if not keys:
        dictionary[key0] = value
        return dictionary
    return nested_set(dictionary[key0], tuple(keys), value, debug)


def nested_get(dictionary, key, debug=False):
    '''Get value from nested dictionary'''
    assert isinstance(key, tuple)

    debug and logger.info(f'Get {key} {list(dictionary.keys())}')
    key0, *keys = key
    if not keys:
        return dictionary[key0]
    return nested_get(dictionary[key0], tuple(keys), debug)


class Not(tuple):
    '''Not(('foo', 'bar')) is used to exclude keys 'foo', 'bar' '''
    def __new__(self, args):
        return tuple.__new__(self, args)


class All(tuple):
    '''All() selects all keys of the dictionary'''
    def __new__(self):
        return tuple.__new__(self, ())


# NOTE: Rule is a tuple of tuples. It can be longer than then dictionary
# depth - then the irrelevant part is ignored
class Rule(tuple):
    '''Rule is a tuple of tuples'''
    def __new__(self, args):
        assert isinstance(args, tuple)
        # Insist of value type
        assert len(args) == 1 or all(isinstance(a, tuple) for a in args), list(map(type, args))

        return tuple.__new__(self, args)


def expand_rule(rule, dictionary):
    '''Rule -> list of queries'''
    # Non dictionaries get invalid query
    if not hasattr(dictionary, 'keys'): return []

    # Case (single_rule, ). So how do we exapand now
    if len(rule) == 1:
        rule, = rule
        valid_keys = set(dictionary.keys())
        # Check explicit keys
        if not isinstance(rule, (Not, All)):
            rule = set(rule)
            # NOTE: we are graceful here and ignore wrong keys
            explicit_keys = rule & valid_keys
            # The others are perhaps lambdas
            for predicate in filter(lambda rule: isinstance(rule, FunctionType), rule):
                # Add those that match
                explicit_keys.update(filter(predicate, valid_keys))

            return [(k, ) for k in explicit_keys]
        # Implicit ones
        else:
            # All expands to every key
            if isinstance(rule, All):
                return [(k, ) for k in valid_keys]
            # Not is a subset
            assert isinstance(rule, Not)
            return [(k, ) for k in valid_keys - set(rule)]

    # Nested, break to head and tail
    rule0, rule = rule[:1], rule[1:]
    keys0 = expand_rule(rule0, dictionary)
    # Combine keys due to expanding first rule on top level dictionary
    # with those obtained by expanding the rest of rule on the subdictionaries
    # of the key
    return [key0 + key
            for key0 in keys0
            if hasattr(nested_get(dictionary, key0), 'keys')
            for key in expand_rule(rule, nested_get(dictionary, key0))
            ]


def nested_filter(rules, dictionary, debug=False):
    '''A new dictionary is filled using keys'''
    assert all(isinstance(rule, Rule) for rule in rules)

    filtered = nested_dict()
    # Rules should result in valid multikeys
    for rule in rules:
        # We expand the rule to have the form a list of tuple
        for key in expand_rule(rule, dictionary):
            value = nested_get(dictionary, key, debug)
            nested_set(filtered, key, value, debug)

    return filtered


def nested_depth(dictionary):
    '''Count the nestings. Maximum'''
    if not isinstance(dictionary, (defaultdict, dict)) or not dictionary:
        return 0
    # This depth + maximum depth of the (possible) subdicts
    return 1 + max(map(nested_depth, dictionary.values()))


def nested_keys(dictionary):
    '''Keys of all non dict values in the nested dictionary'''
    for key in dictionary:
        value = dictionary[key]
        if isinstance(value, (defaultdict, dict)) and value:
            for rest in nested_keys(value):
                yield (key, ) + rest
        else:
            yield (key, )


# --------------------------------------------------------------------

is_bt_duration = lambda key: key.startswith('bt_') and key.endswith('_duration')

# These are rules for FHI filtering
FHI_RULES = [
    # Cummulative
    Rule((All(), ('cumulative', ), ('all_contacts', ), ('points_of_interest', 'number_of_contacts', 'risk_cat', 'bar_plot', 'days_in_contact'))),
    Rule((All(), ('cumulative', ), ('bt_contacts', 'gps_contacts'), ('cumulative_duration', 'cumulative_risk_score', 'days_in_contact'))),
    Rule((All(), ('cumulative', ), ('bt_contacts', ), (is_bt_duration, ))),
    Rule((All(), ('cumulative', ), ('gps_contacts', ), ('hist_plot', ))),
    # Individual
    Rule((All(), ('daily', ), All(), ('all_contacts', ), ('summary_plot', 'points_of_interest' ))),
    Rule((All(), ('daily', ), All(), ('bt_contacts', 'gps_contacts'), ('cumulative_duration','number_of_contacts'))),
    # Zoom in on blue tooth
    Rule((All(), ('daily', ), All(), ('bt_contacts', ),  (is_bt_duration, )))
]


def fhi_filter_dict(data, rules=FHI_RULES):
    '''Use FHI rules in filtering'''
    return nested_filter(rules, data)
