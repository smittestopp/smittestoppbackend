import numpy as np
import pandas as pd
import datetime
import weighted # library wquantiles
import pandas as pd

from corona.utils import union_of_time_stamps, convert_seconds
from corona.analysis.trajectory import TrajectoryParser
from corona.analysis.contact import BaseContact
from corona.analysis.contact_list import ContactList
from corona import logger
from corona.analysis.pois import POI

class GPSContact(BaseContact):
    """ A class to store details about a contact """

    def __init__(self, t1, t2, contact_details):
        BaseContact.__init__(self, t1, t2, contact_details)

        # Filter the trajectories so that they only contain the contact time +- slacktime
        slacktime = 30*60

        self.t1 = t1.filter(self.starttime()-slacktime, self.endtime()+slacktime)
        self.t2 = t2.filter(self.starttime()-slacktime, self.endtime()+slacktime)

        if len(self.cd['contact_timestamps']) == 0:
            raise RuntimeError("Got a GPSContact with zero information - something is wrong: {0}".format(self.__str__()))
        self._init_transport_mode()
        self.contact_pois = POI(self.t1, self.t2, self.cd, self.duration(), self.duration()) # the second is duration with GPS info

    def contact_type(self):
        """ Returns contact type 'gps' """
        return 'gps'

    def starttime(self):
        """ Returns unix time stamp of start time """
        return min(self.cd['contact_timestamps'])

    def endtime(self):
        """ Returns unix time stamp of start time """
        return max(self.cd['contact_timestamps'])

    def timestamps_in_contact(self):
        """ Returns ordered array of unix time stamps where we recorded a contact """
        return self.cd['contact_timestamps']

    def average_distance(self):
        """ Returns average distance in meters (uses trapezoidal rule for integration).
        Return value: float """
        t = self.timestamps_in_contact()
        return np.trapz(self.cd['dists'], t)/float(self.duration())

    def median_distance(self):
        """ Returns median distance in metres (a bit more robust towards outliers) """
        t = self.timestamps_in_contact()
        # Handle the case there is no or only one GPS point
        if len(t) == 0:
            # If no GPS points are given, all we can do is to return an unrealistic distance value
            logger.error("Requesting median distance from an empty trajectory - returning unphysical value 1e6")
            return 1e6
        if len(t) == 1:
            # For a single GPS point, the median is the distance at that point
            logger.warning("Requesting median distance from a trajectory with a single point")
            return self.cd['dists'][0]

        weights = np.array([t[i] - t[i-1] for i in range(1,len(t))])
        weights /= sum(weights)
        # because len(self.cd['dists']) = len(weights) + 1, I do this transformation
        dists = [(self.cd['dists'][i] + self.cd['dists'][i-1])/2 for i in range(1,len(t))]
        df = pd.DataFrame({'dists' : dists, 'w' : weights})
        return weighted.median(df['dists'], df['w'])


    def average_accuracy(self):
        """ Returns average accuracy in meters (uses trapezoidal rule for integration).
        Return value: float """
        t = self.timestamps_in_contact()
        return np.trapz(np.mean(self.cd['accuracy'], axis = 1), t)/float(self.duration())

    def duration(self):
        """ Returns contact duration in seconds """
        return self.endtime() - self.starttime()

    def risk_score(self):
        """ Returns the risk value of the contact in minutes/meters**2 """
        return GPSContact._compute_risk_function(self.cd['dists'], self.cd['contact_timestamps'])/60.

    def risk_category_thresholds(self):
        """ Returns thresholds for risk categories 'high', 'medium', 'low' and 'no' """
        return [4.0, 2.5, 0.01]

    def bar_plot(self, ax):
        """ Adds a plot t -> distance to the given handle """
        """ Adds a plot t -> distance to the given handle """
        datetimes = [datetime.datetime.utcfromtimestamp(val) for val in self.timestamps_in_contact()]
        ax.plot(datetimes, self.cd['dists'], 'r', linewidth=4, label = 'GPS ')
        ax.plot(datetimes, self.cd['dists_min'], 'r', alpha=0.5, linewidth=4, label = 'GPS minimum')
        ax.plot(datetimes, self.cd['dists_max'], 'r', alpha=0.5, linewidth=4, label = 'GPS maximum')

        # logger.info(f'Adding GPS from {min(datetimes)} - {max(datetimes)}')

        return ax

    def split_contact(self, switching_time):
        """
        Splits the GPSContact at the given switching point.
        :param switching_time: A datetime.datetime object (UTC time) at which point the contact is supposed
        to be split into two parts
        :returns: tuple of GPSContacts
        """
        c_times = self.timestamps_in_contact()
        # Convert switchting time to unix time stamp (ASSUMES UTC time)
        switching_time_stamp = datetime.datetime.timestamp(switching_time)
        if switching_time_stamp <= self.starttime() or switching_time_stamp >= self.endtime():
            raise RuntimeError("GPSContact.split_contact() tries to split at time {0} outside of contact time {1} - {2}".format(
                switching_time_stamp, self.starttime(), self.endtime()))
        c1_t1 = TrajectoryParser(self.t1.get_pd_frame().loc[self.t1.get_pd_frame()['time'] < switching_time_stamp], self.t1.uuid)
        c1_t2 = TrajectoryParser(self.t2.get_pd_frame().loc[self.t2.get_pd_frame()['time'] < switching_time_stamp], self.t2.uuid)
        c2_t1 = TrajectoryParser(self.t1.get_pd_frame().loc[self.t1.get_pd_frame()['time'] >= switching_time_stamp], self.t1.uuid)
        c2_t2 = TrajectoryParser(self.t2.get_pd_frame().loc[self.t2.get_pd_frame()['time'] >= switching_time_stamp], self.t2.uuid)

        switching_point = np.searchsorted(c_times, switching_time_stamp)  # Finds the index where the gps contact information should be splitted
        contact_details_1 = {item: self.cd[item][:switching_point] for item in self.cd}
        contact_details_2 = {item: self.cd[item][switching_point:] for item in self.cd}
        c1 = GPSContact(c1_t1, c1_t2, contact_details_1)
        c2 = GPSContact(c2_t1, c2_t2, contact_details_2)
        return c1, c2

    """ Helpers """
    @staticmethod
    def _compute_risk_function(distances, times):
        """
        Computes risk function with parameters specified in function get_risk_function_parameters()
        for contact of given length and distance
        NOTE THAT if times = self.times[self.cd['timesteps_in_contact']] and self.cd['timesteps_in_contact'] has non-consecutive elements (indices)
          (!!)   then we assumed that the contact was continuously going on at same distance between the two timestamps taken at non-consecutive indices.
        """
        assert len(distances) == len(times)
        integral = 0
        threshold_min = 1 # so 1 metre, to deal with when distances[ii] = 0, e.g. missing values?
        for ii in range(1,len(distances)):
            integral +=(times[ii] - times[ii-1])* ((1/max(threshold_min,distances[ii-1]))**2 + (1/max(threshold_min,distances[ii]))**2 ) / 2
        return integral


    def __str__(self):
        s =  f" * Type: GPS\n"
        s += f" * Time: {self.time_from()} -- {self.time_to()} (UTC)\n"
        s += f" * Duration: {convert_seconds(self.duration())}\n"
        s += f" * Start location: {self.trajectory()[0][:3]}\n"
        s += f" * Transport modes: {set(self.transport_modes())}\n"
        s += f" * POI: {self.pois()}\n"
        s += f" * Risk score: {self.risk_score()}\n"
        return s


