from __future__ import annotations

import json
import math
from typing import List, Dict, Any, Iterable

import numpy as np
import requests
import concurrent.futures
import time
import os
import hashlib

from functools import partial, reduce

from enum import Enum
from dataclasses import dataclass
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from collections import defaultdict

from corona import logger, logging
from corona.map.utils import make_bounding_box
from corona.utils import haversine_distance
from corona.config import __CONFIG__

_QUERY_TYPES = dict(
    all_buildings='building',
    bank_and_atm='amenity~"bank|atm"',
    education='amenity~"college|driving_school|kindergarten|language_school|library|music_school|school|university"',
    amenity_all='amenity',
    healthcare='amenity~"clinic|dentist|doctors|hospital|nursing_home|pharmacy|social_facility"',
    public_transport='public_transport~"platform|stop_position"',
    shops_all='shop',
    shop_generalstores='shop~"department_store|general|kiosk|mall|supermarket|wholesale"',
    apartments='building~"apartments|residential"',
    offices='office',
    schools='amenity~"school"',
    bars_and_restaurants='amenity~"bar|bbq|biergarten|cafe|drinking_water|fast_food|food_court|ice_cream|pub|restaurant"',
    kindergartens='amenity~"kindergarten"',
    hospitals='amenity~"hospital|clinic"',
    nursing_homes='amenity~"nursing_home|social_facility|community_centre"',
    commercial='amenity~"commercial|industrial|kiosk|retail|supermarket|warehouse|charging_station|bicycle_rental"',
    residential='building~"apartments|bungalow|cabin|detached|dormitory|farm|ger|hotel|house|houseboat|residential|semidetached_house|static_caravan|terrace|shed"')

_REQUIRED_ELEMENT_TYPES = defaultdict(lambda: ["node", "way"])
_REQUIRED_ELEMENT_TYPES.update(dict(
    all_buildings=["way"],
    apartments=["way"],
    offices=["node"],
    shops_all=["node"],
    shop_generalstores=["node"],
    bank_and_atm=["node"],
    public_transport=["node", "way", "relation"],
    amenity_all=["node", "way", "relation"],
    healthcare=["node", "way", "relation"],
    education=["node", "way", "relation"],
    schools=["node", "way", "relation"],
    residential=["node", "way", "relation"]))


class ElementType(Enum):
    node = 'node'
    way = 'way'
    relation = 'relation'


class Tag(Enum):
    amenity = 'amenity'
    building = 'building'
    public_transport = 'public_transport',
    shop = 'shop',
    office = 'office'


@dataclass(frozen=True)
class BoundingBox:
    minlat: float
    minlon: float
    maxlat: float
    maxlon: float

    def to_query(self):
        return f"{self.minlat},{self.minlon},{self.maxlat},{self.maxlon}"

    def combine(self, box: BoundingBox) -> BoundingBox:
        return BoundingBox(
            minlat=min(self.minlat, box.minlat),
            minlon=min(self.minlon, box.minlon),
            maxlat=max(self.maxlat, box.maxlat),
            maxlon=max(self.maxlon, box.maxlon))

    def contained_elements(self, els: List[Dict[str, Any]]):
        return [el for el in els if self.__contains_element(el)]

    def area_str(self) -> str:
        sqm = self.sqm()
        if sqm > 1000000:
            return f"{int(sqm / 1000000)}km^2"
        return f"{int(sqm)}m^2"

    def sqkm(self) -> float:
        return self.sqm() / 1000000

    def sqm(self) -> float:
        return haversine_distance(self.minlat, self.minlon, self.maxlat, self.minlon) * \
               haversine_distance(self.minlat, self.minlon, self.minlat, self.maxlon)

    def __contains_element(self, e: Dict[str, Any]) -> bool:
        try:
            if 'bounds' in e:
                b = e['bounds']
                element_box: BoundingBox = BoundingBox(
                    minlat=b['minlat'],
                    minlon=b['minlon'],
                    maxlat=b['maxlat'],
                    maxlon=b['maxlon'])
                return element_box.__overlaps_with(self) or self.__overlaps_with(element_box)
            else:
                return self.__contains(e['lat'], e['lon'])
        except KeyError as ke:
            raise ValueError(f"Invalid element contained neither valid bounds nor lat/lon pair: {str(e)}") from ke

    def __overlaps_with(self, box: BoundingBox) -> bool:
        return self.__contains(box.minlat, box.minlon) or \
               self.__contains(box.maxlat, box.maxlat) or \
               self.__contains(box.maxlat, box.minlon) or \
               self.__contains(box.minlat, box.maxlon)

    def __contains(self, lat: float, lon: float) -> bool:
        return self.minlat < lat < self.maxlat and self.minlon < lon < self.maxlon


