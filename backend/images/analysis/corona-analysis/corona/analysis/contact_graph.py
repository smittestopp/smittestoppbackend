import networkx as nx
import math
import datetime

from tqdm import tqdm
import pandas as pd

from corona import logger
from corona.data import load_azure_data, load_azure_data_bluetooth, load_device_info
from corona.analysis.trajectory import TrajectoryParser
from corona.analysis.contact_list import ContactList
from corona.analysis.gps_contact import get_gps_contacts_from_trajectories
from corona.analysis.bt_contact import BluetoothContactDetailsIterator, BluetoothContact
from corona.analysis.intersection_functions import convolution
from corona.utils import haversine_distance

class BaseContactGraph(object):
    def __init__(self, query_uuids, params):
        """
        Constructs a contact graph for a list of query uuids.

        :params: query_uuids: A list of uuids to query
        :params: params: A parameter dictionary used for the graph computations
        """

        logger.info("Building contact graph")
        self.query_uuids = query_uuids
        self.params = params

        self._G = nx.Graph()
        self._compute_graph_nodes()
        self._compute_graph_edges()
        # Collect device info for all participant uuids
        self.node_device_info = load_device_info(list(self._G.nodes))

        logger.info("Finished building contact graph")


    def contacts_with(self, uuid):
        """ Returns a list with all contacts with a given uuid.

        :param uuid: The uuid of interest
        :return: A list of ContactList objects

        """
        if uuid in self.uuids:
            contacts = [(uuid1, uuid2, edge["contact_list"]) for uuid1, uuid2, edge in self._G.edges(uuid, data=True)]
            return ContactGraphResult(uuid, contacts)
        else:
            logger.info(f"{self.__class__.__name__}: No contacts for {uuid} - returning empty list")
            return ContactGraphResult(uuid, [])


    def _add_contacts(self, uuid1, uuid2, contacts):
        """ Adds contact information to graph. """

        # We should never overwrite an existing edge
        if self._G.get_edge_data(uuid1, uuid2) is not None:
            raise("Contact already in graph")

        if len(contacts)>0:
            self._G.add_edge(uuid1, uuid2, contact_list=contacts)


    def __str__(self, verbose=True):
        print(f"Number of nodes {len(self._G.nodes())}")
        print(f"Number of edges {len(self._G.edges())}")
        if verbose:
            print(self._G.nodes(data=True))
            print(self._G.edges())