def find_consecutive_timestamp_indices(timestamps, timesteps_in_contact, glue_below_duration):
    """ Find consecutive timesteps_in_contact in list. Note: this function returns its indices, not the values themselves.
    Example: [10, 13, 14, 16, 17, 18] -> [[0], [1, 2], [3, 4, 5]]
    """
    if len(timesteps_in_contact) == 0:
        return []
    index_map = []
    seq = []
    for i, idx in enumerate(timesteps_in_contact):
        if len(seq) == 0:
            # Starting a new sequence
            seq.append(i)
        elif idx - timesteps_in_contact[i - 1] == 1:
            # Consecutive sequence case 1
            seq.append(i)
        elif timestamps[idx] - timestamps[timesteps_in_contact[i - 1]] <= glue_below_duration:
            # Consecutive sequence case 2
            seq.append(i)
        else:
            # End sequence
            index_map.append(seq)
            seq = [i]
    index_map.append(seq)
    return index_map



class GPSContactDetailsIterator(object):
    """ Takes output of intersection functions with all contacts
    and splits them into iterator with single outputs """

    def __init__(self, contact_details, times, glue_below_duration):
        self.cd = contact_details
        # FIXME: Will this still work of timesteps_in_contact is not sorted?
        self.consecutive_timestamp_indices = find_consecutive_timestamp_indices(times, contact_details['timesteps_in_contact'],
                                                                                glue_below_duration)
        self.n_sequences = len(self.consecutive_timestamp_indices)
        self.current = -1
        self.times = times

    def __iter__(self):
        return self

    def __next__(self):
        self.current += 1
        if self.current < self.n_sequences:
            seq = self.consecutive_timestamp_indices[self.current]
            contact_details_local = {}
            for key in self.cd.keys():
                contact_details_local[key] = self.cd[key][seq[0]:seq[-1]+1]
            # Overwrite contact_details_local['timesteps_in_contact'] by the actual timestamps with a contact
            contact_details_local['contact_timestamps'] = self.times[contact_details_local['timesteps_in_contact']]
            del contact_details_local['timesteps_in_contact']
            return contact_details_local
        raise StopIteration


def get_gps_contacts_from_trajectories(t1, t2, allowed_jump, hard_time_gap, glue_below_duration, dist_func, dist_func_options):
    """ Returns a list of contacts for a trajectory pair.
        Parameters:
        * t1: Trajectory 1
        * t2: Trajectory 2
        * dist_func: the distance function to be used for the contact computation
        * dist_func_options: options dictionary for the dist_function.
    """
    # Interpolate trajectories on union of time stamps
    times_t1 = t1.get_time_stamps()
    times_t2 = t2.get_time_stamps()
    times = union_of_time_stamps(times_t1, times_t2)

    interp_t1 = t1.restricted_upsampling_stamps(times, allowed_jump=allowed_jump, hard_time_gap=hard_time_gap)
    interp_t2 = t2.restricted_upsampling_stamps(times, allowed_jump=allowed_jump, hard_time_gap=hard_time_gap)

    # Find contacts
    contact_details = dist_func(interp_t1, interp_t2, **dist_func_options)

    # Create contact objects
    contacts = ContactList([GPSContact(t1, t2, contact_detail) for contact_detail
                            in GPSContactDetailsIterator(contact_details, times, glue_below_duration)
                           ])

    return contacts

