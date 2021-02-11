import multiprocessing
import numpy as np
import datetime
import base64
import matplotlib.pyplot as plt
import matplotlib.dates as md
import io
import weighted # library wquantiles
import folium
import pandas as pd
import matplotlib.pyplot as plt
from cartopy.io.img_tiles import OSM
import cartopy.crs as ccrs

from corona import logger
from corona.analysis.trajectory.viewer import TrajectoryFoliumViewer
from collections import defaultdict
from corona.utils import convert_seconds, get_or, duration_of_contact, haversine_distance

# Thresholds for assigning a risk category to a cumulative contact
__RISK_CATEGORY_IDENTIFIER__ = ['high','medium','low','no']


class ContactList(list):
    """ A class storing a list of contacts """

    def filter(self, min_duration=None, contact_type=None, average_accuracy_below=None):
        """ Filters the contact list. The method always returns a new ContactList object.contact_list

        :params min_duration: Filter all contacts have a duration of at least min_duration
        :params contact_type: Filter all contacts that are of the specified contact type. Valid choices: ["bluetooth", "gps"]
        :params average_accuracy_below: Filter all contacts for which the average accuracy is below the given threshold.

        """
        results = self

        if min_duration is not None:
            results = self.__class__([c for c in results if c.duration()>=min_duration])

        if contact_type is not None:
            assert  contact_type in ["bluetooth", "gps"]
            results = self.__class__([c for c in results if c.contact_type()==contact_type])

        if average_accuracy_below is not None:
            results = self.__class__([c for c in results if c.average_accuracy()<average_accuracy_below])

        return results

    def include_in_report(self):
        """ Checks whether contact list is sufficient based on certain criteria:

            1) needs to contain BT contacts with cumulative duration of > 2 minutes OR
            2) needs to contain GPS contacts of accuracy below 10 meters and cumulative duration of > 30 minutes.
        """
        bt_contacts = self.filter(contact_type='bluetooth')
        gps_contacts_accurate = self.filter(contact_type='gps', average_accuracy_below=10)
        if bt_contacts.cumulative_duration() > 2 * 60:
            return True
        elif gps_contacts_accurate.cumulative_duration() > 30 * 60:
            return True
        else:
            return False


    def empty(self):
        """ Returns True if the contact list is empty and False otherwise. """
        return len(self) == 0

    def cumulative_duration(self):
        return sum([c.duration() for c in self])

    def cumulative_risk_score(self):
        """ Returns the cumulative risk score in minutes/meters**2 """
        return sum([c.risk_score() for c in self])

    def risk_category_as_int(self):
        """ Returns the risk category identify (is an integer)
            3 if 'no'
            2 if 'low'
            1 if 'medium'
            0 if 'high',
        based on cumulative risk score and risk categories (see contacts classes).
        Assumes all contacts in list to be either GPS or Bluetooh! """
        risk_score = self.cumulative_risk_score()
        if len(self) == 0:
            return 3
        for cat in range(3):
            # Note ordering of risks to go from high to low here is important!!
            if risk_score > self[0].risk_category_thresholds()[cat]:
                return cat
        return 3

    def risk_category(self):
        """ Returns risk category as string.

            Together with include_in_report(), we implement the following logic:

            BT duration   ->      | none          |  between 2 min and 15min     | > 15min
            ------------------------------------------------------------------------------------
            GPS duration  |       |               |                              |
                          v       |               |                              |
            < 30min high accuracy | not reported  |  bt_below_15_min             | low/normal/high
            > 30min high accuracy | gps_only      |  low/normal/high             | low/normal/high

        """

        bt_contacts = self.filter(contact_type='bluetooth')
        gps_contacts = self.filter(contact_type='gps')
        gps_contacts_accurate = gps_contacts.filter(average_accuracy_below=10)

        # Special cases for FHI testing.
        # 1. If the GPS duration is below 30min, and the BT duration below 15min,
        # we set the risk category to "bt_below_15_min"
        if (gps_contacts_accurate.cumulative_duration() <= 30*60 and
            bt_contacts.cumulative_duration() <= 15*60):
            return "bt_below_15_min"
        # 2. If there are no BT contacts, but at least 30 minutes GPS contact duration
        #    with high accuracy, set the category to "gps_only"
        if (gps_contacts_accurate.cumulative_duration() > 30*60 and
            bt_contacts.empty()):
            return "gps_only"

        bt_risk = bt_contacts.risk_category_as_int()
        gps_risk = gps_contacts.risk_category_as_int()
        return __RISK_CATEGORY_IDENTIFIER__[min(bt_risk, gps_risk)]

    def most_common_pois(self, threshold_prop = 0.2, threshold_time = 180, long_threshold_time = 300):
        """
        Returns the most common points of interest
        threshold_prop: returned pois must account to at least xx% of total inside time
        threshold_time: returned pois must account to at least xx seconds
        """
        if len(self)==0:
            return {'uncertain' : self.cumulative_duration()}

        pois_info = np.asarray([c.pois() for c in self])
        pois_list, inside_time, outside_time, uncertain_time = pois_info[:,0], sum(pois_info[:,1]), sum(pois_info[:,2]), sum(pois_info[:,3])
        total_time = inside_time # outside_time and uncertain_time not counted
        pois = {d: 0 for dico in pois_list for d in dico} # if d!='uncertain'}
        for dico in pois_list:
            for d in dico:
                    pois[d] += dico[d]
        # Note that we eliminate 'uncertain' here
        most_common_pois = {place: dur for place, dur in pois.items() if ( ((dur >= threshold_prop*total_time and dur >= threshold_time) or (dur>= long_threshold_time)) and (place!='uncertain') and (place!='N/A'))}

        if most_common_pois == {}:
             return {max(pois, key = pois.get) : pois[max(pois, key = pois.get)]}

        return most_common_pois

    def split_by_days(self):
        """
        Transforms a contact_list into a dictionary of the form:
            {'2020-04-06' : contact_list_1, '2020-04-07' : contact_list_2, '2020-04-08' : contact_list_ 3}

        Days are always 'cut' at 02:00 am.
        However, in the case of a path extended from day 20 02:00 am to day 20 07:00 am,
                 we would also fully include it in day 20 (rather than in days 19 and 20).
        This also applies to a path finishing before 02:00 on the next day,
                 i.e. in the case of a path extended from day 20 06:00 am (or 02:00 am) to day 21 02:00 am,
                 we would fully contain it in day 20.

        FIXME: The description is not quite clear
        """
        d = defaultdict(ContactList)
        for c in self:
            start_datetime = datetime.datetime.utcfromtimestamp(c.starttime())
            end_datetime = datetime.datetime.utcfromtimestamp(c.endtime())
            # If the path is contained in the day from 00:00 to 02:00 (UTC) on the next day, we assign it this day
            if start_datetime.date() >= (end_datetime - datetime.timedelta(hours=2)).date():
                d[start_datetime.date()].append(c)
            # Else the path exceeds 02:00 (UTC) the next day and therefore spans several days
            else:
                c1, c2 = c, c
                stopping_criteria = start_datetime.date() >= (end_datetime - datetime.timedelta(hours = 2)).date()
                while not stopping_criteria:
                    # Split contact at day-i + 1 at 02:00 am
                    next_day = start_datetime.date() + datetime.timedelta(days = 1) # Day i+1
                    splitting_time = datetime.datetime.combine(next_day, datetime.time(hour = 2)) # 02 AM on Day i + 1
                    # Split contact: c1 goes from start_datetime to splitting_time, c_2 from splitting_time end_datetime
                    c1, c2 = c2.split_contact(splitting_time)
                    d[start_datetime.date()].append(c1)
                    start_datetime = splitting_time
                    stopping_criteria = start_datetime.date() >= (end_datetime - datetime.timedelta(hours = 2)).date()
                d[start_datetime.date()].append(c2)
        # Sort dictionary by date, needs Python 3.7+
        return dict(sorted(d.items(), key=lambda time_value: time_value[0]))

    def cumulative_duration_types(self):
        if len(self)==0:
            return "", 0, 0, 0
        pois_info = np.asarray([c.pois() for c in self])
        pois, times_inside, times_outside, times_uncertain = pois_info[:,0], pois_info[:,1], pois_info[:,2], pois_info[:,3]
        pois =', '.join(set([x for poi in pois for _,x in enumerate(poi) if (x!='outside' and x!='inside_transport' and x!='uncertain')]))
        return pois, sum(times_inside), sum(times_outside), sum(times_uncertain)

    def starttime(self):
        """ Returns the starttime of the first contact in list of contact. """
        return min([c.starttime() for c in self])

    def endtime(self):
        """ Returns the endtime of the last contact in list of contact. """
        return max([c.endtime() for c in self])

    def median_distance(self):
        """ returns the median of the medians of each contact's distances """
        if len(self) == 0:
            return None
        medians = [c.median_distance() for c in self]
        weights = [c.duration() for c in self]
        weights = [w/sum(weights) for w in weights]
        df = pd.DataFrame({'medians' : medians, 'w' : weights})
        return weighted.median(df['medians'], df['w'])

    def __str__(self):
        s =  f"Cumulative duration: {convert_seconds(self.cumulative_duration())}\n"
        s += f"Cumulative risk score: {round(self.cumulative_risk_score(),2)}\n"

        for i, contact in enumerate(self):
            s += "-"*80 + "\n"
            s += f"Contact {i}:\n"
            s += str(contact)

        return s

    def cumulative_duration_naive_heuristic(self):
        pois_info = np.asarray([c.heuristic_pois() for c in self])
        pois, times_inside, times_outside = pois_info[:,0], pois_info[:,1], pois_info[:,2]
        pois =', '.join(set([x for poi in pois for _,x in enumerate(poi) if (x!='outside' and x!='inside_transport' and poi[x] != 0)]))
        return pois, sum(times_inside), sum(times_outside)

    def to_dict(self, include_plots=None, include_individual_contacts=True, include_bar_plot=False, include_summary_plot=False, include_hist=False):
        """ Returns a dictionary representation of the contact list.

        :params include_plots: Which type of plots should be included. Can  be None, "static" or "interactive".
                               Only relevant if include_individual_contacts is True.
        :params include_individual_contacts: if True, a list of individual contact detils will be added.
        :params include_summary_plot: if True includes a plot that shows all data in ContactList
         """
        pois, cumulative_duration_inside, cumulative_duration_outside, cumulative_uncertain_duration = self.cumulative_duration_types()
        dic = {'cumulative_duration':   self.cumulative_duration(),
               'cumulative_risk_score': round(self.cumulative_risk_score(),2),
               'number_of_contacts':    len(self),
               'median_distance':       self.median_distance(),
               'cumulative_duration_inside': cumulative_duration_inside,
               'cumulative_duration_outside': cumulative_duration_outside,
               'cumulative_uncertain_duration': cumulative_uncertain_duration,
               'points_of_interest': self.most_common_pois(), # pois,
               'risk_cat': self.risk_category(),
               # For BlueTooth we want to propagate forward some of the details of the
               # contact
               'bt_very_close_duration': sum(get_or(c, 'very_close_duration', 0) for c in self),
               'bt_close_duration': sum(get_or(c, 'close_duration', 0) for c in self),
               'bt_relatively_close_duration': sum(get_or(c, 'relatively_close_duration', 0) for c in self)
              }

        if include_bar_plot:
            dic['bar_plot'] = base64.b64encode(self.bar_plot()).decode('utf-8')

        if include_hist:
            res = self.distances_hist()
            if res is not None:
                dic['hist_plot'] = base64.b64encode(res).decode('utf-8')

        if include_summary_plot == 'interactive':
            dic['summary_plot'] = self.plot_interactive()
        elif include_summary_plot == 'static':
            plot = self.plot_static()
            if plot is not None:
                dic['summary_plot'] = base64.b64encode(self.plot_static()).decode('utf-8')

        if include_individual_contacts:
            dic["contact_details"] = [c.to_dict(include_plots) for c in self]

        return dic

    def distances_hist(self, format="png", dpi=100):
        """ returns a bar chart for each category of distances """
        if len(self)==0:
            return None
        bins=[0,5,10,20,30,50]
        categories=[0,1,2,3,4,5]
        labels=[("[" + str(bins[i-1]) + "," + str(bins[i]) + "]") for i in range(1,len(bins))] + ["["+str(bins[-1])+",inf["]

        all_times = np.zeros(len(bins))
        for c in self:
            c_times = c.cd['contact_timestamps']
            c_dists = c.cd['dists']
            c_cats = [good_bin(x) for x in c_dists]
            indices_per_bin = [[i for i in range(len(c_cats)) if c_cats[i]==bin_number] for bin_number in categories]
            time_per_bin = [duration_of_contact(c_times, indices_list) for indices_list in indices_per_bin]
            all_times += np.asarray(time_per_bin)
        all_times /= 60.0
        values = [int(round(el)) for el in all_times]
        x = np.arange(len(labels)) # label locations
        width = 0.35
        plt.figure(figsize = (10, 7))
        ax = plt.gca()
        rects = ax.bar(x, values, width)

        ax.set_ylabel('Duration (in minutes)')
        ax.set_title('Duration in each distance category.')
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        for rect in rects:
            height = rect.get_height()
            ax.annotate('{}'.format(height), xy=(rect.get_x() + rect.get_width() / 2, height), xytext=(0, 3),
                        textcoords="offset points", ha='center', va='bottom') # 3 points vertical offset

        plt.gcf().autofmt_xdate()
        f = io.BytesIO()
        plt.savefig(f, format=format, quality=95, dpi=dpi)
        f.seek(0)
        plt.close()
        return f.getvalue()

    def bar_plot(self, format="png", dpi=100):
        """ Creates a plot of contacts during the entire analysis period """
        plt.figure(figsize = (10, 7))
        ax = plt.gca()
        for c in self:
            ax = c.bar_plot(ax)

        xmin, xmax = ax.get_xlim()
        if xmax - xmin > 0.5:
            xfmt = md.DateFormatter('%Y-%m-%d')
            ax.xaxis.set_major_locator(md.DayLocator(interval=1))
        # If the plot would cover only half a day we increase granularity
        # for x axis
        else:
            xfmt = md.DateFormatter('%Y-%m-%d-%H-%M')
            ax.xaxis.set_major_locator(md.MinuteLocator(interval=30))
        ax.xaxis.set_major_formatter(xfmt)
        ax.xaxis_date()

        # let's rely here on the defaults instead
        #start_datetime = datetime.datetime.utcfromtimestamp(self.starttime()).replace(hour=3, minute=0, second=0)
        #end_datetime = (datetime.datetime.utcfromtimestamp(self.endtime()) + datetime.timedelta(days=1)).replace(hour=3, minute=0, second=0)
        # ax.set_xlim(start_datetime, end_datetime)

        plt.ylabel("Distance [m]")
        plt.gcf().autofmt_xdate()
        f = io.BytesIO()
        plt.savefig(f, format=format, quality=95, dpi=dpi)
        f.seek(0)
        plt.close()

        return f.getvalue()

    def plot_static(self, format="png", dpi=150):
        '''Creates a map of the contact list using a cartopy map.'''
        # Plotting work horse, basically we want a big plot and then a zoom in
        # on contact area
        def do_plot(ax, t1s, t2s, contact_ts, extend, imagery, level=14):
            '''Add to axis'''
            ax.set_extent(extend)
            ax.add_image(imagery, level)

            lons = t1s["longitude"].to_numpy()
            lats = t1s["latitude"].to_numpy()
            size = t1s["accuracy"].to_numpy()

            # do coordinate conversion of (lat,y)
            xynps = ax.projection.transform_points(ccrs.Geodetic(), lons, lats)
            ax.scatter(xynps[:,0], xynps[:,1], size, marker='o', alpha=.5, color="blue", label="Patient")

            lons = t2s["longitude"].to_numpy()
            lats = t2s["latitude"].to_numpy()
            size = t2s["accuracy"].to_numpy()
            # do coordinate conversion of (x,y)
            xynps = ax.projection.transform_points(ccrs.Geodetic(), lons, lats)
            ax.scatter(xynps[:,0], xynps[:,1], size, marker='o', alpha=.5, color="green", label="Infected")

            lons = contact_ts["longitude"].to_numpy()
            lats = contact_ts["latitude"].to_numpy()
            size = contact_ts["accuracy"].to_numpy()
            # do coordinate conversion of (x,y)
            xynps = ax.projection.transform_points(ccrs.Geodetic(), lons, lats)
            ax.scatter(xynps[:,0], xynps[:,1], size, marker='o', alpha=.5, color="red", label="Contacts")

        def safe_concat(l):
            if len(l) > 0:
                return pd.concat(l)
            else:
                return pd.DataFrame(columns=['time', 'longitude', 'latitude', 'accuracy'])

        contact_ts = safe_concat([pd.DataFrame(c.trajectory(), columns=['time', 'longitude', 'latitude', 'accuracy'], dtype=np.float64) for c in self])
        # It should not be needed to plot if there are no contacts
        if not len(contact_ts): return None

        t1s = safe_concat([c.t1.pd_frame for c in self if len(c.t1.data) > 0])
        t2s = safe_concat([c.t2.pd_frame for c in self if len(c.t2.data) > 0])

        # We are going to plot addition zoom in plots on clusters of
        # contacts. A cluster of contacts are events seperated by edge
        # of large distance. We say distance is large relative to max blue
        # and green distances
        contact_ts = contact_ts.sort_values(by='time').reset_index(drop=True)

        all = pd.concat([t1s, t2s, contact_ts])

        if len(all) == 0: return None

        # This would be related to window size
        max_separation = max(get_max_dist_meters(t1s), get_max_dist_meters(t2s))
        # We can form a possible cluster iff we make a large step
        edge_lengths = conseq_distance_meters(contact_ts)

        # There will always be at least to global plot
        slack_lon = 0.015
        slack_lat = 0.005

        extends = [(min(all["longitude"])-slack_lon, max(all["longitude"])+slack_lon,
                    min(all["latitude"])-slack_lat, max(all["latitude"])+slack_lat)]

        # For just one contact we zoom in
        if not len(edge_lengths):
            extends.append((min(all["longitude"])-slack_lon/10., max(all["longitude"])+slack_lon/10.,
                            min(all["latitude"])-slack_lat/10., max(all["latitude"])+slack_lat/10.))
        # So will we zoom in?
        elif any(e > 0.5*max_separation for e in edge_lengths):
            # A subplot has different extends
            slack_lon /= 10.
            slack_lat /= 10.
            # Subplots will be for slices based on break points
            bpts = [0] + [p[0] for p in enumerate(edge_lengths, 1) if p[1] > 0.5*max_separation] + [len(contact_ts)]

            for start, end in zip(bpts[:-1], bpts[1:]):
                cluster = contact_ts.iloc[start:end]

                extends.append((min(cluster["longitude"])-slack_lon, max(cluster["longitude"])+slack_lon,
                                min(cluster["latitude"])-slack_lat, max(cluster["latitude"])+slack_lat))

        imagery = OSM()
        fig = plt.figure(figsize=(8, 8))
        # Fill
        nplots = len(extends)
        for idx, extend in enumerate(extends, 1):
            ax = fig.add_subplot(nplots, 1, idx, projection=imagery.crs)
            do_plot(ax, t1s, t2s, contact_ts, extend, imagery=imagery,
                    level=14 if idx == 1 else 16)  # Fine for zoomd

        f = io.BytesIO()
        fig.savefig(f, format=format, quality=95, dpi=dpi)
        f.seek(0)
        plt.close()
        return f.getvalue()


    def plot_interactive(self):
        '''Creates a plot of the contact list using an interactive folium map.'''
        t1s = [c.t1.data for c in self if len(c.t1.data) > 0]
        t2s = [c.t2.data for c in self if len(c.t2.data) > 0]
        trajectories = [c.trajectory() for c in self]

        t1 = np.row_stack(t1s) if t1s else []
        t2 = np.row_stack(t2s) if t2s else []
        trajectory = np.row_stack(trajectories) if trajectories else []

        if len(t1) > 0:
            lon, lat = np.mean(t1, axis=0)[1:3]
        elif len(t2) >0:
            lon, lat = np.mean(t2, axis=0)[1:3]
        else:
            return "No GPS information"

        folium_map = folium.Map(location=[lat, lon], zoom_start=14, control_scale=True, prefer_canvas=True)

        viewer1 = TrajectoryFoliumViewer(t1)
        viewer1.add_folium_markers(folium_map, "blue")

        # Add trajectory 2
        viewer2 = TrajectoryFoliumViewer(t2)
        viewer2.add_folium_markers(folium_map, "green")

        # Add contact points
        viewer3 = TrajectoryFoliumViewer(trajectory)
        viewer3.add_folium_markers(folium_map, "red")

        # Controls for toggle markers
        folium.LayerControl().add_to(folium_map)

        return folium_map._repr_html_()

def good_bin(x, bins=[0,5,10,20,30,50]):
    i=-1
    while x>=bins[i+1]:
        i+=1
        if i>=len(bins)-1:
            break
    return i


def get_max_dist_meters(frame):
    '''Frame[col=["latitude", "longitude", ...]] -> max distance of rows'''
    if not len(frame): return 0

    res = 0
    lat, lon = frame['latitude'].to_numpy(), frame['longitude'].to_numpy()
    for i, (ai, oi) in enumerate(zip(lat, lon)):
        for (aj, oj) in zip(lat[i+1:], lon[i+1:]):
            res = max(res, haversine_distance(ai, oi, aj, oj))

    return res


def conseq_distance_meters(frame):
    '''Frame[col=["latitude", "longitude", ...]] -> distances of conseq rows'''
    lat, lon = frame['latitude'].to_numpy(), frame['longitude'].to_numpy()
    return np.array([haversine_distance(lat[i], lon[i], lat[i+1], lon[i+1])
                     for i in range(len(lat)-1)])