@dataclass
class QueryType:
    name: str
    tag: Tag
    element_types: List[ElementType]
    values: List[str] = None

    def to_queries(self, override_element_types=None) -> Iterable[str]:
        return [f"{element_type.name}[{self.__query()}]" for element_type in self.__types(override_element_types)]

    def matching_elements(self, elements: Iterable[Dict[str, Any]]):
        return [element for element in elements if self.__is_matching_element(element)]

    def __query(self) -> str:
        if self.values is None:
            return self.tag.name
        if len(self.values) == 0:
            return self.tag.name
        values: str = "|".join(self.values)
        return f"{self.tag.name}~\"{values}\""

    def __types(self, override_element_types=None) -> Iterable[ElementType]:
        if override_element_types is None:
            return self.element_types
        if len(override_element_types) == 0:
            return self.element_types
        return override_element_types

    def __is_matching_element(self, element: Dict[str, Any]) -> bool:
        if 'tags' in element:
            tags = element['tags']
            if self.tag.name in tags:
                if self.values is None:
                    return True
                if len(self.values) == 0:
                    return True
                value: str = tags[self.tag.name]
                return (value == 'yes') or (self.values is not None) and (value in self.values)
        return False


def bounding_box(p_latitude, p_longitude, distance_in_meters) -> BoundingBox:
    """
    For a given lat and long point get the bounding box around them for a certain distance
    """

    lat_radian: float = math.radians(p_latitude)

    deg_lat_km: float = 110.574235
    deg_lon_km: float = 110.572833 * math.cos(lat_radian)

    delta_lat: float = distance_in_meters / 1000.0 / deg_lat_km
    delta_lon: float = distance_in_meters / 1000.0 / deg_lon_km

    return BoundingBox(
        minlat=p_latitude - delta_lat,
        minlon=p_longitude - delta_lon,
        maxlat=p_latitude + delta_lat,
        maxlon=p_longitude + delta_lon)


_QUERY_TYPES_LIST = [
    QueryType(
        'all_buildings', Tag.building,
        element_types=[ElementType.way]),
    QueryType(
        'bank_and_atm', Tag.amenity,
        values=['bank', 'atm'],
        element_types=[ElementType.node]),
    QueryType(
        'education', Tag.amenity,
        values=[
            'college', 'driving_school', 'kindergarten', 'language_school', 'library', 'music_school',
            'school', 'university'],
        element_types=[ElementType.node, ElementType.way, ElementType.relation]),
    QueryType(
        'amenity_all', Tag.amenity,
        element_types=[ElementType.node, ElementType.way, ElementType.relation]),
    QueryType(
        'healthcare', Tag.amenity,
        values=['clinic', 'dentist', 'doctors', 'hospital', 'nursing_home', 'pharmacy', 'social_facility'],
        element_types=[ElementType.node, ElementType.way, ElementType.relation]),
    QueryType(
        'public_transport', Tag.public_transport,
        values=['platform', 'stop_position'],
        element_types=[ElementType.node, ElementType.way, ElementType.relation]),
    QueryType(
        'shops_all', Tag.shop,
        element_types=[ElementType.node]),
    QueryType(
        'shop_generalstores', Tag.shop,
        values=['department_store', 'general', 'kiosk', 'mall', 'supermarket', 'wholesale'],
        element_types=[ElementType.node]),
    QueryType(
        'apartments', Tag.building,
        values=['apartments', 'residential'],
        element_types=[ElementType.way]),
    QueryType(
        'offices', Tag.office,
        element_types=[ElementType.node]),
    QueryType(
        'schools', Tag.amenity,
        values=['school'],
        element_types=[ElementType.node, ElementType.way, ElementType.relation]),
    QueryType(
        'bars_and_restaurants', Tag.amenity,
        values=['bar', 'bbq', 'biergarten', 'cafe', 'drinking_water', 'fast_food', 'food_court',
                'ice_cream', 'pub', 'restaurant'],
        element_types=[ElementType.node, ElementType.way]),
    QueryType(
        'kindergartens', Tag.amenity,
        values=['kindergarten'],
        element_types=[ElementType.node, ElementType.way]),
    QueryType(
        'hospitals', Tag.amenity,
        values=['hospital', 'clinic'],
        element_types=[ElementType.node, ElementType.way]),
    QueryType(
        'nursing_homes', Tag.amenity,
        values=['nursing_home', 'social_facility', 'community_centre'],
        element_types=[ElementType.node, ElementType.way]),
    QueryType(
        'commercial', Tag.amenity,
        values=['commercial', 'industrial', 'kiosk', 'retail', 'supermarket', 'warehouse',
                'charging_station', 'bicycle_rental'],
        element_types=[ElementType.node, ElementType.way]),
    QueryType(
        'residential', Tag.building,
        values=['apartments', 'bungalow', 'cabin', 'detached', 'dormitory', 'farm', 'ger', 'hotel', 'house',
                'houseboat', 'residential', 'semidetached_house', 'static_caravan', 'terrace', 'shed'],
        element_types=[ElementType.node, ElementType.way, ElementType.relation])]

