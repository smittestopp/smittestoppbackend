import math
import json
from typing import List

import pandas as pd

import shapely
from shapely.geometry import Point, Polygon, MultiPolygon, LineString, box


def make_bounding_box(p_latitude, p_longitude, distance_in_meters) -> List[float]:
    """For a given lat and long point get the bounding box around them for a certain distance"""

    lat_radian: float = math.radians(p_latitude)

    deg_lat_km: float = 110.574235
    deg_lon_km: float = 110.572833 * math.cos(lat_radian)
    delta_lat: float = distance_in_meters / 1000.0 / deg_lat_km
    delta_lon: float = distance_in_meters / 1000.0 / deg_lon_km

    min_lat: float = p_latitude - delta_lat
    min_lon: float = p_longitude - delta_lon
    max_lat: float = p_latitude + delta_lat
    max_lon: float = p_longitude + delta_lon

    return [min_lat, min_lon, max_lat, max_lon]


def get_overpass_df_from_list(result_list, drop_duplicates=True):
    """Get df or geodf from list of resutls"""

    df_list = []

    for result in result_list:

        result = get_overpass_df(result)

        if result is not None:
            df_list.append(result)

    if len(df_list) == 0:
        return None

    df = pd.concat(df_list, ignore_index=True)

    if drop_duplicates:
        df.drop_duplicates(subset="id", inplace=True)

    return df


def get_overpass_df(jsn):
    if jsn is None:
        return None
    if not 'elements' in jsn:
        return None

    df = pd.DataFrame(jsn['elements'])  # convert into dat frame

    if df.empty:
        return None

    # converting normal geometry informations into shapely.geometry types
    df["geometry"] = df.apply(get_geometry_data, axis=1)

    return df


def get_geometry_data(row):
    if row.type == "node":
        bounding_box = make_bounding_box(row.lon, row.lat, 10)  # 10 meters bounding boxes
        return shapely.geometry.box(*bounding_box)  # every point is represented by a bounding box

    elif row.type == "way":
        geometry_df = pd.DataFrame(row.geometry)
        coords = list(zip(geometry_df.lon, geometry_df.lat))

        if len(coords) < 3:
            line = LineString(coords)
            return line.buffer(0.0001, cap_style=0)

        return Polygon(coords)

    elif row.type == "relation":
        member_df = pd.DataFrame(row.members)
        member_df["geometry"] = member_df.apply(get_geometry_data, axis=1)

        return MultiPolygon(list(member_df["geometry"]))
