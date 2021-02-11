import pytest
from itertools import chain
import corona.analysis.dict_filter as df
import re


dictionary = {'m': 1, 'i': 2, 'r': 3, 'o': 4}

# Basic logic
def test_simple_single(dictionary=dictionary):
    rule = df.Rule((('m', ), ))
    queries = set(df.expand_rule(rule, dictionary))
    print(queries)
    queries0 = set([('m', )])
    assert queries == queries0, (queries, queries0)


def test_simple_all(dictionary=dictionary):    
    rule = df.Rule((df.All(), ))
    queries = set(df.expand_rule(rule, dictionary))
    print(queries)
    queries0 = set([('m', ), ('i', ), ('r', ), ('o', )])
    assert queries == queries0, queries


nested_dictionary = {'m': {'MM': {'iii': {'kkkk': 4, 'uuuu': 5},
                                  'rrr': 3,
                                  'ooo': 4},
                           'RR': {'iii': {'kkkk': 4},
                                  'rrr': 3,
                                  'ooo': 4},
                           'II': {'rrr': 2,
                                  'ooo': {'ssss': 2,
                                          'llll': 3}}},
                     'i': 2, 'r': 3, 'o': 4}

def test_depth(dictionary=nested_dictionary):
    assert df.nested_depth(dictionary) == 4

    
def test_keys(dictionary=nested_dictionary):
    keys = set(df.nested_keys(dictionary))
    keys0 = set([('i', ), ('r', ), ('o', ),
                 ('m', 'II', 'rrr'), ('m', 'RR', 'rrr'), ('m', 'RR', 'ooo'), ('m', 'MM', 'rrr'), ('m', 'MM', 'ooo'),
                 ('m', 'MM', 'iii', 'kkkk'), ('m', 'MM', 'iii', 'uuuu'), ('m', 'RR', 'iii', 'kkkk'), ('m', 'II', 'ooo', 'ssss'), ('m', 'II', 'ooo', 'llll')])
    assert keys == keys0
    
    
def test_nested_1(dictionary=nested_dictionary):
    rule = df.Rule((('m', ), ('MM', 'II'), df.All(), df.All()))
    queries = set(df.expand_rule(rule, dictionary))
    queries0 = set([('m', 'MM', 'iii', 'kkkk'),
                    ('m', 'MM', 'iii', 'uuuu'),
                    ('m', 'II', 'ooo', 'ssss'),
                    ('m', 'II', 'ooo', 'llll')])
    assert queries == queries0, queries

def test_nested_2(dictionary=nested_dictionary):
    rule = df.Rule((('m', ), df.Not(('M', )), df.Not(('rr', )), df.All()))
    queries = set(df.expand_rule(rule, dictionary))
    queries0 = set([('m', 'MM', 'iii', 'kkkk'),
                    ('m', 'MM', 'iii', 'uuuu'),
                    ('m', 'RR', 'iii', 'kkkk'),
                    ('m', 'II', 'ooo', 'ssss'),
                    ('m', 'II', 'ooo', 'llll')])
    assert queries == queries0, queries

    
def test_nested_3(dictionary=nested_dictionary):
    rule = df.Rule((('m', ), df.Not(('MM', )), df.Not(('rrr', )), df.All()))
    queries = set(df.expand_rule(rule, dictionary))
    queries0 = set([('m', 'RR', 'iii', 'kkkk'),
                    ('m', 'II', 'ooo', 'ssss'),
                    ('m', 'II', 'ooo', 'llll')])
    assert queries == queries0, queries

# Three level
def test_nested_4(dictionary=nested_dictionary):
    rule = df.Rule((('m', ), ('MM', 'II'), df.All()))
    queries = set(df.expand_rule(rule, dictionary))
    queries0 = set([('m', 'MM', 'iii'),
                    ('m', 'MM', 'rrr'),
                    ('m', 'MM', 'ooo'),
                    ('m', 'II', 'rrr'),
                    ('m', 'II', 'ooo')])
    assert queries == queries0, queries

    
def test_nested_5(dictionary=nested_dictionary):
    # Four level where last is 's'
    rule = df.Rule((df.All(), df.All(), df.All(), ('ssss', )))
    queries = set(df.expand_rule(rule, dictionary))
    queries0 = set([('m', 'II', 'ooo', 'ssss')])
    assert queries == queries0, queries

    
def test_nested_6(dictionary=nested_dictionary):    
    rule = df.Rule((df.All(), ('MM', 'RR'), df.All(), ('kkkk', 'uuuu')))
    queries = set(df.expand_rule(rule, dictionary))
    queries0 = set([('m', 'MM', 'iii', 'kkkk'),
                    ('m', 'MM', 'iii', 'uuuu'),
                    ('m', 'RR', 'iii', 'kkkk')])
    assert queries == queries0, queries


def test_nested_7(dictionary=nested_dictionary):    
    # Empty one
    rule = df.Rule((df.All(), df.All(), df.All(), df.All(), ('ssss', )))
    queries = set(df.expand_rule(rule, dictionary))
    assert not queries

    
