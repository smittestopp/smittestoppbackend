import io
import folium
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from corona.utils import numpy_to_pd_frame, convert_seconds
from corona.plotting import create_map_for_user
import datetime

class TrajectoryViewer(object):
    """
    Class takes in a pandas data or numpy array frame with columns representing
    ['time', 'longitude', 'latitude','accuracy'] and can be used to
    inspect and plot corresponding trajectories
    """

    def __init__(self):
        pass

    """ Callable methods """
    def plot(self, trajectory, ax=None, timecol=False, label=None, **plot_options):
        """ Adds plot of trajectory to the given axis
        Parameters
        ----------

        trajectory : pd_frame or numpy array of trajectory

        ax : plt axis if plot should be added to existing axis

        timecol : if trajectory is numpy array and timecol = True, method assumes
            numpy array of shape (n_timestamps, 4) with first column being time column

        label : str
            Label for legend
        """
        if not isinstance(trajectory, pd.DataFrame):
            trajectory = numpy_to_pd_frame(trajectory, timecol=timecol)
        df_new = trajectory[trajectory['latitude'] != 0]
        if ax is not None:
            ax.scatter(df_new['latitude'], df_new['longitude'], label=label, **plot_options)
        else:
            plt.figure()
            ax = plt.gca()
            ax.scatter(df_new['latitude'], df_new['longitude'], label=label, **plot_options)
        if len(df_new) > 0:
            lat_min, lat_max = min(df_new['latitude']), max(df_new['latitude'])
            long_min, long_max = min(df_new['longitude']), max(df_new['longitude'])
            plt.xlim(lat_min - 0.05 * max(lat_max - lat_min, 1e-4), lat_max + 0.05 * max(lat_max - lat_min, 1e-4))
            plt.ylim(long_min - 0.05 * max(long_max - long_min, 1e-4), long_max + 0.05 * max(long_max - long_min, 1e-4))
        return ax


    def create_keplerGL_html_output(self, trajectories, file_name, filter_uuid = None, timecol = False):
        """
        Wrapper for corona.plotting create_map_for_user

        Takes trajectories dictionary with key equals uuid and
        values equal pd frame or numpy array with location data.
        """
        trajectories_new = {}
        if filter_uuid is None:
            filter_uuid = trajectories.keys()
        for uuid, trajectory in trajectories.items():
            if not uuid in filter_uuid:
                continue
            if not isinstance(trajectory, pd.DataFrame):
                trajectory = numpy_to_pd_frame(trajectory, timecol=timecol)
            df_new = trajectory[trajectory['latitude'] != 0]
            trajectories_new[uuid] = df_new
        map = create_map_for_user(trajectories_new)
        map.save_to_html(file_name=file_name)


    def animate(self, trajectory, timecol = False, delay = 200):
        """
        Plots an time animiation of a trajectory with given delay in ms.
        """
        if not isinstance(trajectory, pd.DataFrame):
            trajectory = numpy_to_pd_frame(trajectory, timecol = timecol)
        df_new = trajectory[trajectory['latitude'] != 0]
        lat_min, lat_max = min(df_new['latitude']), max(df_new['latitude'])
        long_min, long_max = min(df_new['longitude']), max(df_new['longitude'])
        fig = plt.figure()
        plt.xlim(lat_min - 0.05 * (lat_max - lat_min), lat_max + 0.05 * (lat_max - lat_min))
        plt.ylim(long_min - 0.05 * (long_max - long_min), long_max + 0.05 * (long_max - long_min))
        graph, = plt.plot([], [], 'o')
        def _animate_(i):
            graph.set_data(df_new['latitude'].to_numpy()[:i+1], df_new['longitude'].to_numpy()[:i+1])
            return graph
        ani = FuncAnimation(fig, _animate_, frames=len(df_new), interval = delay, repeat = False)
        plt.show()

    def show(self):
        """ Wrapper for plt.show() so no need to import matplotlib """
        plt.legend()
        plt.show()

    def as_svg(self):
        """ Returns the figure as an SVG string """
        f = io.StringIO()
        plt.savefig(f, format = "svg")
        return f.getvalue()

    def close(self):
        """ Closes the figure """
        plt.close()


class TrajectoryFoliumViewer(object):
    def __init__(self, trajectory_data):
        self.t = trajectory_data

        self.color_settings = {
                "blue": {'color': '#3186cc',
                         'fill': True,
                         'fill_color':'#3186cc'
                         },
                "green": {'color': '#31cc46',
                         'fill': True,
                         'fill_color':'#31cc46'
                         },
                "red": {'color': 'crimson',
                         'fill': False,
                         }
                }

        self.group_names = {'red': 'Contacts',
                            'blue': 'Patient',
                            'green': 'Riskinfected'}

    def add_folium_markers(self, folium_map, color):
        """ Color can be one of: green, blue, red """
        color_setting = self.color_settings[color]

        # Markers are added as feature group so that they can be toggled
        group = folium.FeatureGroup(name=self.group_names[color])
        for (time, lon, lat, acc) in self.t:
            utc_time = datetime.datetime.utcfromtimestamp(time)
            folium.Circle(
                location=[lat, lon],
                radius=acc,
                popup=f"Time: {utc_time}\nAcc: {acc:.1f}",
                **color_setting
            ).add_to(group)
        # Bind to map
        group.add_to(folium_map)

