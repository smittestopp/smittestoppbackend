import json
import time
import statistics
import pandas as pd
import numpy as np
import pyodbc
import re

from collections import defaultdict
from datetime import timedelta
from contextlib import contextmanager

from corona.map.api import OverpassAPI
from corona.map.utils import get_overpass_df_from_list
from corona.config import __CONFIG__
from corona.utils import haversine_distance, sparsify_mask, Singleton, retry, timer
from corona.bt_load_helper import get_contacts, convert_frame
from corona import logger

_DEFAULT_INCLUDE_ATTRIBUTES = [
    "uuid",
    "timefrom",
    "timeto",
    "longitude",
    "latitude",
    "accuracy",
    "speed",
]

_DEFAULT_INCLUDE_ATTRIBUTES_BLUETOOTH = [
    "uuid",
    "paireddeviceid",
    "encounterstarttime",
    "duration",
    "very_close_duration",
    "close_duration"
    "relatively_close_duration"
]

_TRANSPORT_TYPES = {
    0: "still",
    1: "on_foot",
    2: "vehicle",
    3: "public_transport"
}


def connect_to_azure_database():
    """ Connects to the Azure database using the credentials storeed in
    "~/.config/corona.conf" on Linux/Mac or "AppData/Roaming" on Windows."""

    host : str =  __CONFIG__.database.host
    user : str =  __CONFIG__.database.user
    password : str =  __CONFIG__.database.password
    database : str =  __CONFIG__.database.database
    driver : str =  __CONFIG__.database.driver

    db = pyodbc.connect(
        "DRIVER=%s;SERVER=%s;PORT=1433;DATABASE=%s;UID=%s;PWD=%s" % (driver, host, database, user, password)
    )

    return db
# PATCH! Connect to azure with a token from the environment
# overrides the above definition
from ._data_patch import connect_to_azure_database

class Database(metaclass=Singleton):

    __host        : str =  __CONFIG__.database.host
    __user        : str =  __CONFIG__.database.user
    __password    : str =  __CONFIG__.database.password
    __database    : str =  __CONFIG__.database.database
    __driver      : str =  __CONFIG__.database.driver
    __port        : str = "1433"

    __connection_string : str = None

    __db : pyodbc.Connection = None

    def __init__(self) -> None:
        self.__build_connection_string()
        self.connect()

    def __is_open(self) -> bool:
        """ Checks if database connection is open."""
        try:
            cursor = self.__db.cursor()
            cursor.close()
            return True
        except:
            return False

    def __connection_is_valid(self) -> bool:
        """Checks if the current database connection is valid."""

        if not self.__is_open():
            logger.info("Database connection is closed!")
            return False

        return True

    def __build_connection_string(self) -> None:
        """Builds the database connection string"""

        connection_string = ""
        connection_string += "DRIVER=%s;" % self.__driver
        connection_string += "SERVER=%s;" % self.__host
        connection_string += "PORT=%s;" % self.__port
        connection_string += "DATABASE=%s;" % self.__database
        connection_string += "UID=%s;" % self.__user
        connection_string += "PWD=%s" % self.__password

        self.__connection_string = connection_string

    def close(self) -> None:
        """Closes the database connection."""
        self.__db.close()

    @retry(Exception)
    def connect(self) -> None:
        """Connects to the database. Will reuse connection if
           a connection is open and the connection string has not
           changed.
        """

        logger.info("Connecting to database...")

        if self.__db is not None and self.__connection_is_valid():
            logger.info("A connection is already open! Reusing old connection.")
            return

        try:
            self.__db = pyodbc.connect(self.__connection_string)
            logger.info("Database connection successful!")
        except Exception as e:
            logger.error(f"Database connection failed! | { e }")
            raise

    @retry(Exception)
    def query(self, query: str, *argv, **kwargs) -> pyodbc.Cursor:
        """ Queries the database and returns the result as a Cursor."""

        logger.info(f'Querying SQL with { query }')

        if not self.__connection_is_valid():
            logger.info("Trying to reconnect...")
            self.connect()

        cursor = self.__db.cursor()

        try:
            cursor.execute(query, *argv, **kwargs)
        except Exception as e:
            logger.error(f'Error querying SQL with { query } | { e }')
            raise

        return cursor

    @retry(pd.io.sql.DatabaseError)
    def query_pd(self, query: str, *argv, **kwargs) -> pd.DataFrame:
        """ Queries the database and returns the result as a DataFrame."""

        logger.info(f'Querying SQL with { query }')

        if not self.__connection_is_valid():
            logger.info("Trying to reconnect...")
            self.connect()

        data = pd.DataFrame()

        return pd.read_sql(query, self.__db, *argv, **kwargs)

