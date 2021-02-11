import numpy as np
import multiprocessing
import datetime
import more_itertools as mit
import pandas as pd

from corona.utils import union_of_time_stamps, duration_of_contact, convert_seconds
from corona.analysis.default_parameters import params
from corona.analysis.trajectory.parser import TrajectoryParser, transports_preprocessing
from corona.preprocessing.trajectory import extract_trajectories_by_time_intervals, extract_polygons_from_dilated_areas
from corona.map.poi import get_pois_contacted_with_points

class POI(object):

    # functions to call -----------------------------------------------------------------------

    def __init__(self, t1, t2, contact_details, duration, duration_with_gps):
        """ The attributes are the same than the ones of a Contact object """
        self.t1 = t1
        self.t2 = t2
        self.cd = contact_details

        self.duration_with_gps = duration_with_gps
        # The duration has to be the one of the GPS contacts, even for a BT contact, since we relate it to some GPS duration
        self.duration = duration

        self._pois = None
        self._filtered_pois = None

    def __str__(self):

        if self._pois == None:
            return "Points of interest not computed or no data available."

        points_of_interest, inside, outside, uncertain = self._pois
        formatted_pois = {m: convert_seconds(d) for m, d in pois.items()}
        s = f"Points of interest: {formatted_pois},\n"
        s+= f"Total duration inside: {inside},\n"
        s+= f"Total duration outside: {outside},\n"
        s+= f"Uncertain duration: {uncertain}"

        return s

    def pois(self):
        """ Returns a tuple with the dict of points of interest, and duration inside, outside, uncertain """
        if self._pois is not None:
            return self._pois

        if len(self.cd['locations']) == 0 or self.duration == 0 or self.duration_with_gps == 0:
            self._pois = {'N/A' : self.duration}, 0, 0, self.duration
            return {'N/A' : self.duration}, 0, 0, self.duration

        self._pois = self.get_outputs_from_dict()

        return self._pois

    def filtered_pois(self, threshold_prop=params["pois_options"]["proportion_threshold"], threshold_time=params["pois_options"]["duration_threshold"],
                      long_threshold_time=params["pois_options"]["long_duration_threshold"], keep_uncertain=params["pois_options"]["keep_uncertain"]):
        """
        Returns the most common points of interest, and duration inside, outside, uncertain
        threshold_prop: returned pois must account to at least xx% of total inside time
        threshold_time: returned pois must account to at least xx seconds
        """
        if self._filtered_pois is not None:
            return self._filtered_pois

        if len(self.cd['locations'])==0 or self.duration == 0 or self.duration_with_gps == 0:
            self._filtered_pois = {'N/A' : self.duration}, 0, 0, self.duration
            return {'N/A' : self.duration}, 0, 0, self.duration

        pois, inside_time, outside_time, uncertain_time = self.pois()
        total_time = inside_time
        # (!) Note that we do not take into account for filtering outside/uncertain time
        if keep_uncertain:
            filtered_pois = {place: dur for place, dur in pois.items() if ((dur>=threshold_prop*total_time and dur>=threshold_time) or (dur>=long_threshold_time)) and place != 'N/A'}
        else:
            filtered_pois = {place: dur for place, dur in pois.items() if place != 'uncertain' and place != 'N/A' and ((dur>=threshold_prop*total_time and dur>=threshold_time) or (dur>=long_threshold_time))}

        if filtered_pois == {}:
            filtered_pois = {max(pois, key = pois.get) : pois[max(pois, key = pois.get)]}

        self._filtered_pois = filtered_pois, inside_time, outside_time, uncertain_time

        return self._filtered_pois

    # methods used to compute the points of interest -------------------------------------------

    def build_dataframes(self):
        """ Creates a dataframe and its chunks for feeding it to the PoI detection """
        timesteps_contact = [t for t in self.cd['contact_timestamps']]
        longitudes_contact = [pos[0] for pos in self.cd['locations']]
        latitudes_contact = [pos[1] for pos in self.cd['locations']]
        accuracy_contact = [(acc[0]+acc[1])/2 for acc in self.cd['accuracy']]
        transport_contact_1 = self.t1.get_mode_of_transport(timesteps_contact)
        transport_contact_2 = self.t2.get_mode_of_transport(timesteps_contact)
        accuracy_radius = [accuracy_radius_factor(t[0],t[1])*accuracy_contact[i] for i,t in enumerate(zip(transport_contact_1,transport_contact_2))]
        # build the main dataframe
        trajectory_df = pd.DataFrame({'timeFrom' : timesteps_contact, 'longitude' : longitudes_contact, 'latitude' : latitudes_contact,
                                      'accuracy' : accuracy_contact, 'radius' : accuracy_radius}, columns = ['timeFrom', 'longitude', 'latitude', 'accuracy', 'radius'])
        df_poi = trajectory_df.loc[trajectory_df.latitude !=  0]
        df_poi.index = range(len(df_poi))
        timesteps_contact = df_poi.timeFrom.tolist()
        # calls the trajectory transport modes analysis function and update dataframe
        is_inside, is_onfoot, is_uncertain = transports_preprocessing(self.t1, self.t2, timesteps_contact)
        df_poi.insert(5, 'inside_transport', is_inside, True)
        df_poi.insert(6, 'uncertain', is_uncertain, True)
        df_poi.insert(7, 'on_foot', is_onfoot, True)
        # get the df for point of interests and cut it into 'hour' chunks
        trajectory_per_hour = extract_trajectories_by_time_intervals(df_poi, time_mode = "2H") # this needed the column to be named timeFrom
        df_poi = df_poi.rename(columns = {'timeFrom' : 'time'}) # rename back to time
        for ii in range(len(trajectory_per_hour)):
            trajectory_per_hour[ii] = trajectory_per_hour[ii].rename(columns = {'timeFrom' : 'time'})
        return df_poi, trajectory_per_hour

    def call_mapmatching(self, types_of_amenities = params["pois_options"]["types_of_amenities"]):
        """ Calls the PoI detection on the points that are on_foot/still by chunks of 2-hour for frequencies to make more sense """
        df_poi, trajectory_per_hour = self.build_dataframes()
        list_of_dataframes = []

        for ii in range(len(trajectory_per_hour)):

            if trajectory_per_hour[ii].to_numpy().tolist() != []:
                contact_df, poi_df, contact_counts = get_pois_contacted_with_points(trajectory_per_hour[ii], types_of_amenities, padding=-1, max_padding=50, column_name="radius")
                if ii>0:
                    contact_df.index = range(trajectory_per_hour[ii-1].index[-1]+1, len(contact_df.index) + trajectory_per_hour[ii-1].index[-1]+1)
                    trajectory_per_hour[ii].index = range(trajectory_per_hour[ii-1].index[-1]+1, trajectory_per_hour[ii-1].index[-1]+1 + len(trajectory_per_hour[ii].index))
                contact_df = self._eliminate_suspicious_pois(contact_df, df_poi)
                output_points = contact_df[['trajectoryId', 'time', 'longitude', 'latitude', 'accuracy', 'contacted', 'selected_poi', 'inside_transport', 'uncertain', 'on_foot']]
                output_points.insert(8, 'inside_building', [(trajectory_per_hour[ii].on_foot[i] and output_points.contacted[i]) for i in output_points.index.tolist()], True)
                output_points = output_points.rename(columns = {'selected_poi' : 'poi'})
            else:
                output_points = trajectory_per_hour[ii]
                output_points.insert(8, 'inside_building', [False for i in output_points.index.tolist()], True)

            if len(output_points.loc[output_points.inside_building == False]) != len(output_points):
                tags = [poi_df.loc[poi_df.id == int(output_points.poi[kk])]['tags'].tolist()[0] if output_points.inside_building[kk]==True else 'not_contacted' for kk in output_points.index.tolist()]
                building_types = get_types_from_tags(tags)
                output_points.insert(9, 'building_type', building_types, True)
            else:
                output_points.insert(9, 'building_type', ['not_contacted' for i in output_points.index.tolist()], True)

            list_of_dataframes.append(output_points)

        return pd.concat(list_of_dataframes)

    def compute_durations(self):
        """ Input a dataframe with the location information and Output a dict with duration in each category """
        dict_pois = {'outside' : 0, 'inside_transport' : 0, 'uncertain' : 0}
        df = self.call_mapmatching()
        total_inside_time = 0
        total_outside_time = 0

        # inside a PoI
        buildings_types = [el for el in list(set(df.building_type.tolist())) if el != 'not_contacted']
        buildings_indices = [df.loc[df.building_type==build_type].index.tolist() for build_type in buildings_types]
        for jj in range(len(buildings_types)):
            time_inside = 0
            for list_of_indices in consecutive_elements(buildings_indices[jj]):
                time_inside += duration_of_contact(df.time.tolist(), list_of_indices)
            if buildings_types[jj] in dict_pois:
                dict_pois[buildings_types[jj]] += time_inside
            else:
                dict_pois[buildings_types[jj]] = time_inside
            total_inside_time += time_inside

        # inside a Transport
        for list_of_indices in consecutive_elements(df.loc[df.inside_transport == True].index.tolist()):
            transport_time = duration_of_contact(df.time.tolist(), list_of_indices)
            total_inside_time += transport_time
            dict_pois['inside_transport'] += transport_time

        # Not in a Transport, nor uncertain, nor in a building: for example still or on_foot but not in a building
        for list_of_indices in consecutive_elements(df.loc[df.uncertain == False].loc[df.inside_transport == False].loc[df.inside_building == False].index.tolist()):
            outside_time = duration_of_contact(df.time.tolist(), list_of_indices)
            total_outside_time += outside_time
            dict_pois['outside'] += outside_time

        all_indices = [i for i in df.index.tolist()]
        uncertain_duration = max(duration_of_contact(df.time.tolist(), all_indices) - total_inside_time - total_outside_time, 0)
        uncertain_duration += (self.duration - self.duration_with_gps) # this has no impact on GPS contacts
        dict_pois['uncertain'] = uncertain_duration

        if uncertain_duration + total_outside_time + total_inside_time == 0:
            print("Duration of all PoI was 0")
            return {'uncertain' : self.duration, 'outside' : 0, 'inside_transport' : 0}

        # This will ensure that all the added duration pieces will add to the full duration, as this is never guaranteed to happen otherwise
        ratio_factor = self.duration / (uncertain_duration + total_outside_time + total_inside_time)
        dict_pois = {item: ratio_factor * dict_pois[item] for item in dict_pois}
        # Rounding errors with the ratio_factor multiplication can still lead to things not summing up correctly
        dict_pois['uncertain'] = max(0, self.duration - sum([dur for item,dur in dict_pois.items() if item != 'uncertain']))

        return dict_pois

    def get_outputs_from_dict(self):
        """ Get duration outside, inside and 'uncertain' from the dictionary of points of interest """

        dict_pois = self.compute_durations()

        # compute the durations of contact in each of the three categories
        codelist = [b for a,b in enumerate(dict_pois)]
        length_contact_inside = 0
        for code in codelist:
            if code!='outside' and code!='uncertain':
                length_contact_inside += dict_pois[code]
        length_contact_uncertain = dict_pois['uncertain']
        length_contact_outside = dict_pois['outside']


        # removes entry where the value is 0
        dict_pois = {item : dict_pois[item] for item in dict_pois if dict_pois[item] != 0}

        return dict_pois, length_contact_inside, length_contact_outside, length_contact_uncertain

    # static methods ----------------------------------------------------------------------------------------

    @staticmethod
    def _eliminate_suspicious_pois(contact_df, df_poi, min_frequency = params["pois_options"]["pois_filtration_frequency"],
                                   min_duration = params["pois_options"]["pois_filtration_duration"]):
        """ We filter out identified poi with low frequency and small duration  """
        set_supposed_pois = list(set(contact_df.selected_poi.tolist()))
        pois_frequency_list = [(len(contact_df.loc[contact_df.selected_poi == item].selected_poi.tolist())>min_frequency) for item in set_supposed_pois]
        suspicious_pois = [poi for poi,x in zip(set_supposed_pois, pois_frequency_list) if x==False]
        suspicious_indices_lists = [contact_df.loc[contact_df.selected_poi == item].index.tolist() for item in suspicious_pois]
        very_suspicious_indices = []
        for suspicious_indices in suspicious_indices_lists:
            computed_time = duration_of_contact(df_poi.time.tolist(), suspicious_indices)
            if computed_time < min_duration:
                very_suspicious_indices += [suspicious_indices]
        for index in very_suspicious_indices:
            contact_df.loc[index, 'contacted'] = False
        return contact_df


