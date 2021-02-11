"""
Class file for a GPS trajectory smoother
"""
import math
import pandas as pd
import numpy as np
import os
from datetime import datetime
from corona.utils import haversine_distance, convert_seconds, duration_of_contact
from corona.analysis.default_parameters import params

class TrajectoryParser(object):
    """
    Class takes in a pandas data or numpy array frame with columns representing
    ['time', 'longitude', 'latitude','accuracy'] and performs processing
    task such as:

        - interpolation/upsampling
        - ...

    If pdf_frame is None, a empty trajectory will be returned.

    """
    def __init__(self, pd_frame, uuid, verbose = 0):
        if pd_frame is None:
            pd_frame = pd.DataFrame([], columns=['time', 'longitude', 'latitude', 'accuracy'], dtype=np.float64)

        self.pd_frame = pd_frame # we're not working with pd frames anymore after this point
        self.data = pd_frame[['time', 'longitude', 'latitude', 'accuracy']].to_numpy()
        self.uuid = uuid
        if not self._empty_():
            self.min_time = np.min(self.data[:,0])
            self.max_time = np.max(self.data[:,0])
        else:
            self.min_time, self.max_time = np.nan, np.nan
        self.n_time_stamps = self.data.shape[0]
        self.verbose = verbose # Can be used for showing debugging information

    def __str__(self):
        """ Representation function: TBD """
        print("Instance of type Trajectory(uuid = {0})".format(self.uuid))

    def __len__(self):
        """ Returns the number of data points in the trajectory """
        return len(self.data)

    def filter(self, min_time, max_time):
        """ Return a copy of the trajectory that contains only locations between min_time and max_time """
        df = self.get_pd_frame()
        df = df[df["time"]>=min_time]
        df = df[df["time"]<=max_time]
        return self.__class__(df, self.uuid, self.verbose)

    """ Getters """
    def get_min_time(self):
        """ Returns smallest time stamp for which there is data """
        return self.min_time

    def get_max_time(self):
        """ Returns largest time stamp for which there is data """
        return self.max_time

    def get_n_time_stamps(self):
        """ Returns number of available data points """
        return self.n_time_stamps

    def get_raw_data(self):
        """ Returns after data as numpy array """
        return self.data

    def get_time_stamps(self):
        """ Returns time stamps as numpy array """
        return self.data[:,0]

    def get_pd_frame(self):
        """ Returns raw pandas data frame used to create this trajectory object. """
        return self.pd_frame

    def get_mode_of_transport(self, time_stamps):
        """ Takes a list of unix time stamps and returns mode of transport from
        pandas frame. If a time_stamp is not contained in self.pd_frame['time'],
        we return the mode of the CLOSEST time stamp. If several are equally close,
        earlier timestep is used. """
        if self._empty_() or len(time_stamps) == 0:
            return ['N/A' for _ in range(len(time_stamps))]
        ts_with_available_transport = self.pd_frame['time'].to_numpy()
        ts_with_available_transport = np.repeat(np.reshape(ts_with_available_transport,
                                                (-1,1)), len(time_stamps), axis = 1) # Contains columnwise ts_with_available_transport columnwise
        # Subtract timestamp[i] from column i
        subtracted = np.abs(ts_with_available_transport - time_stamps)
        # Find columnwise minimum
        idx_closest = np.argmin(subtracted, axis = 0)
        # Write transport mode in list of strings
        transport = [aux for aux in self.pd_frame['transport'].iloc[idx_closest].values]
        return transport


    """ Callable methods """
    def inspect(self, allowed_jump, time_gap):
        """
        Method for inspecting given trajectory data. Outputs:
            - time span
            - all 'gaps' in the data where either the time gap is surpassed
            or the distance moved is more than allowed_jump
        """
        print("\n")
        self.__str__()
        if self._empty_():
            print("Data array is empty - no inspection possible")
            return
        print("Data covers period {0} - {1}         Time Delta = {2} (h,m,s)        n_timestamps = {3}".format(
            datetime.utcfromtimestamp(self.get_min_time()).strftime('%Y-%m-%d %H:%M:%S'),
            datetime.utcfromtimestamp(self.get_max_time()).strftime('%Y-%m-%d %H:%M:%S'),
            convert_seconds(self.get_max_time() - self.get_min_time()),
            self.get_n_time_stamps()))
        print("GPS Gaps:")
        time_gap_s = time_gap * 60 * 60
        gaps = self._find_sequence_startpoints(allowed_jump, time_gap_s)[1:]
        for s, gap in enumerate(gaps):
            distance = haversine_distance(self.data[gap-1,1], self.data[gap-1,2], self.data[gap,1], self.data[gap,2])
            print(" * {0}   -   {1}        Time Delta = {2} (h,m,s)       Distance {3}m       GPS accuracy {4}m".format(
                datetime.utcfromtimestamp(self.data[gap-1,0]).strftime('%Y-%m-%d %H:%M:%S'),
                datetime.utcfromtimestamp(self.data[gap,0]).strftime('%Y-%m-%d %H:%M:%S'),
                convert_seconds(self.data[gap,0] - self.data[gap-1,0]),
                round(distance), max(self.data[gap-1,3], self.data[gap,3])))

    def simple_upsampling(self, min_time, max_time, timestep, timecol = False):
        """
        comment

        Returns upsampled trajectory as numpy matrix of size
        (timesteps, 3 (lat, long, accuracy)).

        Timecol == True adds timestemps as a first column
        """
        timesteps = np.arange(min_time, max_time+1, timestep)
        table = np.zeros((len(timesteps), 3))
        if not self._empty_():
            for i in [1,2,3]:
                table[:,i - 1] = np.interp(timesteps, self.data[:,0], self.data[:,i], left = 0, right = 0)
        if timecol:
            table = np.concatenate((np.reshape(timesteps, (-1, 1)), table), axis = 1)
        return table

    def restricted_upsampling(self, min_time, max_time, timestep,
                              allowed_jump, hard_time_gap, timecol = False):
        """
        As simple_upsampling method with the difference that data is never interpolated
        for more than one hour.

        Timecol == True adds timestemps as a first column
        """
        time_stamps = np.arange(min_time, max_time+1, timestep)
        return self._restricted_upsampling(time_stamps, allowed_jump, hard_time_gap,
                                            timecol = timecol)

    def restricted_upsampling_stamps(self, time_stamps, allowed_jump, hard_time_gap,
                                   timecol = False):
        """
        As simple_upsampling method with the difference that data is never interpolated
        for more than one hour.

        Timecol == True adds timestemps as a first column
        """
        return self._restricted_upsampling(time_stamps, allowed_jump, hard_time_gap,
                                           timecol = timecol)

    """ Helpers """
    def _empty_(self):
        """ Returns true if data is empty. """
        return self.data.shape[0] == 0

    def _find_sequence_startpoints(self, allowed_jump, hard_time_gap):
        """ Returns ordered list of indices with time sequence start points. A
        time sequence satisfies that there are no two time points further than
        hard_time_gap away. Furthermore in a time gap more than soft_time_gap,
        the travelled distance must be less than allowed_jump to keep a connected
        time sequence (otherwise we add a break point)
        Note that index 0 is always contained as a start point.
        """
        time_steps = np.diff(self.data[:,0])
        sequence_startpoints = [0]
        mask = [True for i in range(self.get_n_time_stamps())]
        break_due_to_time = []
        for i in range(self.get_n_time_stamps() - 1):
            if time_steps[i] >= hard_time_gap:
                continue
            distance_jumped = haversine_distance(self.data[i,1], self.data[i,2], self.data[i+1,1], self.data[i+1,2])
            if distance_jumped > allowed_jump:
                continue
            mask[i+1] = False
        sequence_startpoints.extend([i for i, val in enumerate(mask) if (val and i != 0)])
        return sequence_startpoints

    def _restricted_upsampling(self, time_stamps, allowed_jump, hard_time_gap,
                              timecol = False):
        """
        As simple_upsampling method with the difference that data is never interpolated
        for more than one hour.

        Timecol == True adds timestemps as a first column
        """
        table = np.zeros((len(time_stamps), 3))
        if not self._empty_():
            max_interpol_s = hard_time_gap * 60 * 60
            startpoints = self._find_sequence_startpoints(allowed_jump, 2 * max_interpol_s)
            for s in range(len(startpoints)):
                start_seq = startpoints[s]
                if s < len(startpoints) - 1:
                    end_seq = startpoints[s+1]
                else:
                    end_seq = len(self.data[:,0])
                if self.verbose > 0:
                    print(" Processing {0} to {1} (Total length = {2})".format(
                        start_seq, end_seq, self.get_n_time_stamps()))
                temp_data = self.data[start_seq : end_seq, :]
                lat_temp = np.interp(time_stamps, temp_data[:,0], temp_data[:,1], left=0, right=0)
                long_temp = np.interp(time_stamps, temp_data[:,0], temp_data[:,2], left=0, right=0)
                acc_temp = np.interp(time_stamps, temp_data[:,0], temp_data[:,3], left=0, right=0)
                active_times = np.nonzero(lat_temp)[0]
                table[active_times, 0] = lat_temp[active_times]
                table[active_times, 1] = long_temp[active_times]
                table[active_times, 2] = acc_temp[active_times]
            active_times = np.nonzero(lat_temp)[0]
        if timecol:
            table = np.concatenate((np.reshape(time_stamps, (-1, 1)), table), axis = 1)
        return table


