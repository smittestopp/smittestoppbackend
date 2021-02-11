import numpy as np
import multiprocessing
import datetime
import more_itertools as mit
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as md
import io
import folium

from corona.utils import union_of_time_stamps, duration_of_contact, convert_seconds
from corona.analysis.default_parameters import params
from corona.analysis.trajectory.viewer import TrajectoryViewer, TrajectoryFoliumViewer
from corona.analysis.trajectory.parser import TrajectoryParser
from corona.analysis.pois import POI

__RISK_CATEGORY_IDENTIFIER__ = ['high','medium','low','no']

class BaseContact(object):

    def __init__(self, t1, t2, contact_details):
        """ Class takes two trajectoryParser objects t1 and t2 and
        contact details (output from intersection functions over consecutive
        time stamps) and creates a contact.
        """
        self.cd = contact_details

    def time_from(self):
       """ Returns start time in UTC format """
       return datetime.datetime.utcfromtimestamp(self.starttime()).strftime('%Y-%m-%d %H:%M:%S')

    def time_to(self):
       """ Returns end time in UTC format """
       return datetime.datetime.utcfromtimestamp(self.endtime()).strftime('%Y-%m-%d %H:%M:%S')

    def risk_category(self):
       """ Returns risk category of an individual BT contact """
       risk_score = self.risk_score()
       for cat in range(3):
           # Note ordering of risks to go from high to low here is important!!
           if risk_score > self.risk_category_thresholds()[cat]:
              return __RISK_CATEGORY_IDENTIFIER__[cat]
       return __RISK_CATEGORY_IDENTIFIER__[3]

    def trajectory(self):
       """ Returns the contact as a trajectory of time, lat, lon, acc """
       n_timestamps_contact = len(self.cd['contact_timestamps'])
       contact_trajectory = np.zeros((n_timestamps_contact,4))
       contact_trajectory[:,0] = self.cd['contact_timestamps']
       contact_trajectory[:,1] = np.array([pos[0] for pos in self.cd['locations']])
       contact_trajectory[:,2] = np.array([pos[1] for pos in self.cd['locations']])
       contact_trajectory[:,3] = np.array([0.5 * acc[0] + 0.5 * acc[1] for acc in self.cd['accuracy']])
       return contact_trajectory

    def filtered_pois(self):
        return self.contact_pois.filtered_pois()

    def pois(self):
        return self.contact_pois.pois()

    def to_dict(self, include_plot=None):
        pois, duration_inside, duration_outside, uncertain_duration = self.filtered_pois()
        dic = {'duration': self.duration(),
            'time_from': self.time_from(),
            'time_to': self.time_to(),
            'transport_modes': {m: convert_seconds(d) for m, d in self.transport_modes().items()},
            'risk_score' : self.risk_score(),
            'average_distance' : self.average_distance(),
            'median_distance' : self.median_distance(),
            'average_accuracy' : self.average_accuracy(),
            'duration_inside' : duration_inside,
            'duration_outside' : duration_outside,
            'uncertain_duration' : uncertain_duration,
            'pois' : {m: convert_seconds(d) for m, d in pois.items()},
            'most_common_transport_modes' : self.get_most_common_transport_modes()}

        if include_plot in ("static", "interactive"):
            if (len(self.t1)>0 or len(self.t2)>0):
                if include_plot=="static":
                    dic["plot"] = self.plot(as_svg=True)
                if include_plot=="interactive":
                    dic["plot"] = self.plot_interactive()
            else:
                dic["plot"] = "No GPS data available"
        return dic

    def _init_transport_mode(self):
        """ Helper for derived objects, do not call without having
        self.t1, self.t2  instantiated. """
        t1_transport = self.t1.get_mode_of_transport(self.cd['contact_timestamps'])
        t2_transport = self.t2.get_mode_of_transport(self.cd['contact_timestamps'])
        t1_t2_transport = list(zip(t1_transport, t2_transport))
        self.cd['transport_mode'] = t1_t2_transport

    def transport_modes(self,  threshold = 0.2, threshold_duration = 300):
        """
        Return transport modes as a list of strings.
        threshold: float s.t. we filter with a given amount (e.g. 0.3 : 30%)
        threshold_duration: if it is above a certain duration, we don't filter out even if below threshold.
        """

        mode_list = self.cd['transport_mode']
        contact_times = np.asarray(self.cd['contact_timestamps'])
        durations = contact_times[1:]-contact_times[:-1]

        weights = np.zeros(len(contact_times))
        weights[:-1] = 0.5*durations
        weights[1:] += 0.5*durations

        # Sum the duration for each transport mode tuple
        d = dict.fromkeys(set(mode_list), 0)
        for mode, w in zip(mode_list, weights):
            d[mode] += w

        return {mode: dur for mode, dur in d.items() if dur >= threshold*self.duration() or dur >= threshold_duration}

    def get_most_common_transport_modes(self):

        # create a dictionary attributing time to each transport_mode
        transport_modes = self.transport_modes(threshold = 0.0)

        entry_pairs = [x for _,x in enumerate(transport_modes)]
        entries = set(np.reshape(entry_pairs, 2 * len(entry_pairs)))
        dic = {i : 0 for i in entries if i != 'N/A'}

        # fill dictionary with values
        for t in transport_modes:
            if t[0] != 'N/A':
                dic[t[0]] += transport_modes[t]
            if t[1] != 'N/A':
                dic[t[1]] += transport_modes[t]
        total = sum([dic[t] for t in dic])

        # report only the most common transport modes
        threshold_max = 0.4 # (40 %)
        most_common_transport_modes = [t for t in dic if dic[t] > threshold_max * total]

        # it can happen that there is no transport mode constituting 40 % of the total time
        # this ensures to return at least one transport mode (the most common)
        if most_common_transport_modes == [] and transport_modes != {}:
            return [max(dic, key = dic.get)]

        return most_common_transport_modes

    def plot(self, title = "", as_svg=False):
        """ Creates a plot of the contact """
        viewer = TrajectoryViewer()
        trajectory1 = self.t1.get_raw_data()
        trajectory2 = self.t2.get_raw_data()
        contact_trajectory = self.trajectory()
        ax = viewer.plot(trajectory1, label=self.t1.uuid, ax=None, timecol=True, color='b', marker="o")
        ax = viewer.plot(trajectory2, label=self.t2.uuid, ax=ax, timecol=True, color='g', marker=".")
        ax = viewer.plot(contact_trajectory, label=f"Contact points", ax=ax, timecol=True, facecolors='none', edgecolors='r')
        ax.set_title(title)
        ax.legend()
        if as_svg:
            svg = viewer.as_svg()
            viewer.close()
            return svg
        else:
            viewer.show()

    def plot_interactive(self, folium_map = None):
        """ Creates a plot of the contact using an interactive folium map. """
        if folium_map is None:
            if len(self.t1.get_raw_data())>0 and len(self.t2.get_raw_data())>0:
                # Only get lat, lon if both have a trajectory
                lon, lat = self.t1.get_raw_data()[0][1:3]
                # lon, lat = self.t2.get_raw_data()[0][1:3]
            else:
                return "No GPS information"

        folium_map = folium.Map(location=[lat, lon], zoom_start=14,
                                control_scale=True, prefer_canvas=True)

        # Add trajectory 1
        viewer1 = TrajectoryFoliumViewer(self.t1.data)
        viewer1.add_folium_markers(folium_map, "blue")

        # Add trajectory 2
        viewer2 = TrajectoryFoliumViewer(self.t2.data)
        viewer2.add_folium_markers(folium_map, "green")

        # Add contact points
        contact_trajectory = self.trajectory()
        viewer3 = TrajectoryFoliumViewer(contact_trajectory)
        viewer3.add_folium_markers(folium_map, "red")

        # Controls for toggle markers
        folium.LayerControl().add_to(folium_map)

        return folium_map._repr_html_()