_QUERY_TYPES_INDEX = {query_type.name: query_type for query_type in _QUERY_TYPES_LIST}


class RetrySession(requests.Session):
    def __init__(self, max_retries=5, backoff_factor=0.2,
                 status_forcelist=(500, 502, 504), max_workers=1000):
        super().__init__()
        adapter = HTTPAdapter(
            max_retries=Retry(
                total=max_retries,
                read=max_retries,
                connect=max_retries,
                backoff_factor=backoff_factor,
                status_forcelist=status_forcelist),
            pool_connections=max_workers,
            pool_maxsize=max_workers)
        self.mount("http://", adapter)
        self.mount("https://", adapter)


def query_batch(queries: List[str]) -> str:
    batched_query: str = ""
    for i, query in enumerate(queries):
        batched_query += f"({query})->.t{i};.t{i} out count;.t{i} out body geom;"
    return batched_query


class OSMBaseAPI:

    def __init__(self, verbose=0, cachedir=__CONFIG__.cache.location,
                 connect_timeout=5, read_timeout=20, max_retries=5,
                 max_workers=32, enable_caching=__CONFIG__.cache.enabled):

        self.verbose = verbose
        self.cachedir = cachedir
        self.caching = enable_caching

        if not os.path.exists(cachedir):
            os.makedirs(cachedir)

        self.max_retries = max_retries
        self.max_workers = max_workers

        self.read_timeout = read_timeout
        self.connect_timeout = connect_timeout

        self.timeout = (self.connect_timeout, self.read_timeout)

        self.session = RetrySession(
            max_retries=self.max_retries,
            max_workers=self.max_workers
        )

    @staticmethod
    def __hash(string):
        h = hashlib.sha1()
        h.update(string.encode("utf-8"))
        return h.hexdigest()

    @staticmethod
    def __load_from_cache(filename) -> Dict[str, Any]:
        with open(filename, "r") as f:
            return json.load(f)

    @staticmethod
    def __save_to_cache(filename, data):
        with open(filename, "w") as f:
            json.dump(data, f)

    def __get(self, url: str) -> Dict[str, Any]:
        # filename: str = os.path.join(self.cachedir, self.__hash(url))
        # if self.caching and os.path.exists(filename):
        #     return self.__load_from_cache(filename)
        response = self.session.get(url, timeout=self.timeout).json()
        # if self.caching:
        #     self.__save_to_cache(filename, response)
        return response

    def query_single(self, url):
        try:
            response = self.__get(url)
        except Exception as ex:
            logger.warn("Failed to process single OSM request: %s", url, ex)
            return None
        return response

    def query_timed(self, url: str) -> Dict[str, Any]:
        start_time: float = time.time()
        response: Dict[str, Any] = self.__get(url)
        duration_sec: float = time.time() - start_time
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("OSM query took ~%s: %s", int(duration_sec), url)
        else:
            logger.info("OSM query took ~%s: %s chars", duration_sec, len(url))
        return response

    def query_multiple_mt(self, queries, wrapper) -> List[Dict[str, Any]]:
        ordered_output: List[Dict[str, Any]] = [{}] * len(queries)
        success: int = 0
        logger.info("Starting %s OSM requests...", len(queries))
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for index, url in enumerate(queries):
                futures[executor.submit(partial(self.__get, wrapper(url)))] = index
            for future in concurrent.futures.as_completed(futures):
                try:
                    response = future.result()
                    ordered_output[futures[future]] = response
                    success += 1
                except Exception as ex:
                    if self.verbose > 0:
                        logger.warning(ex)
            logger.info("Successfully processed %s / %s OSM requests.", success, len(queries))
        return ordered_output


