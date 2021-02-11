import datetime
import numpy as np
import pandas as pd

from corona.utils import convert_seconds, union_of_time_stamps
from corona.analysis.trajectory import TrajectoryParser
from corona.analysis.contact import BaseContact
from corona.analysis import bt_merge as BTMerge
from corona import logger
from corona.analysis.default_parameters import params
from corona.analysis.pois import POI

class BluetoothContact(BaseContact):
    """ A class to store details about a Bluetooth contact contact """

    def __init__(self, t1, t2, contact_details):
        """
        """
        BaseContact.__init__(self, t1, t2, contact_details)

        # Filter the trajectories so that they only contain the contact time +- slacktime
        slacktime = 30*60

        t1 = t1.filter(self.starttime()-slacktime, self.endtime()+slacktime)
        t2 = t2.filter(self.starttime()-slacktime, self.endtime()+slacktime)

        # Find GPS data times happening during the BT contact
        times_t1 = t1.get_time_stamps()
        times_t2 = t2.get_time_stamps()
        times = union_of_time_stamps(times_t1, times_t2)
        timesteps_in_contact = np.where((times >= self.starttime()) & (times <= self.endtime()))[0]
        timestamps_in_contact = times[timesteps_in_contact]

        if len(timestamps_in_contact) == 0:
            self.t1 = TrajectoryParser(pd.DataFrame({'time' : [], 'longitude' : [], 'latitude' : [], 'accuracy' : [], 'transport' : []}, columns = ['time','longitude','latitude','accuracy', 'transport']), t1.uuid)
            self.t2 = TrajectoryParser(pd.DataFrame({'time' : [], 'longitude' : [], 'latitude' : [], 'accuracy' : [], 'transport' : []}, columns = ['time','longitude','latitude','accuracy', 'transport']), t2.uuid)
            self.cd['contact_timestamps'] = []
            self.cd['locations'] = []
            self.cd['accuracy'] = []
            duration_with_gps = 0
        else:
            # Get when the GPS info is starting --- We do not interpolate for more than 5 minutes
            interpolation_duration = params['max_interpolation_duration_gps_for_bt']
            start_info, end_info = max(self.starttime(), timestamps_in_contact[0]- interpolation_duration), min(self.endtime(), timestamps_in_contact[-1]+ interpolation_duration)
            bluetooth_timestamps = list(set(np.arange(start_info, end_info,  interpolation_duration).tolist() + [end_info]))
            new_times = union_of_time_stamps(bluetooth_timestamps, timestamps_in_contact)

            # Get the total duration with GPS information (I do it that way to ensure in the end that uncertain + inside + outside == total duration)
            start_duration_without_gps = new_times[0] - self.starttime()
            end_duration_without_gps = self.endtime() - new_times[-1]
            assert start_duration_without_gps >= 0
            assert end_duration_without_gps >= 0
            duration_with_gps = self.duration() - start_duration_without_gps - end_duration_without_gps

            interp_t1 = t1.restricted_upsampling_stamps(new_times, allowed_jump=params['allowed_jump'], hard_time_gap=params['max_interpol_in_h'])
            interp_t2 = t2.restricted_upsampling_stamps(new_times, allowed_jump=params['allowed_jump'], hard_time_gap=params['max_interpol_in_h'])
            transport1 = t1.get_mode_of_transport(new_times)
            transport2 = t2.get_mode_of_transport(new_times)
            df1 = pd.DataFrame({'time' : new_times, 'longitude' : interp_t1[:,0].tolist(), 'latitude' : interp_t1[:,1].tolist(), 'accuracy' : interp_t1[:,2].tolist(), 'transport' : transport1},
                                   columns = ['time','longitude','latitude','accuracy', 'transport'])
            df2 = pd.DataFrame({'time' : new_times, 'longitude' : interp_t2[:,0].tolist(), 'latitude' : interp_t2[:,1].tolist(), 'accuracy' : interp_t2[:,2].tolist(), 'transport' : transport2},
                                   columns = ['time','longitude','latitude','accuracy', 'transport'])

            df1 = df1.loc[df1.latitude != 0].loc[df1.longitude != 0]
            df2 = df2.loc[df2.latitude != 0].loc[df2.longitude != 0]
            df1.index = range(len(df1.index))
            df2.index = range(len(df2.index))

            if len(df1.time.tolist()) > 0:
                assert df1.time.tolist()[0] >= start_info
                assert df1.time.tolist()[-1] <= end_info
            if len(df2.time.tolist()) > 0:
                assert df2.time.tolist()[0] >= start_info
                assert df2.time.tolist()[-1] <= end_info
            if end_info > start_info:
                assert len(df1.index) > 0 or len(df2.index) > 0

            self.t1 = TrajectoryParser(df1, t1.uuid)
            self.t2 = TrajectoryParser(df2, t2.uuid)

            # Get corresponding locations
            common_df = pd.concat([self.t1.get_pd_frame(), self.t2.get_pd_frame()])
            common_df = common_df.drop_duplicates(subset = 'time', keep="first")
            common_df = common_df.sort_values('time')
            common_df = common_df.reset_index(drop=True)

            if len(common_df.time.tolist()) > 0:
                assert common_df.time.tolist()[0] >= start_info
                assert common_df.time.tolist()[-1] <= end_info

            # gps accuracy
            self.cd['contact_timestamps'] = common_df.time.tolist()
            self.cd["accuracy"] =  [(acc1,acc1) for acc1 in common_df.accuracy.to_numpy().tolist()]
            self.cd["locations"] = common_df[['longitude','latitude']].to_numpy().tolist()
            assert len(self.cd['contact_timestamps']) == len(self.cd["accuracy"]) == len(self.cd["locations"])

        self._init_transport_mode()
        self.contact_pois = POI(self.t1, self.t2, self.cd, self.duration(), duration_with_gps)


    def __str__(self):
        s =  f" * Type: Bluetooth\n"
        s += f" * Time: {self.time_from()} -- {self.time_to()} (UTC)\n"
        s += f" * Duration: {convert_seconds(self.duration())}\n"
        s += f" * Transport modes: {self.transport_modes()}\n"
        s += f" * Close duration: {convert_seconds(self.close_duration())}\n"
        s += f" * Very close duration: {convert_seconds(self.very_close_duration())}\n"
        s += f" * Relatively close duration: {convert_seconds(self.relatively_close_duration())}\n"
        s += f" * Risk score: {self.risk_score():.2f}\n"
        return s

    def contact_type(self):
        """ Returns contact type 'bluetooth' """
        return 'bluetooth'

    def average_distance(self):
        """ Returns average distance in meters.
        Return value: float """
        return (1*self.very_close_duration() + 2*self.close_duration() + 5*self.relatively_close_duration())/self.duration()

    def median_distance(self):
        """ Returns median distance in metres """
        # FIXME: compute as duration weighted median
        values = [1.]*int(self.very_close_duration())
        values.extend([2.]*int(self.close_duration()))
        values.extend([5.]*int(self.relatively_close_duration()))
        # NOTE: Unlike previous code, this does not give 1.5
        median = np.median(values)
        return max(1, median)

    def average_accuracy(self):
        """ Returns average accuracy in meters.
        Return value: float """
        return 1.

    def duration(self):
        """ Returns contact duration in seconds """
        return self.close_duration() + self.very_close_duration() + self.relatively_close_duration()

    def close_duration(self):
        """ Returns close contact duration in seconds """
        return self.cd['close_duration']

    def relatively_close_duration(self):
        """ Returns relative close contact duration in seconds """
        return self.cd['relatively_close_duration']

    def very_close_duration(self):
        """ Returns very close contact duration in seconds """
        return self.cd['very_close_duration']

    def starttime(self):
        """ Returns unix time stamp of start time """
        return self.cd['starttime']

    def endtime(self):
        """ Returns unix time stamp of start time """
        return self.duration() + self.starttime()

    def risk_score(self):
        """ Returns the risk value of the given bluetooth contact in minutes/meters**2 """
        risk_score_close = self.close_duration() / 60. * 1.0/2.0**2            # USING DISTANCE CONVENTION: dist = 2 m
        risk_score_very_close = self.very_close_duration() / 60. * 1.0/1.0**2  # USING DISTANCE CONVENTION: dist = 1 m
        risk_score_relatively_close = self.relatively_close_duration() / 60. * 1.0/5.0**2  # USING DISTANCE CONVENTION: dist = 5 m
        return risk_score_close + risk_score_very_close + risk_score_relatively_close

    def risk_category_thresholds(self):
        """ Returns thresholds for risk categories 'high', 'medium', 'low' and 'no' """
        return [10.0, 7.5, 0.6]

    def to_dict(self, include_plot=None):
        """ Returns a dictionary representation of the contact """
        dic = super(BluetoothContact, self).to_dict(include_plot)
        dic.update({
            'close_duration' : self.close_duration(),
            'very_close_duration' : self.very_close_duration(),
            'relatively_close_duration': self.relatively_close_duration()
            })
        return dic

    def split_contact(self, switching_time):
        """
        Splits the BTContact at the given switching point.
        :param switching_time: A datetime.datetime object (UTC time) at which point the contact is supposed
        to be split into two parts
        :returns: tuple of BTContacts
        """
        # Convert switchting time to unix time stamp (ASSUMES UTC time)
        switching_time_stamp = datetime.datetime.timestamp(switching_time)
        if switching_time_stamp <= self.starttime() or switching_time_stamp >= self.endtime():
            raise RuntimeError("BluetoothContact.split_contact() tries to split at time {0} outside of contact time {1} - {2}".format(
                switching_time_stamp, self.starttime(), self.endtime()))

        contact_details_1 = {'starttime' : self.starttime()}
        contact_details_2 = {'starttime' : switching_time_stamp}
        duration_c2 = self.endtime() - switching_time_stamp # in seconds
        duration_c1 = self.duration() - duration_c2 # in seconds
        relative_duration_c1 = float(duration_c1)/float(self.duration())
        relative_duration_c2 = float(duration_c2)/float(self.duration())

        contact_details_1.update({'close_duration' : self.close_duration() * relative_duration_c1})
        contact_details_1.update({'very_close_duration' : self.very_close_duration() * relative_duration_c1})
        contact_details_1.update({'relatively_close_duration' : self.relatively_close_duration() * relative_duration_c1})

        contact_details_2.update({'close_duration' : self.close_duration() * relative_duration_c2})
        contact_details_2.update({'very_close_duration' : self.very_close_duration() * relative_duration_c2})
        contact_details_2.update({'relatively_close_duration' : self.relatively_close_duration() * relative_duration_c2})

        # Trajectory objects
        c1_t1 = TrajectoryParser(self.t1.get_pd_frame().loc[self.t1.get_pd_frame()['time'] < switching_time_stamp], self.t1.uuid)
        c1_t2 = TrajectoryParser(self.t2.get_pd_frame().loc[self.t2.get_pd_frame()['time'] < switching_time_stamp], self.t2.uuid)
        c2_t1 = TrajectoryParser(self.t1.get_pd_frame().loc[self.t1.get_pd_frame()['time'] >= switching_time_stamp], self.t1.uuid)
        c2_t2 = TrajectoryParser(self.t2.get_pd_frame().loc[self.t2.get_pd_frame()['time'] >= switching_time_stamp], self.t2.uuid)
        # Check and potentially split contact_details 'timesteps_in_contact','accuracy','locations','transport_mode' entries
        c_times = self.cd['contact_timestamps']
        if len(c_times) > 0:
            switching_point = np.searchsorted(c_times, switching_time_stamp)  # Finds the index where the gps contact information should be splitted
            contact_details_1.update({item: self.cd[item][:switching_point] for item in self.cd if item in ['contact_timestamps','accuracy','locations','transport_mode']})
            contact_details_2.update({item: self.cd[item][switching_point:] for item in self.cd if item in ['contact_timestamps','accuracy','locations','transport_mode']})
        else:
            contact_details_1.update({item: [] for item in self.cd if item in ['contact_timestamps','accuracy','locations','transport_mode']})
            contact_details_2.update({item: [] for item in self.cd if item in ['contact_timestamps','accuracy','locations','transport_mode']})
        c1 = BluetoothContact(c1_t1, c1_t2, contact_details_1)
        c2 = BluetoothContact(c2_t1, c2_t2, contact_details_2)
        return c1, c2

    def bar_plot(self, ax):
        """ Adds a plot t -> distance to the given handle """
        start = self.starttime()
        end_c = start + self.close_duration()
        end_vc = start + self.very_close_duration()
        end_rc = start + self.relatively_close_duration()
        # As utc
        start, end_c, end_vc, end_rc = map(datetime.datetime.utcfromtimestamp,
                                           (start, end_c, end_vc, end_rc))

        short = datetime.timedelta(seconds=10)
        # We plot short signals as points!
        for end, color, dist in zip((end_c, end_vc, end_rc), ('blue', 'cyan', 'magenta'), (2, 1, 5)):
            if end > start:
                if (end - start) > short:
                    ax.plot(np.array([start, end]), dist * np.ones(2), color, linewidth=4)
                    # logger.info(f'Adding {color} to BT line plot {start} - {end}')
                else:
                    ax.plot(start + 0.5*(end-start), dist, color=color, marker='o', markersize=4)
                    # logger.info(f'Adding {color} to BT point plot {start} - {end}')

        return ax


class BluetoothContactDetailsIterator(object):
    '''
    Given a Pandas dataframe

      [uuid, paireddeviceid, encounterstarttime, duration, very_close_duration, close_duration, relatively_close_duration]

    we want to produce non-ovelapping events that are the contact details
    '''
    def __init__(self, df_contacts, glue_below_duration):
        self.n_entries = len(df_contacts)
        # Make frame row table to frame row table
        self.events = BTMerge.BTMerge(df_contacts, glue_below_duration)

    def __iter__(self):
        for event in self.events:
            # Fill based on row of table
            yield {'starttime': BTMerge.e_start(event),
                   'very_close_duration': BTMerge.e_vcd(event),
                   'close_duration': BTMerge.e_cd(event),
                   'relatively_close_duration': BTMerge.e_rcd(event)}