#from profilehooks import profile
#@profile
@retry(Exception)
def load_azure_data_bluetooth(patient_uuid, timeFrom, timeTo, dt_threshold=None):
    """ Loads bluetoot data from the Azure database and returns a dictionary
    of uuids and user events. If patient_uuid is given, data frame will be sorted
    so that primary uuid/device belongs to patient.

    dt_threshold is None or number. None keeps original data. With number
    data is filter such that 2 conseq events are at least dt_threshold
    apart. NOTE: dt_threshold value is in seconds
    """
    with timer("db connect"):
        db = connect_to_azure_database()

    df = get_contacts(patient_uuid, timeFrom, timeTo, db)
    db.close()
    df = convert_frame(df)
    df = df.sort_values('encounterstarttime')
    df = df.reset_index(drop=True)

    if dt_threshold is not None:
        # NOTE: enocounterstatime column is unix timestamp in seconds
        assert dt_threshold > 0
        # Setup for recreating a valid (with correct columns) but empty
        # frame
        keys = list(df.keys())
        df = df[sparsify_mask(df['encounterstarttime'], dt_threshold)]

        if not len(df):
            print('BlueTooth time coarsening yielded empty frame')
            df = pd.DataFrame(columns=keys)
    return df

#from profilehooks import profile
#@profile
@retry(Exception)
def load_azure_data(query, outlier_threshold=100,
                    include_attributes=_DEFAULT_INCLUDE_ATTRIBUTES,
                    dt_threshold=None, dx_threshold=None):
    """ Loads data from the Azure database and returns a dictionary of
    uuids and user events.

    dt_threshold is None or number. None keeps original data. With number
    data is filter such that 2 conseq events are at least dt_threshold
    apart. NOTE: dt_threshold value is in seconds

    dx_threshold is None or number. None keeps original data. With number
    a distance threshold (in meters) in data is applied such that kepts
    consecutive events have distance > dx_threshold.
    """

    with timer("db connect"):
        db = connect_to_azure_database()

    db_func = re.search('(FROM|from) (\w*)', query).group(2)
    with timer(f"db query {db_func}"):
        df = pd.read_sql(
            query,
            con=db,
            parse_dates=[ "timeto", "timefrom" ],
        )
    db.close()

    df = df.sort_values(by='timefrom')
    df = df.reset_index(drop=True)

    # Time coarse
    if dt_threshold is not None:
        # NOTE: here we get timestamps and timedelta as their diff so convert
        # threshold for comparison
        assert dt_threshold > 0
        dt_threshold = timedelta(days=0, seconds=dt_threshold)
        # Setup for recreating a valid (with correct columns) but empty
        # frame
        keys = list(df.keys())
        df = df[sparsify_mask(df['timefrom'], dt_threshold)]

        if not len(df):
            print('GPS time coarsening yielded empty frame')
            df = pd.DataFrame(columns=keys)

    # Space coarsen
    if dx_threshold is not None:
        assert dx_threshold > 0
        position = np.c_[df['latitude'].to_numpy(), df['longitude'].to_numpy()]
        # Inside filter we want to get distance between rows x, y
        distance = lambda x, y: haversine_distance(x[0], x[1], y[0], y[1])

        keys = list(df.keys())
        df = df[sparsify_mask(position, threshold=dx_threshold, distance=distance)]

        if not len(df):
            print('GPS distance coarsening yielded empty frame')
            df = pd.DataFrame(columns=keys)

    df = df.loc[ :, include_attributes ]

    data_dict = { }

    for uuid in df.uuid.unique():
        user_data = df.loc[ df[ "uuid" ] == uuid ]
        data_dict[ uuid.lower() ] = process_data_frame(user_data, outlier_threshold)

    return data_dict