class NominatimAPI(OSMBaseAPI):
    endpoint = __CONFIG__.nominatim.endpoint

    def query_address(self, latitude, longitude):
        query = self.endpoint + "reverse?format=geojson&lat=%s&lon=%s" % (latitude, longitude)
        return self.query_single(query)

    def query_osm_id(self, osm_id, element_type="W"):
        query = self.endpoint + "lookup?osm_ids=%s%s&polygon_kml=1&format=json" % (element_type, osm_id)
        return self.query_single(query)

    def query_country(self, country="Norway"):
        query = self.endpoint + "search?country=%s&polygon_kml=1&format=json" % country
        return self.query_single(query)

    def query_search(self, search):
        query = self.endpoint + "?addressdetails=1&q=%s&format=json&limit=1" % search
        return self.query_single(query)


class OverpassAPI(OSMBaseAPI):
    endpoint = __CONFIG__.overpass.endpoint
    batched = __CONFIG__.overpass.batched
    batched_mt_threshold = __CONFIG__.overpass.batched_mt_threshold

    def __simple_query_wrapper(self, query: str) -> str:
        return f"{self.__query_wrapper(query)}out body geom;"

    def __query_wrapper(self, query: str) -> str:
        return f"{self.endpoint}interpreter?data=[out:json];{query}"

    def __global_query_wrapper(self, box: BoundingBox, queries: Iterable[str]) -> str:
        box: str = box.to_query()
        q: str = ''.join(queries)
        return f"{self.endpoint}interpreter?data=[out:json][bbox:{box}];{q}"

    @staticmethod
    def __query_merge(queries, n_splits=10):
        merged_queries = defaultdict(list)
        for query in queries:
            parts = query.split("[out:json];")
            merged_queries[parts[0] + "[out:json];"].append(parts[1])
        queries = []
        for key in merged_queries:
            for i in range((len(merged_queries[key]) // n_splits) + 1):
                queries.append(key + "".join(merged_queries[key][i: i + n_splits]))
        return queries

    @staticmethod
    def __build_bounding_box_query(box, query_type, element_types) -> str:
        bounding_box_string: str = ",".join(map(str, box))
        if element_types is None:
            element_types = _REQUIRED_ELEMENT_TYPES[query_type]
        query_type = _QUERY_TYPES[query_type]
        query: str = ""
        for element_type in element_types:
            query += f"{element_type}[{query_type}]({bounding_box_string});"
        return query

    @staticmethod
    def __build_polygon_query(polygon, query_type, element_types) -> str:
        polygon_string: str = " ".join(map(str, polygon))
        if element_types is None:
            element_types = _REQUIRED_ELEMENT_TYPES[query_type]
        query_type: str = _QUERY_TYPES[query_type]
        query: str = ""
        for element_type in element_types:
            query += f"{element_type}[{query_type}](poly: '{polygon_string}');"
        return query

    def __build_id_query(self, osm_id, element_types):
        query = ""
        for element_type in element_types:
            query += "%s(id:%s);" % (element_type, osm_id)
        return self.__simple_query_wrapper(query)

    def __build_point_query(self, latitude, longitude, query_type, distance, element_types):
        box = make_bounding_box(latitude, longitude, distance)
        return self.__build_bounding_box_query(box, query_type, element_types)

    def query_metadata_from_osmid(self, osm_id, element_types=None):
        query = self.__build_id_query(osm_id, element_types)
        return self.query_single(query)

    def query_bounding_box(self, box, query_type, element_types=None):
        query = self.__build_bounding_box_query(box, query_type, element_types)
        return self.query_single(query)

    def query_polygon(self, polygon, query_type, element_types=None):
        query = self.__build_polygon_query(polygon, query_type, element_types)
        return self.query_single(query)

    def query_point(self, latitude, longitude, query_type, distance, element_types=None):
        query = self.__build_point_query(latitude, longitude, query_type, distance, element_types)
        return self.query_single(query)

    def query_polygons(self, polygons, query_types, element_types=None) -> List[Dict[str, Any]]:
        queries: List[str] = []
        for polygon in polygons:
            for query_type in query_types:
                queries.append(self.__build_polygon_query(polygon, query_type, element_types))
        return self.query_multiple_mt(queries, self.__simple_query_wrapper)

    def query_points(
            self,
            points,
            query_types,
            distances,
            element_types=None,
            mt_split=False,
            mt_threshold=0
    ) -> List[Dict[str, Any]]:
        if self.batched:
            return self.query_points_batched(
                points, query_types, distances, element_types, mt_split=mt_split, mt_threshold=mt_threshold)
        return self.query_points_single(distances, element_types, points, query_types)

    def query_points_single(self, distances, element_types, points, query_types):
        if type(distances) == int:
            distances = [distances] * len(points)
        bounding_boxes: List[List[float]] = []
        for point, distance in zip(points, distances):
            bounding_boxes.append(make_bounding_box(point[0], point[1], distance))
        queries: List[str] = []
        for box, distance in zip(bounding_boxes, distances):
            for query_type in query_types:
                queries.append(self.__build_bounding_box_query(box, query_type, element_types))
        return self.query_multiple_mt(queries, self.__simple_query_wrapper)

    def query_points_batched(
            self,
            points: List[List[float]],
            query_type_names: List[str],
            distances,
            element_types=None,
            mt_split=True,
            mt_threshold=0
    ) -> List[Dict[str, Any]]:
        """
        This method needs some cleaning up.

        :param points: The points, as a list of pairs of coordinates
        :param query_type_names: Query types, as in the _QUERY_TYPES_LIST dict.  Types of POIs to retrieve
        :param distances: Accuracy/distances for each point.  Can be an integer, which sets a distance for each point
        :param element_types: The types of OSM structures to retreive
        :param mt_split:
        :param mt_threshold:
        :return:
        """
        query_types: Iterable[QueryType] = [_QUERY_TYPES_INDEX[query_type] for query_type in query_type_names]

        trajectory_length = len(points)
        if type(distances) == int:
            distances = [distances] * trajectory_length

        # The OSM query denoting poi types and their node/way/relation setup
        type_queries: Iterable[str] = self.__type_queries(element_types, query_types)

        # Decide on multithreading parameters ...
        resolved_mt_threshold = max(self.batched_mt_threshold, mt_threshold)
        resolved_mt = (resolved_mt_threshold > 0) and self.batched or mt_split

        # Compute the bounding boxes and the containing bounding box
        bounding_boxes, containing_box = self.__bounding_boxes(points, distances)
        sqkm = containing_box.sqkm()

        if trajectory_length > 100 or sqkm > 10.0:
            # We need to split the box.  (All hard-coded parameters here are candidates for configuration.)
            split_count = max(2, int(min(trajectory_length / 2, trajectory_length / 50)))
            logger.info(f"Trajectory[{trajectory_length}] spans {containing_box.area_str()}, split in {split_count}")
            trajectory_splits = np.array_split(points, split_count)
            distances_splits = np.array_split(distances, split_count)
            query_hits_splits = []

            if resolved_mt and split_count > resolved_mt_threshold:
                # We want to multi-thread to exploit the OSM capacity
                ordered_output: List[Dict[str, Any]] = [{}] * split_count
                success: int = 0
                logger.info(f"Starting {split_count} OSM sub-threads...")
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = {}
                    for index in range(0, split_count):
                        futures[
                            executor.submit(partial(
                                self.subquery,
                                trajectory_splits[index],
                                distances_splits[index],
                                query_type_names,
                                query_types,
                                type_queries))
                        ] = index
                    for future in concurrent.futures.as_completed(futures):
                        try:
                            response = future.result()
                            ordered_output[futures[future]] = response
                            success += 1
                        except Exception as ex:
                            logger.warn("Failed to query OSM", ex)
                    logger.info(f"Successfully processed {success:d} / {split_count:d} OSM requests.")
                for output in ordered_output:
                    query_hits_splits.extend(output)
                return query_hits_splits
            else:
                # Run the boxes in sequence, avoid the overhead of multithreading
                for i in range(0, split_count):
                    hits = self.subquery(
                        trajectory_splits[i],
                        distances_splits[i],
                        query_type_names,
                        query_types,
                        type_queries)
                    query_hits_splits.extend(hits)
            return query_hits_splits
        else:
            # Run the whole box in one go
            return self.query_hits_partial_trajectory(
                query_type_names,
                bounding_boxes,
                containing_box,
                query_types,
                type_queries)

    def subquery(
            self,
            trajectory_split,
            distances_split,
            query_type_names,
            query_types,
            type_queries
    ):
        """
        This method is mainly needed to work with the API of the executor
        """
        bounding_boxes_split, containing_box_split = self.__bounding_boxes(trajectory_split, distances_split)
        return self.query_hits_partial_trajectory(
            query_type_names,
            bounding_boxes_split,
            containing_box_split,
            query_types,
            type_queries)

    # TODO Could we vectorize this?
    def query_hits_partial_trajectory(
            self,
            query_type_names: Iterable[str],
            bounding_boxes: List[BoundingBox],
            containing_box: BoundingBox,
            query_types: Iterable[QueryType],
            type_queries: Iterable[str]
    ) -> List[Dict[str, Any]]:
        """
        Query for the POIs in the containing box, then use the bounding_boxes (originally submitted) to filter away
        the POIs that fell outside of the original boxes. Possible CPU bottleneck, so it logs preocessing time.

        :param query_type_names: Query types by name
        :param bounding_boxes: Bounding boxes originally submitted
        :param containing_box: Bounding box containing all the bounding boxes
        :param query_types: QueryType objects
        :param type_queries:
        :return:
        """
        url = self.__global_query_wrapper(containing_box, type_queries)
        loggable_types = ", ".join(query_type_names)
        logger.info(f"OSM: trajectory[{len(bounding_boxes)}]: {loggable_types}: {containing_box.area_str()}")
        logger.debug(f"OSM: {url}")
        results = self.query_timed(url)
        start_time: float = time.time()
        elements = results['elements']
        bounding_box_hits = [box.contained_elements(elements) for box in bounding_boxes]
        query_typed_hits_per_box = []
        for box_hits in bounding_box_hits:
            for query_type in query_types:
                query_typed_hits_per_box.append(dict(elements=query_type.matching_elements(box_hits)))
        duration_sec: float = time.time() - start_time
        logger.info("%s elements from %s boxes -> %s processed in %sms",
                    len(elements), len(bounding_boxes), str(containing_box), int(1000 * duration_sec))
        return query_typed_hits_per_box

    @staticmethod
    def __bounding_boxes(points: List[List[float]], distances: List[int]):
        """
        Takes a list of points and distances, and returns bounding boxes for each point, with a combined boundingbox
        :param points: List of coordinates as float pairs
        :param distances: List of distances/accuracies
        :return: Bounding boxes for the points, along with a containing bounding box combining all the boxes
        """
        bounding_boxes = [bounding_box(point[0], point[1], distance) for point, distance in zip(points, distances)]
        containing_box: BoundingBox = reduce(BoundingBox.combine, bounding_boxes)
        return bounding_boxes, containing_box

    @staticmethod
    def __type_queries(element_types: List[str], query_types: Iterable[QueryType]) -> Iterable[str]:
        """
        :param element_types: Node/way/relation
        :param query_types: POI types (schools etc.)
        :return: OSM-syntax query denoting the query types (POIs to return) with their respective element types
                 (node, way, relation)
        """
        query_lists: Iterable[Iterable[str]] = \
            [query_type.to_queries(element_types) for query_type in query_types]
        osm_queries = [f"({';'.join(query_list)};);out body geom;" for query_list in query_lists]
        return osm_queries

    # TODO Not in use (?)
    @staticmethod
    def __build_typed_queries(query_type: str, element_types: List[str]) -> Iterable[str]:
        if element_types is None:
            element_types = _REQUIRED_ELEMENT_TYPES[query_type]
        query_type = _QUERY_TYPES[query_type]
        return [f"{element_type}[{query_type}]" for element_type in element_types]