def accuracy_radius_factor(t1,t2,factor=params["pois_options"]['accuracy_radius_factor']):
    """ Decreases the PoI search radius depending on the transport mode """
    if t1=='still' and t2=='still':
        return factor[0]
    if (t1=='still' or t2=='still') and (t1=='N/A' or t2=='N/A' or t1=='on_foot' or t2=='on_foot'):
        return factor[1]
    if (t1=='on_foot' or t2=='on_foot') and (t1=='N/A' or t2=='N/A' or t1=='on_foot' or t2=='on_foot'):
        return factor[2]
    else:
        return factor[3]

def get_types_from_tags(tags, dict_of_buildings = params["pois_options"]['dict_of_buildings']):
    """ Convert the various tags from open street map into standardised building names """
    building_types = []
    for tag in tags:
        if tag == 'not_contacted':
            building_type = 'not_contacted'
        elif 'amenity' in tag:
            building_type = tag['amenity']
            if building_type in dict_of_buildings:
                building_type = dict_of_buildings[building_type]
            else:
                building_type = 'other_buildings'
        elif 'building' in tag:
            building_type = tag['building']
            if building_type == 'yes':
                if 'building:type' in tag:
                    building_type = tag['building:type']
                elif 'building:use' in tag:
                    building_type = tag['building:use']
                else:
                    building_type = 'other_buildings'
            if building_type in dict_of_buildings:
                building_type = dict_of_buildings[building_type]
            else:
                building_type = 'other_buildings'
        elif 'shop' in tag:
            building_type = 'shop'
        elif 'public_transport' in tag:
            building_type = 'public_transport_stop'
        elif 'office' in tag:
            building_type = 'office_building'
        else:
            building_type = 'other_buildings'
        building_types.append(building_type)
    return building_types

def consecutive_elements(l):
    """
    Split a list into lists of consecutive indices
    For example [0,1,2,4,5,10] -> [[0,1,2],[4,5],[10]]
    """
    if l == []:
        return []
    else:
        ll = []
        ll.append([l[0]])
        current_j = 0
        for i in range(1,len(l)):
            if l[i] == l[i-1]+1:
                ll[current_j].append(l[i])
            else:
                current_j+=1
                ll.append([l[i]])
        return ll