class BTContactGraph(BaseContactGraph):

    def _compute_graph_nodes(self):
        """ Load uuids and add as graph nodes """
        self._load_bt_data()
        if len(self._bt_data) == 0:
            self.uuids = set()
        else:
            self.uuids = set(self._bt_data['uuid']) | set(self._bt_data['paireddeviceid'])
        self._G.add_nodes_from(self.uuids)


    def _compute_graph_edges(self):
        """
        Computes contacts and adds as edges to graph
        """

        glue_below_duration = self.params['bt_glue_below_duration']
        min_duration = self.params['bt_min_duration']
        timeFrom = self.params['timeFrom']
        timeTo = self.params['timeTo']
        outlier_threshold = self.params['bt_outlier_threshold']
        bt_data = self._bt_data

        logger.info("Building Bluetooth contact graph edges")

        for uuid1 in self.query_uuids:
            trajectory_uuid1 = self._load_trajectory(uuid1)

            for uuid2 in tqdm(self.uuids):
                if uuid1 == uuid2:
                    continue

                # Extract relevant part of pandas frame
                bt_data_local = bt_data.loc[((bt_data['uuid'] == uuid1) &
                                            (bt_data['paireddeviceid'] == uuid2)) |
                                            ((bt_data['paireddeviceid'] == uuid1) &
                                            (bt_data['uuid'] == uuid2))]
                if len(bt_data_local) == 0:
                    # No contacts
                    continue

                trajectories = {uuid1: trajectory_uuid1,
                                uuid2: self._load_trajectory(uuid2)}

                # Construct contact list
                t1 = trajectories[uuid1]
                t2 = trajectories[uuid2]
                bt_iterator = BluetoothContactDetailsIterator(bt_data_local, glue_below_duration)
                contacts = ContactList([BluetoothContact(t1, t2, contact_details) for contact_details in bt_iterator])
                contacts = contacts.filter(min_duration=min_duration)

                self._add_contacts(uuid1, uuid2, contacts)

        logger.info("Building Bluetooth contact graph edges")


    def _load_bt_data(self):
        # Load data from database
        assert(len(self.query_uuids)==1)  # FIXME: support multiple query uuids
        query_uuid = self.query_uuids[0]
        timeFrom = self.params['timeFrom']
        timeTo = self.params['timeTo']
        dt_threshold = self.params['bt_dt_threshold']

        logger.info(f"BTContactGraph: Loading BT contacts from SQL server for uuid {query_uuid}.")
        self._bt_data = load_azure_data_bluetooth(query_uuid, timeFrom, timeTo, dt_threshold=dt_threshold)
        logger.info("BTContactGraph: Finished loading BT contacts from SQL server")


    def _load_trajectory(self, uuid):
        """ Loads GPS trajectory for a uuid for the analysis period """

        # Get the trajectory for all uuids
        params = self.params
        dt_threshold = params['gps_dt_threshold']
        dx_threshold = params['gps_dx_threshold']

        query = f"SELECT * FROM getTrajectorySpeed('{uuid}','{params['timeFrom']}','{params['timeTo']}')"
        logger.info(f"BTContactGraph: Calling getTrajectorySpeed() for BT contact.")
        df = load_azure_data(query, params['outlier_threshold'], dt_threshold=dt_threshold, dx_threshold=dx_threshold).get(uuid, None)
        logger.info(f"BTContactGraph: Parsing trajectory for BT contact")
        trajectory = TrajectoryParser(pd_frame=df,
                                      uuid=uuid,
                                      verbose=0)
        logger.info(f"Finished getTrajectorySpeed() and parsing trajectory for BT contact.")
        return trajectory


