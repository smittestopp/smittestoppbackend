import numpy as np
import pandas as pd
import shapely.speedups
from shapely.geometry import Polygon, LineString, Point

def extract_trajectories_by_time_intervals(data, time_mode="H"):
    """
    Extract trajectories based on set time intervals, e.g., by hour, minute or second.
    Parameters
    ----------
    data : pandas.DataFrame
        A DataFrame containing the logged events for one person.
    time_mode : string
        The time mode to extract trajectores by.
        The suppported modes are:
            "H"-- for hour
            "HAH" -- half and hour
            "M" -- for minutes
            "S" -- for seconds
            "MS" -- miliseconds
    Returns
    ----------
    List
        A list of trajectories for given person data
    """

    trajectories = [ ]
    
    time_modes = {
        "2H": (2 * 60 * 60),
        "H": (1 * 60 * 60),
        "HAH": (1 * 60 * 30 ),
        "M": (1 * 60),
        "S": (1),
    }

    if time_mode not in time_modes:
        raise NotImplementedError("%s is not implemented!" % time_mode)

    time_divided = np.array(data[ "timeFrom" ].values // time_modes[ time_mode ])

    for trajectory_id, time_value in enumerate(np.unique(time_divided)):
        trajectory = data.iloc[ time_divided == time_value ]
        trajectory.insert(0, "trajectoryId", [ trajectory_id ] * len(trajectory))
        trajectories.append(trajectory)
    
    return trajectories
    
def extract_trajectories_by_chunks(data, chunk_size=10):
    """
    Extract trajectores based on a set size.

    Parameters
    ----------
    data : pandas.DataFrame
        A DataFrame containing the logged events for one person.
    chunk_size : int
        The number of logged events per chunk.

    Returns
    ----------
    List
        A list of trajectories for given person data
    """

    trajectories = [ ]

    for trajectory_id, chunk_index in enumerate(range(0, len(data), chunk_size)):
        trajectory = data.iloc[ chunk_index : chunk_index + chunk_size ]
        trajectory.insert(0, "trajectoryId", [ trajectory_id ] * len(trajectory))
        trajectories.append(trajectory)

    return trajectories

def extract_polygons_from_dilated_areas(trajectory_list, distance=0.001, cap_style=1):
    
    dilated_polygons = []
    
    for trj in trajectory_list:

        trj[ "geometry" ] = [ Point(xy) for xy in zip(trj.longitude, trj.latitude) ]

        if len(trj) > 1:
            line = LineString(list(trj.geometry))
            dilated = line.buffer(distance, cap_style=cap_style)
        else:
            dilated = trj.iloc[0].geometry.buffer(distance, cap_style=cap_style)
        
        dilated_polygons.append(dilated)
        
    return pd.DataFrame(dilated_polygons, columns=["geometry"])