def test_nested_8(dictionary=nested_dictionary):
    # Empty one
    rule = df.Rule(('aa', ))
    queries = set(df.expand_rule(rule, dictionary))
    assert not queries

    
def test_nested_9(dictionary=nested_dictionary):    
    rules = [df.Rule((df.All(), df.All(), df.All(), ('ssss', )))]
    v = df.nested_filter(rules, dictionary)
    assert len(v) == 1
    key,  = list(df.nested_keys(v))
    assert key == ('m', 'II', 'ooo', 'ssss')


def test_nested_lambda(dictionary=nested_dictionary):
    rule = df.Rule((df.All(), (lambda key: len(key) == 2, )))

    queries = set(df.expand_rule(rule, dictionary))
    queries0 = set([('m', 'MM'),
                    ('m', 'II'),
                    ('m', 'RR')])
    assert queries == queries0, queries

    
def test_nested_lambda2(dictionary=nested_dictionary):
    
    pattern = re.compile('^ssss$')
    want = lambda key, pattern=pattern: pattern.match(key) is not None
    rule = df.Rule((df.All(), (lambda key: len(key) == 2, ), df.All(), (want, )))

    queries = set(df.expand_rule(rule, dictionary))
    queries0 = set([('m', 'II', 'ooo', 'ssss')])
    assert queries == queries0, (queries, queries0)

    
# More FHI specific


day_2020_04_10 = {
    'all_contacts': {'cumulative_duration': 804.950495049505,
                     'cumulative_risk_score': 13.415841584158416,
                     'number_of_contacts': 1,
                     'median_distance': 1.0,
                     'cumulative_duration_inside': 15,
                     'cumulative_duration_outside': 20,
                     'points_of_interest': 'school, car',
                     'risk_cat': 'high',
                     'summary_plot': '',
                     'contact_details': [{'duration': 804.950495049505,
                                          'time_from': '2020-04-10 10:01:24',
                                          'time_to': '2020-04-10 10:14:48',
                                          'transport_modes': {('still', 'N/A'): '0:06:39'},
                                          'risk_score': 13.415841584158416,
                                          'average_distance': 1.0,
                                          'median_distance': 1.0,
                                          'average_accuracy': 1.0,
                                          'duration_inside': 15,
                                          'duration_outside': 20,
                                          'pois': {'car': '0:00:10', 'school': '0:00:05', 'outside': '0:00:20'},
                                          'naive_heuristic_duration_inside': 399.0,
                                          'naive_heuristic_duration_outside': 405.950495049505,
                                          'naive_heuristic_pois': {'outside': '0:06:45',
                                                                   'inside_building': '0:06:39',
                                                                   'inside_transport': '0:00:00'},
                                          'most_common_transport_modes': ['still'],
                                          'close_duration': 0.0,
                                          'very_close_duration': 804.950495049505}]},
    'gps_contacts': {'cumulative_duration': 0,
                     'cumulative_risk_score': 0,
                     'number_of_contacts': 0,
                     'median_distance': None,
                     'cumulative_duration_inside': 0,
                     'cumulative_duration_outside': 0,
                     'points_of_interest': '',
                     'risk_cat': 'no',
                     'contact_details': []},
    'bt_contacts': {'cumulative_duration': 804.950495049505,
                    'cumulative_risk_score': 13.415841584158416,
                    'number_of_contacts': 1,
                    'median_distance': 1.0,
                    'cumulative_duration_inside': 15,
                    'cumulative_duration_outside': 20,
                    'points_of_interest': 'school, car',
                    'risk_cat': 'high',
                    'contact_details': [{'duration': 804.950495049505,
                                         'time_from': '2020-04-10 10:01:24',
                                         'time_to': '2020-04-10 10:14:48',
                                         'transport_modes': {('still', 'N/A'): '0:06:39'},
                                         'risk_score': 13.415841584158416,
                                         'average_distance': 1.0,
                                         'median_distance': 1.0,
                                         'average_accuracy': 1.0,
                                         'duration_inside': 15,
                                         'duration_outside': 20,
                                         'pois': {'car': '0:00:10', 'school': '0:00:05', 'outside': '0:00:20'},
                                         'naive_heuristic_duration_inside': 399.0,
                                         'naive_heuristic_duration_outside': 405.950495049505,
                                         'naive_heuristic_pois': {'outside': '0:06:45',
                                                                  'inside_building': '0:06:39',
                                                                  'inside_transport': '0:00:00'},
                                         'most_common_transport_modes': ['still'],
                                         'close_duration': 0.0,
                                         'very_close_duration': 804.950495049505}]}}