def is_inside_transport(s, inside_transport_modes=params["pois_options"]["inside_transport_modes"]):
    return s in inside_transport_modes

def is_not_in_transport(s, walking_modes=params["pois_options"]["walking_modes"]):
    return s in walking_modes

def filter_suspicious_transport_modes(is_inside, times_list, min_duration=params["pois_options"]['transport_filtration_duration']):
    """
    Isolated True/False values with small duration will be considered suspicious and smoothed (if duration small enough)
    For example [True,True,True,True,False,True,True,True] -> [True,True,True,True,True,True,True,True]
    """
    if len(is_inside) > 4:
        is_suspicious = [(is_inside[i] and (not is_inside[i+1]) and (not is_inside[i+2]) and (not is_inside[i-1]) and (not is_inside[i-2])) or ((not is_inside[i]) and is_inside[i+1] and is_inside[i+2] and is_inside[i-1] and is_inside[i+1]) for i in range(2, len(is_inside) - 2)]
        is_suspicious = [False,False] + is_suspicious + [False,False]
        suspicious_indices = [item for item,x in enumerate(is_suspicious) if x]
        for suspicious_index in suspicious_indices:
            computed_time = duration_of_contact(times_list, [suspicious_index])
            if computed_time > min_duration:
                is_suspicious[suspicious_index] = False
        new_inside = [not is_inside[i] if is_suspicious[i] else is_inside[i] for i in range(len(is_inside))]
        return new_inside
    else:
        return is_inside

