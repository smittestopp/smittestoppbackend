
import numpy as np
import pandas as pd

from collections import Counter

from corona.map.api import OverpassAPI
from corona.map.utils import get_overpass_df_from_list

def get_pois_contacted_with_points(df, amenities, padding=-1, max_padding=100, column_name="accuracy"):

    api = OverpassAPI()

    contact_info = {}
    pois_list = []
    pois_info = []

    df.reset_index( drop=True, inplace=True)

    points = list(zip(df.latitude, df.longitude))

    if padding < 0:
        padding = [ min(accuracy, max_padding) for accuracy in list(df[column_name]) ]

    results = api.query_points(points, amenities, padding)
    # TODO Use batched POI query
    # results = api.query_points_batched(points, amenities, padding)
    results = np.array_split(results, len(points))

    for index, result in enumerate(results):

        points_of_interest = get_overpass_df_from_list(result)

        info = [ np.nan ]
        contacted = points_of_interest is not None

        if contacted:
            info = list(points_of_interest.id)
            pois_info.append(points_of_interest)
            pois_list = pois_list + info

        contact_info[ index ] = { "contacted_pois": info, "contacted": contacted }

    pois_contact_count = Counter(pois_list)

    for _, value in contact_info.items():
        ranks = [ pois_contact_count[ poi ] for poi in value[ "contacted_pois"] ]
        value.update({
            "ranks": ranks,
            "selected_poi": str(value[ "contacted_pois" ][ np.argmax(ranks) ])
        })

    contact_info_df = pd.DataFrame.from_dict(contact_info, orient='index')

    if len(pois_info) > 0:
        poi_df = pd.concat(pois_info, ignore_index=True)
        poi_df.drop_duplicates(subset="id", inplace=True)
    else:
        poi_df = pd.DataFrame()

    result_points_df = pd.concat([ df, contact_info_df ], axis=1, sort=False)

    return result_points_df, poi_df, pois_contact_count

def get_pois_contacted_with_points_v3(df, amenities, padding=-1, max_padding=100, column_name="accuracy", mt=True):

    api = OverpassAPI()

    contact_info = {}
    pois_list = []
    pois_info = []

    df.reset_index( drop=True, inplace=True)

    points = list(zip(df.latitude, df.longitude))

    if padding < 0:
        padding = [ min(accuracy, max_padding) for accuracy in list(df[column_name]) ]

    #results = api.query_points(points, amenities, padding)

    results = api. query_points_batched(points, amenities, padding, element_types=None, mt_split=mt)
    # TODO Use batched POI query
    # results = api.query_points_batched(points, amenities, padding)
    results = np.array_split(results, len(points))

    for index, result in enumerate(results):

        points_of_interest = get_overpass_df_from_list(result)

        info = [ np.nan ]
        contacted = points_of_interest is not None

        if contacted:
            info = list(points_of_interest.id)
            pois_info.append(points_of_interest)
            pois_list = pois_list + info

        contact_info[ index ] = { "contacted_pois": info, "contacted": contacted }

    pois_contact_count = Counter(pois_list)

    for _, value in contact_info.items():
        ranks = [ pois_contact_count[ poi ] for poi in value[ "contacted_pois"] ]
        value.update({
            "ranks": ranks,
            "selected_poi": str(value[ "contacted_pois" ][ np.argmax(ranks) ])
        })

    contact_info_df = pd.DataFrame.from_dict(contact_info, orient='index')

    if len(pois_info) > 0:
        poi_df = pd.concat(pois_info, ignore_index=True)
        poi_df.drop_duplicates(subset="id", inplace=True)
    else:
        poi_df = pd.DataFrame()

    result_points_df = pd.concat([ df, contact_info_df ], axis=1, sort=False)

    return result_points_df, poi_df, pois_contact_count

def get_all_almost_contacted_points_v2(points_df, types_of_amenities, distance=-1, max_distance=100, check_results=False):

    api = OverpassAPI()
    contact_info = {}
    pois_list = []
    pois_info = []

    points_df.reset_index(drop=True, inplace=True) # reset index for final mergin

    points = list(zip(points_df.latitude, points_df.longitude))
    distances = list(points_df.accuracy)
    distances_filtered = []

    if distance < 0:

        for d in distances:
            if d <= max_distance:
                distances_filtered.append(d)
            else:
                distances_filtered.append(max_distance)

    else:
        distances_filtered = [distance for d in range(len(distances))]

    results = api.query_points(points,types_of_amenities,distances_filtered)
    # results = get_types_from_points_parallel_OLD(points, distances_filtered, types_of_amenities)
    results = np.array_split(results, len(points))

    for i,result in enumerate(results):
        pois = get_overpass_df_from_list(result)

        if pois is None:
            contact_info[i] = {"contacted_pois":[np.nan], "contacted": False}

        else:
            pois_info.append(pois)
            l = list(pois.id)
            contact_info[i] = {"contacted_pois":l, "contacted": True}
            pois_list = pois_list + l

    pois_contact_count = Counter(pois_list)

    for k,v in contact_info.items():
        ranks = []
        for poi in v["contacted_pois"]:
            ranks.append(pois_contact_count[poi])

        contact_info[k].update({"ranks": ranks})
        contact_info[k].update({"selected_poi": str(v["contacted_pois"][np.argmax(ranks)])})

    contact_info_df = pd.DataFrame.from_dict(contact_info, orient='index')

    if len(pois_info) > 0:
        poi_df = pd.concat(pois_info, ignore_index=True)
        poi_df.drop_duplicates(subset="id", inplace=True) # remove duplicated
    else:
        poi_df = pd.DataFrame() # empty dataframe

    result_points_df = pd.concat([points_df, contact_info_df], axis=1, sort=False)

    return result_points_df, poi_df, pois_contact_count