cumulative = {'all_contacts':
              {'cumulative_duration': 804.950495049505,
               'cumulative_risk_score': 13.415841584158416,
               'number_of_contacts': 1,
               'median_distance': 1.0,
               'cumulative_duration_inside': 15,
               'cumulative_duration_outside': 20,
               'points_of_interest': 'school, car',
               'risk_cat': 'high',
               'bar_plot': '',
               'contact_details': [{'duration': 804.950495049505,
                                    'time_from': '2020-04-10 10:01:24',
                                    'time_to': '2020-04-10 10:14:48',
                                    'transport_modes': {('still', 'N/A'): '0:06:39'},
                                    'risk_score': 13.415841584158416,
                                    'average_distance': 1.0,
                                    'median_distance': 1.0,
                                    'average_accuracy': 1.0,
                                    'duration_inside': 15,
                                    'duration_outside': 20,
                                    'pois': {'car': '0:00:10', 'school': '0:00:05', 'outside': '0:00:20'},
                                    'naive_heuristic_duration_inside': 399.0,
                                    'naive_heuristic_duration_outside': 405.950495049505,
                                    'naive_heuristic_pois': {'outside': '0:06:45',
                                                             'inside_building': '0:06:39',
                                                             'inside_transport': '0:00:00'},
                                    'most_common_transport_modes': ['still'],
                                    'close_duration': 0.0,
                                    'very_close_duration': 804.950495049505}]},
              'gps_contacts': {'cumulative_duration': 0,
                               'cumulative_risk_score': 0,
                               'number_of_contacts': 0,
                               'median_distance': None,
                               'cumulative_duration_inside': 0,
                               'cumulative_duration_outside': 0,
                               'points_of_interest': '',
                               'risk_cat': 'no',
                               'contact_details': []},
              'bt_contacts': {'cumulative_duration': 804.950495049505,
                              'cumulative_risk_score': 13.415841584158416,
                              'number_of_contacts': 1,
                              'median_distance': 1.0,
                              'cumulative_duration_inside': 15,
                              'cumulative_duration_outside': 20,
                              'points_of_interest': 'school, car',
                              'risk_cat': 'high',
                              'contact_details': [{'duration': 804.950495049505,
                                                   'time_from': '2020-04-10 10:01:24',
                                                   'time_to': '2020-04-10 10:14:48',
                                                   'transport_modes': {('still', 'N/A'): '0:06:39'},
                                                   'risk_score': 13.415841584158416,
                                                   'average_distance': 1.0,
                                                   'median_distance': 1.0,
                                                   'average_accuracy': 1.0,
                                                   'duration_inside': 15,
                                                   'duration_outside': 20,
                                                   'pois': {'car': '0:00:10', 'school': '0:00:05', 'outside': '0:00:20'},
                                                   'naive_heuristic_duration_inside': 399.0,
                                                   'naive_heuristic_duration_outside': 405.950495049505,
                                                   'naive_heuristic_pois': {'outside': '0:06:45',
                                                                            'inside_building': '0:06:39',
                                                                            'inside_transport': '0:00:00'},
                                                   'most_common_transport_modes': ['still'],
                                                   'close_duration': 0.0,
                                                   'very_close_duration': 804.950495049505}]}}
    
# NOTE: this is fake data
data = {'9b55b50c729411ea80ea42a51fad92d3':
        {'cumulative': cumulative,
         'daily': {'2020-04-10': day_2020_04_10,
                   '2020-04-11': day_2020_04_10}}} 

# Testing functionality
def compare(d1, d2):
    '''Comparing dict and possibly default dict'''
    keys = set(df.nested_keys(d1))
    if not keys == set(df.nested_keys(d2)):
        return False
    return all(df.nested_get(d1, key) == df.nested_get(d2, key) for key in keys)


def test_copy(data=data):
    fdata = df.nested_filter([df.Rule((df.All(), ))], data)
    assert compare(data, fdata)


# Rule logic
def test_include(data=data):
    fdata = df.nested_filter([df.Rule((df.All(), ('cumulative', )))], data)
    data0 = {'9b55b50c729411ea80ea42a51fad92d3': {'cumulative': data['9b55b50c729411ea80ea42a51fad92d3']['cumulative']}}
    assert compare(data0, fdata)

    
def test_not(data=data):
    rules = [df.Rule((df.All(), ('daily', ), df.All()))]
    fdata = df.nested_filter(rules, data)
    data0 = {'9b55b50c729411ea80ea42a51fad92d3': {'daily': {'2020-04-10': data['9b55b50c729411ea80ea42a51fad92d3']['daily']['2020-04-10'],
                                                            '2020-04-11': data['9b55b50c729411ea80ea42a51fad92d3']['daily']['2020-04-11']}}}
    assert compare(data0, fdata)

    
def test_invalid_key(data=data):
    fdata = df.nested_filter([df.Rule((('1',)))], data)
    assert not len(fdata)

   
def test_fhi_report(data=data):
    data = df.fhi_filter_dict(data)
    # We can find all keys
    for key in chain(*[df.expand_rule(data, r) for r in df.FHI_RULES]):
        df.nested_get(data, key)
    assert True