def transports_preprocessing(t1, t2, timestamps_in_contact):
    """
    Input 2 trajectory objects and some timestamps of contact and get a dataframe with trajectory modes
    Input keys (pairs from): 'still', 'on_foot', 'vehicle', 'public_transport', 'N/A'
    Output keys: 'inside_transport', 'on_foot', 'uncertain'
    """
    transport_contact_1 = t1.get_mode_of_transport(timestamps_in_contact)
    transport_contact_2 = t2.get_mode_of_transport(timestamps_in_contact)
    # inside_transport: s1 and s2 are vehicle/public_transport or one is and the other is N/A
    inside_transport = [( (is_inside_transport(s1) and is_inside_transport(s2)) or ((s1=='N/A' or s2=='N/A') and (is_inside_transport(s1) or is_inside_transport(s2))) ) for s1,s2 in zip(transport_contact_1, transport_contact_2)]
    is_inside_filtered = filter_suspicious_transport_modes(inside_transport,timestamps_in_contact)
    # is_onfoot: s1 and s2 are on_foot/still or one is and the other is N/A
    is_onfoot = [( (is_not_in_transport(s1) and is_not_in_transport(s2)) or ((s1=='N/A' or s2=='N/A') and (is_not_in_transport(s1) or is_not_in_transport(s2))) ) for s1,s2 in zip(transport_contact_1, transport_contact_2)]
    is_onfoot_filtered = filter_suspicious_transport_modes(is_onfoot,timestamps_in_contact)
    # is uncertain: both are N/A or one is still/on_foot and the other is vehicle/public_transport, i.e. what is left
    is_uncertain = [not is_onfoot_filtered[i] and not is_inside_filtered[i] for i in range(len(is_onfoot_filtered))]
    return is_inside_filtered, is_onfoot_filtered, is_uncertain
