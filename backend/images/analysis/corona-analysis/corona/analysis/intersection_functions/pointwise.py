import pandas as pd

from corona.utils import haversine_distance

def pointwise(t1, t2, dist_thresh=100):
    """ Computes the pointwise distance between two trajectories. """

    if isinstance(t1, pd.DataFrame):
        t1 = t1[["latitude", "longitude", "accuracy"]].to_numpy()

    if isinstance(t2, pd.DataFrame):
        t2 = t2[["latitude", "longitude", "accuracy"]].to_numpy()

    contact_details = {'timesteps_in_contact': [],
                       'dists': [],
                       'dists_min': [],
                       'dists_max': [],
                       'accuracy': [],
                       'locations': []}


    for row_idx, (d1, d2) in enumerate(zip(t1, t2)):
        lat1, lon1, acc1 = d1
        lat2, lon2, acc2 = d2

        # Skip edge if no location information is available
        if lat1==0 or lon1==0 or lat2==0 or lon2==0:
            continue

        dist = haversine_distance(lat1, lon1, lat2, lon2)

        # Compute min and max distances using the GPS accuracy
        dist_min = max(0, dist-acc1-acc2)
        dist_max = dist+acc1+acc2

        if dist_min>dist_thresh:
            continue

        contact_details['timesteps_in_contact'].append(row_idx)
        contact_details['dists'].append(dist)
        contact_details['dists_min'].append(dist_min)
        contact_details['dists_max'].append(dist_max)
        contact_details['accuracy'].append((acc1, acc2))
        contact_details['locations'].append([lat1, lon1])

    return contact_details