def add_distance_to_df(df):
    """ Adds distance as a column to the supplied pd.DataFrame"""
    lats1 = np.array(df["latitude"].iloc[ : -1 ].values, dtype=np.float64)
    lats2 = np.array(df["latitude"].iloc[ 1 : ].values, dtype=np.float64)
    lons1 = np.array(df["longitude"].iloc[ : -1 ].values, dtype=np.float64)
    lons2 = np.array(df["longitude"].iloc[ 1 : ].values, dtype=np.float64)
    distance = [ 0 ]
    for lat1, lat2, lon1, lon2 in zip(lats1, lats2, lons1, lons2):
        distance.append(
            haversine_distance(
                lat1=lat1,
                lon1=lon1,
                lat2=lat2,
                lon2=lon2
            )
        )
    df.insert(len(df.columns), "distance", distance)

def add_speed_to_df(df):
    """ Adds speed as a column to the supplied pd.DataFrame"""
    time1 = df[ "timefrom" ].iloc[ : -1 ].values
    time2 = df[ "timeto" ].iloc[ 1 : ].values
    distances = df[ "distance" ].iloc[ 1 : ].values
    speed = distances / (time2 - time1)
    speed = np.insert(speed, 0, 0, axis=0)
    df.insert (len(df.columns), "speed", speed)

def mode_of_transport_from_speed(speed_kph):
    """ A mapping of kph to the most likely transport mode """
    if speed_kph < 1:   return _TRANSPORT_TYPES[ 0 ]
    if speed_kph < 14:   return _TRANSPORT_TYPES[ 1 ]
    return _TRANSPORT_TYPES[ 2 ]

