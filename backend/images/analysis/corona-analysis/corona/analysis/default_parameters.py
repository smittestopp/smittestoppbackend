"""
File contains descriptions and default settings for parameters used within
analysis. Parameters are:

    analysis_duration_in_days : number of days in the past that should be considered in the analysis

    max_interpol_in_h : maximum duration in hours that is allowed to be interpolated

    allowed_jump : maximum distance that is allowed to be interpolated in meters

    outlier_treshhold : GPS data with accuracy < outlier_threshold is discarded

    glue_below_duration: Contacts that are apart less than this value [in seconds] are glued together,
                         even if is GPS data in between suggesting otherwise
    min_duration: minimum duration in seconds for a contact to be not an outlier and thus not discarded

    bt_glue_below_duration: same as glue_below_duration but for bluetooth data

    bt_min_duration: same as min_duration but for bluetooth data

    gps_dt_threshold: None or number in seconds;
     None - keeps original data
     number - keeps events whose distance based on encounterstattime is > threshold

    gps_dx_threshold: None or number in meters;
     None - keeps original data
     number - keeps consecutive events whose distance is > threshold

    bt_dt_threshold: same as gps_dt_threshold but for BT data (based on timefrom)

    filter options : parameters for filter function in distance computations, i.e:
        dist_thresh:
        weight_dist_max:
        weight_dist_min:
        weight_min_val:
        filtre_size:

    pois_options : parameters for all the points of interest operations, i.e.
        inside_transport_modes: modes of transport assumed to be 'inside contacts'
        walking_modes: modes of transport for which we look for points of interest
        accuracy_radius_factor: factor of the total accuracy kept for radius of pois search (depends on transport modes)
        transport_filtration_duration: min duration for pre-processing of filtering transport mode pairs for pois
        pois_filtration_duration: min duration for filtering suspicious points of interest detected
        pois_filtration_frequency: min frequency for filtering suspicious points of interest detected
        dict_of_buildings: dictionary of building labels
        types_of_amenities: types of amenities to query
        proportion_threshold: % of the total duration pois must represent to not be filtered
        duration_threshold: min duration pois must have to not be filtered
        long_duration_threshold: min duration pois must have to not be filtered if they do not satisfy the proportion threshold
        keep_uncertain: whether uncertain is displayed in general in filtered pois

"""

def dict_of_buildings():
    """ Create a dictionary to rename/group detected points of interest """
    bars_and_restaurants = ['bar', 'bbq', 'biergarten', 'cafe', 'drinking_water', 'fast_food', 'food_court', 'ice_cream', 'pub', 'restaurant']
    education_facility = ['driving_school','language_school','library','toy_library','music_school']
    schools = ['school']
    universities = ['university','college']
    kindergartens = ['kindergarten']
    healthcare_facility = ['baby_hatch','dentist','doctors','pharmacy','veterinary']
    hospitals = ['hospital', 'clinic']
    nursing_homes = ['nursing_home', 'social_facility', 'community_centre'] # they are often labelled as such in Norway
    arts_entertainment_culture = ['cinema','casino','arts_centre','studio','planetarium','nightclub','gambling','public_bookcase','stripclub','theatre']
    sport = ['grandstand','pavilion','riding_hall','sports_hall','stadium']
    commercial = ['commercial','industrial','kiosk','retail','supermarket','warehouse','charging_station','bicycle_rental']
    religious = ['cathedral','chapel','church','mosque','religious','shrine','synagogue','temple']
    residential = ['apartments','bungalow','cabin','detached','dormitory','farm','ger','hotel','house','houseboat',
                   'residential','semidetached_house','static_caravan','terrace','shed']
    dict_of_buildings = {}
    dict_of_buildings.update({item: 'bars_and_restaurants' for item in bars_and_restaurants})
    dict_of_buildings.update({item: 'education_facility' for item in education_facility})
    dict_of_buildings.update({item: 'healthcare_facility' for item in healthcare_facility})
    dict_of_buildings.update({item: 'arts_entertainment_culture' for item in arts_entertainment_culture})
    dict_of_buildings.update({item: 'school' for item in schools})
    dict_of_buildings.update({item: 'university' for item in universities})
    dict_of_buildings.update({item: 'kindergarten' for item in kindergartens})
    dict_of_buildings.update({item: 'hospital' for item in hospitals})
    dict_of_buildings.update({item: 'nursing_home' for item in nursing_homes})
    dict_of_buildings.update({item: 'shop' for item in commercial})
    dict_of_buildings.update({item: 'residential' for item in residential})
    dict_of_buildings.update({item: 'religious_building' for item in religious})
    dict_of_buildings.update({item: 'sport_facility' for item in sport})
    return dict_of_buildings


params = {
        'analysis_duration_in_days' : 7,
        'max_interpol_in_h' : 1,
        'allowed_jump' : 1000,
        'outlier_threshold' : 50,
        'glue_below_duration' : 3 * 60,
        'min_duration' : 5 * 60,
        'max_interpolation_duration_gps_for_bt' : 300,
        'bt_outlier_threshold' : 1000,
        'bt_glue_below_duration' : 0,
        'bt_min_duration' : 1,
        'gps_dt_threshold': None,
        'gps_dx_threshold': None,
        'bt_dt_threshold' : None,
        'filter_options' : {"dist_thresh": 10,
                            "weight_dist_max" : 100,
                            "weight_dist_min" : 10,
                            "weight_min_val" : 0.05,
                            "filtre_size" : 2},
        'pois_options' : {"inside_transport_modes": ['public_transport', 'vehicle'],
                          "walking_modes": ['still', 'on_foot'],
                          "accuracy_radius_factor": [1.1,0.9,0.65,0.0],
                          "transport_filtration_duration": 60,
                          "pois_filtration_duration": 60,
                          "pois_filtration_frequency": 1,
                          "dict_of_buildings": dict_of_buildings(),
                          "types_of_amenities": ['all_buildings','amenity_all', 'public_transport', 'offices', 'shop_generalstores'],
                          "proportion_threshold" : 0.2, # 20 %
                          "duration_threshold" : 60,
                          "long_duration_threshold" : 300,
                          "keep_uncertain" : False}

}