class GPSContactGraph(BaseContactGraph):
    """ Class input is a list of trajectories in the form of a
        uuidd -> (timestamp, lat, lon, accuracyt) dictionary.
        From that, it creates a graph containing which uuids
        have been in contact with each other.
    """

    def _compute_graph_nodes(self):
        # Query trajectories
        self._trajectories = self._get_trajectories()

        # Add uuids as graph nodes
        self.uuids = set(self._trajectories.keys())
        self._G.add_nodes_from(self.uuids)


    def _compute_graph_edges(self, dist_function=convolution):
        """ Constructs the edges of the graph by computing the contacts
        of each trajectory pair. The distance function is user-specific.
        """

        dist_func_options=self.params['filter_options']
        allowed_jump=self.params['allowed_jump']
        hard_time_gap=self.params['max_interpol_in_h']
        glue_below_duration=self.params['glue_below_duration']
        min_duration=self.params['min_duration']

        logger.info("Building GPS contact graph edges")
        # Loop over trajectory pairs
        for i, uuid1 in enumerate(self.query_uuids):
            if uuid1 in self._trajectories.keys():
                t1 = self._trajectories[uuid1]
                # self._G.add_nodes(uuid1)
                for uuid2 in tqdm(self.uuids):
                    if uuid2 == uuid1:
                        # Contact with themselves is not relevant
                        continue
                    # Find contact and add to graph
                    t2 = self._trajectories[uuid2]
                    contacts = get_gps_contacts_from_trajectories(t1, t2, allowed_jump, hard_time_gap,
                                                              glue_below_duration, dist_function, dist_func_options)
                    contacts = contacts.filter(min_duration=min_duration)

                    if len(contacts)>0:
                        self._add_contacts(uuid1, uuid2, contacts)
            else:
                logger.info("No trajectory corresponds to that uuid. \n")

        logger.info("Finished building GPS contact graph edges")

    def _get_trajectories(self):
        assert(len(self.query_uuids)==1)  # FIXME: support multiple query uuids
        query_uuid = self.query_uuids[0]
        params = self.params
        # Load data from database

        dt_threshold = params['gps_dt_threshold']
        dx_threshold = params['gps_dx_threshold']

        # Now get the trajectory of the patient
        query = f"SELECT * FROM getTrajectorySpeed('{query_uuid}','{params['timeFrom']}','{params['timeTo']}')"
        logger.info(f"GPSContactGraph: Calling getTrajectorySpeed() for GPS contact")
        t_patient = load_azure_data(query, params['outlier_threshold'], dt_threshold=dt_threshold, dx_threshold=dx_threshold).get(query_uuid, [])
        logger.info("GPSContactGraph: getTrajectorySpeed() for GPS contact finished")
        minimum_duration = 60
        maximum_bb_diameter1 = 800
        maximum_bb_duration1 = 3*60
        maximum_bb_diameter2 = 200
        t_split = GPSContactGraph._bounding_boxes_greedy_(t_patient, minimum_duration,
                                                          maximum_bb_diameter1, maximum_bb_duration1, maximum_bb_diameter2)
        logger.info(f"GPSContactGraph: Split trajectory into {len(t_split)} segments")

        # Get other trajectories using bounding box method
        logger.info(f"GPSContactGraph: Calling get other trajectories (using bounding boxes) for GPS contacts")
        t = {}
        temp_trajectories = []
        for t_piece in t_split:
            timeFrom = datetime.datetime.utcfromtimestamp(t_piece['time'].min()).strftime('%Y-%m-%d %H:%M:%S')
            timeTo = datetime.datetime.utcfromtimestamp(t_piece['time'].max()).strftime('%Y-%m-%d %H:%M:%S')
            logger.info("GPSContactGraph: Dealing with time window: {0} - {1}".format(timeFrom, timeTo))
            lat_min = t_piece['latitude'].min()
            lat_max = t_piece['latitude'].max()
            long_min = t_piece['longitude'].min()
            long_max = t_piece['longitude'].max()
            query = f"SELECT * FROM getWithinBB ({long_min}, {lat_min},{long_max},{lat_max},'{timeFrom}','{timeTo}') ORDER BY 1,2 ASC"
            # Appends dictionary of format {uuid : pd_frame} to the list
            temp_trajectories.append(load_azure_data(query, params['outlier_threshold'], dt_threshold=dt_threshold, dx_threshold=dx_threshold))

        # Combine data frames of temporary trajectories
        for temp_trajectories in temp_trajectories:
            for key in temp_trajectories.keys():
                if key in t.keys():
                    # Concatanate pd frame
                    t[key] = pd.concat([t[key], temp_trajectories[key]])
                else:
                    t[key] = temp_trajectories[key]

        # Finally rebase indexes of pandas frames (these are not consistent now)
        for key in t.keys():
            t[key] = t[key].reset_index()
        logger.info(f"GPSContactGraph: Calling get other trajectories (using bounding boxes) for GPS contacts finished")
        logger.info(f"GPSContactGraph: Found GPS contacts with {len(t)} people.")

        logger.info("GPSContactGraph: Parsing trajectories of GPS contacts")
        trajectories = {}
        for uuid, df in t.items():
            trajectories[uuid] = TrajectoryParser(pd_frame=df,
                                                uuid=uuid,
                                                verbose=0)
        return trajectories

    @staticmethod
    def _bounding_boxes_divideAndConquer_(pd_trajectory, diam_max, trajectories = []):
        """ Takes pandas data frame of trajectory data and splits it so that each
        frame contains consequentive data where location is contained within
        a bounding box of diam_max size. Divide and conquer approach
        :params pd_trajectory: pandas frame with trajectory data
        :params diam_max:  float, maximum diameter of resulting bounding box
        """
        if GPSContactGraph._diam_(pd_trajectory) < diam_max:
            trajectories.append(pd_trajectory)
            return trajectories
        else:
            split_idx = math.ceil(0.5 * len(pd_trajectory))
            GPSContactGraph._bounding_boxes_(pd_trajectory.iloc[:split_idx, :], diam_max, trajectories)
            GPSContactGraph._bounding_boxes_(pd_trajectory.iloc[split_idx:, :], diam_max, trajectories)
            return trajectories

    @staticmethod
    def _bounding_boxes_greedy_(pd_trajectory, duration_min, diam_max1, duration_max1, diam_max2):
        """ Takes pandas data frame of trajectory data and splits it so that each
        frame contains consequentive data where location is contained within
        a bounding box. Greedy approach is used where a new bounding box is created if the a trajectory point
        does not satisfy any of the bounding box constraints specified by the parameters.
        :params pd_trajectory: pandas frame with trajectory data
        :params duration_min:  float, skip trajectories whose duration is below this value
        :params diam_max1:  float, maximum diameter of first resulting bounding box
        :params duration_max1:  float, maximum duration of first resulting bounding box
        :params diam_max2:  float, maximum diameter of second resulting bounding box
        """
        trajectories = []

        if len(pd_trajectory) == 0:
            return trajectories

        start_idx = 0 # start of current segment
        time_min = pd_trajectory.iloc[0]['time']
        time_max = time_min
        lat_min = pd_trajectory.iloc[0]['latitude']
        lat_max = lat_min
        long_min = pd_trajectory.iloc[0]['longitude']
        long_max = long_min
        idx = 1
        while idx < len(pd_trajectory):
            time, latitude, longitude = pd_trajectory.iloc[idx, :].time, pd_trajectory.iloc[idx, :].latitude, pd_trajectory.iloc[idx, :].longitude
            time_min = min(time_min, time)
            time_max = max(time_max, time)
            lat_min = min(lat_min, latitude)
            lat_max = max(lat_max, latitude)
            long_min = min(long_min, longitude)
            long_max = max(long_max, longitude)
            if ((haversine_distance(lat_min, long_min, lat_max, long_max) > diam_max1 and time_max-time_min <= duration_max1) or
                (haversine_distance(lat_min, long_min, lat_max, long_max) > diam_max2 and time_max-time_min > duration_max1)):
                # segment found

                # Skip segment if duration is too short
                if time_max-time_min < duration_min:
                    logger.warning(f"Skipping trajectory segment due to short duration {time_max-time_min}")
                else:
                    trajectories.append(pd_trajectory.iloc[start_idx:idx, :])

                start_idx = idx
                time_min, time_max = time, time
                lat_min, lat_max = latitude, latitude
                long_min, long_max = longitude, longitude
            idx += 1
        if start_idx < len(pd_trajectory) - 1:
            trajectories.append(pd_trajectory.iloc[start_idx:, :])
        return trajectories


    @staticmethod
    def _diam_(pd_trajectory):
        """ Computes the diameter of a trajectory """
        lat_min = pd_trajectory['latitude'].min()
        lat_max = pd_trajectory['latitude'].max()
        long_min = pd_trajectory['longitude'].min()
        long_max = pd_trajectory['longitude'].max()
        return haversine_distance(lat_min, long_min, lat_max, long_max)


class ContactGraphResult(object):
    def __init__(self, patient_uuid, contacts):
        self.patient_uuid = patient_uuid

        self.contacts = {}
        for uuid1, uuid2, contact_list in contacts:
            if uuid2==self.patient_uuid:
                uuid1, uuid2 = uuid2, uuid1
            assert uuid1==patient_uuid

            self.contacts[(uuid1, uuid2)] = contact_list

    def infected_uuids(self):
        """ Returns a list of all infected uuids """
        return self.contacts.keys()

    def contacts_for_infected_uuid(self, uuid):
        """ Returns the contact list of an infected uuid """
        return self.contacts[uuid]

    def __add__(self, other):
        """ Combines two contact graph results. Can be used for instance to
            combine the results of a BT and GPS result. """

        assert self.patient_uuid == other.patient_uuid

        new_result = ContactGraphResult(self.patient_uuid, [])

        new_contacts = self.contacts.copy()
        for uuids, contact_list in other.contacts.items():
            if uuids in new_contacts:
                new_contacts[uuids] += contact_list
            else:
                new_contacts[uuids] = contact_list

        new_result.contacts = new_contacts
        return new_result