def filter_outlier_mode_of_transport(transport, window_size):
    """ Filters out transpoort mode anomalies """
    left_pad = (window_size - 1) // 2
    right_pad = left_pad if window_size % 2 != 0 else left_pad + 1
    transport = ([ transport[ 0 ] ] * left_pad) + transport + ([ transport[ -1 ] ] * right_pad)
    temp = [ ]
    for index in range(len(transport) - (window_size - 1)):
        try:
            window = transport[ index : index + window_size ]
            most_frequent = statistics.mode(window)
        except statistics.StatisticsError:
            most_frequent = transport[index + (window_size // 2) ]
        temp.append(most_frequent)
    return temp

def most_frequent_mot_within_time_interval(df, time_interval=60):

    end_time = df.iloc[ -1 ].timeto
    current_start = df.iloc[ 0 ].timefrom
    current_end = current_start + time_interval
    while current_end <= end_time:
        interval_selection = df[ (df.timefrom <= current_start) & (df.timefrom <= current_end) ]
        most_common = interval_selection[ "transport" ].mode().iloc[ 0 ]
        df.loc[ interval_selection.index, "transport" ] = most_common
        if interval_selection.index[ -1 ]  + 1 >= len(df):
            break
        current_start = df.iloc[ interval_selection.index[ -1 ]  + 1 ].timefrom
        current_end = current_start + time_interval

def mot_helper(row):
    return mode_of_transport_from_speed(row.speed * 3.6)

def add_simple_mode_of_transport_to_df(df):
    """ Adds transport mode as a column to the supplied pd.DataFrame"""
    if not df.empty:
        df[ "transport" ] = df.apply(mot_helper, axis=1)

def add_public_transport_to_df(df, stop_points, search_radius):

    api = OverpassAPI()

    for start, end in zip(stop_points[ : -1 ], stop_points[ 1 : ]):

        transport_stops = get_overpass_df_from_list(
            api.query_point(
                df.iloc[start[1]].latitude,
                df.iloc[start[1]].longitude,
                search_radius,
                [ "public_transport" ]
            )
        )

        if transport_stops is not None:
            df.transport.loc[ start[1] : end[0] ] = _TRANSPORT_TYPES[ 3 ]

def merge_neighboring_stop_points(stop_points, gap_allowence=0):

    index = 0

    while index > len(stop_points) - 1:

        if stop_points[index][1] + 1 + gap_allowence >= stop_points[index + 1][0]:
            stop_points[ index + 1 ] = (
                min(stop_points[ index ][ 0 ], stop_points[ index + 1 ][ 0 ]),
                max(stop_points[ index ][ 1 ], stop_points[ index + 1 ][ 1 ])
            )
            stop_points.pop(index)

    return stop_points


def add_mode_of_transport_to_df(df, stop_duration_threshold=30,
    distance_threshold=30, pt_search_radius=10):
    """ Adds transport mode as a column to the supplied pd.DataFrame"""

    transport = [ mode_of_transport_from_speed(0) ]

    center_point = df.iloc[ 0 ]
    last_point = df.iloc[ 0 ]

    potential_still_points = [ ]
    potential_move_points = [ ]

    stop_points = [ ]
    stop_duration = 0

    for index, current_point in df.iloc[ 1 : ].iterrows():

        time_since_last_point = current_point.timefrom - last_point.timeto

        distance_from_center = haversine_distance(
            lat1=center_point.latitude,
            lon1=center_point.longitude,
            lat2=current_point.latitude,
            lon2=current_point.longitude
        )

        predicted = mode_of_transport_from_speed(current_point.speed  * 3.6)
        potential_move_points.append(predicted)

        if distance_from_center < distance_threshold:
            potential_still_points.append(_TRANSPORT_TYPES[ 0 ])
            stop_duration += time_since_last_point

        else:
            if stop_duration > stop_duration_threshold:
                stop_points.append((index - len(potential_still_points), index))
                potential_still_points.append(_TRANSPORT_TYPES[ 0 ])
                transport.extend(potential_still_points)
            else:
                transport.extend(potential_move_points)

            potential_move_points = [ ]
            potential_still_points = [ ]
            center_point = current_point
            stop_duration = 0

        last_point = current_point

    transport.extend(potential_still_points)

    df.insert(len(df.columns), "transport", transport)

def fix_bluetooth_patient(df, uuid):
    """ Assumes df is a given pd frame with bluetooth events where uuid is always
    involved. Sorts frame such that uuid is always primary device stored
    in df['uuid']. """
    B = df.copy(deep=True)
    B['uuid'] = uuid
    B.loc[df['paireddeviceid'] == uuid,'paireddeviceid'] = df.loc[df['paireddeviceid'] == uuid,'uuid']
    return B

def convert_datetime_to_unix_time(df, cols):
    """ Converts all columns specified by cols in the given pandas dataframe
    from datetime to unix time stamp. If df[col] for col in cols is not
    in datetime, nothing is done to the column and a warning is printed. """
    datetime_cols = df.select_dtypes('datetime64')
    for col in cols:
        if col not in datetime_cols:
            print("convert_datetime_to_unix_time: Column {0} is not a datetime column and is skipped".format(col))
            continue
        df[cols] = (df[cols] - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s")
    return df

def fix_inconsistent_datetimes(df):
    """ Fixes issues with inconsistent time formats pulled from the database/files"""
    # First select and convert all rows where the time is not stored as a UNIX timestamp
    A = df[df["timeto"].apply(type)!=int]
    B = A.copy(deep=True)
    # Convert time columns to DateTime objects
    B["timefrom"] = pd.to_datetime(B["timefrom"])
    B["timeto"] = pd.to_datetime(B["timeto"])
    # Convert time columns to Unix timestamps
    B["timefrom"] = (B.timefrom - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s")
    B["timeto"] = (B.timeto - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s")
    # Now select all rows that are already in UNIX timestamp format
    C = df[df["timeto"].apply(type)==int]
    C = C.copy(deep=True)
    C['timeto'] = C['timeto'].astype(np.int64)
    C['timefrom'] = C['timefrom'].astype(np.int64)
    # return both
    return pd.concat([B, C])

def fix_inconsistent_from_to_times(df):
    """ Fixes issue regarding time columns being swapped"""
    A = df[ (df[ "timeto" ] - df[ "timefrom" ]) < 0 ]
    A = A.rename(columns={ "timefrom": "timeto", "timeto": "timefrom" })
    B = df[ (df[ "timeto" ] - df[ "timefrom" ]) >= 0 ]
    return pd.concat([ A, B ], sort=False)

def fix_os_specific_accuracy_errors(df):
    """ Removes rows from given data frame where 'accuracy' column is less than 0
    and sets values which equal 0 to 100. """
    A = df[ df['accuracy'] > 0 ]
    A[ A['accuracy'] == 0 ].accuracy = 100
    return A

def remove_outliers(df, outlier_threshold):
    """ Removes rows from given data frame where 'accuracy' column is above
    given threshold. """
    return df[ df['accuracy'] <= outlier_threshold ]

def combine_time_columns(df):
    """ Combines the timefrom and timeto columns to a single time column """
    A = df.loc[ :, df.columns != "timeto" ]
    B = df.loc[ :, df.columns != "timefrom" ]
    A = A.rename(columns={"timefrom": "time"})
    B = B.rename(columns={"timeto": "time"})
    C = pd.concat([A, B])
    C = C.drop_duplicates(subset=["time"], keep="first")
    return C

def limit_time_range(df, time_from, time_to):
    """ Limits data to to between the given time range """
    df_limited = df[df["timefrom"] > time_from][df["timeto"] < time_to]
    if len(df_limited) > 0:
      print("Number of rows before day filter: ", len(df), " after: ", len(df_limited))
    return df_limited

def process_data_frame(df, outlier_threshold, time_from = None, time_to = None):
    """
    Takes a dictionary with (uuid, pd_frame) pairs and processes
    the pd_frame for each user. Processing includes selection of desired columns,
    and reinterpreting timeto and timefrom as time. Output data frames have 4 columns
    (time, latitude, longitude, accuracy). """
    df = fix_os_specific_accuracy_errors(df)
    df = remove_outliers(df, outlier_threshold)
    df = fix_inconsistent_datetimes(df)
    df = fix_inconsistent_from_to_times(df)
    if time_from is not None and time_to is not None:
        df = limit_time_range(df, time_from, time_to)
    # Select relevant rows
    df = df.reset_index(drop=True)
    add_simple_mode_of_transport_to_df(df)
    df = combine_time_columns(df)
    df = df.sort_values("time")
    # Resets the pd indices, can be useful sometimes
    df = df.reset_index(drop=True)
    return df


@retry(Exception)
def load_device_info(uuids):
    '''Return a dictionary of uuid -> List of device info tuples'''
    if not __CONFIG__.features.device_info:
        logger.info("Loading device info is disabled in config.")
        return defaultdict(list)

    logger.info("Loading device info")

    if isinstance(uuids, str):
        uuids = (uuids, )

    uuids = set(uuids)

    device_info = defaultdict(list)

    query_template = "SELECT * FROM getDeviceInformationSingle('%s')"

    with timer("db connect"):
        db = connect_to_azure_database()

    for uuid in uuids:
        query = query_template % uuid
        with timer("db query getDeviceInformationSingle"):
            frame = pd.read_sql_query(query, con=db)

        # NOTE: it seems there are some different conventions for naming
        # e.g. ios10.1 and ios101 are (probably) the same thing and we might
        # want to merge these
        frame is not None and device_info[uuid].extend(zip(frame['platform'], frame['model'], frame['appversion']))

    db.close()
    logger.info("Finished loading device info")

    return device_info
