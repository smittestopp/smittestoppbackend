
import pandas as pd

from corona.utils import haversine_distance

# define the function attributing weights to values based on accuracy -----
def weight_accuracy(x, weight_dist_max, weight_dist_min, weight_min_val):
    """ return weight based on accuracy of a given measurement """
    a = 1 / (weight_dist_min - weight_dist_max)
    b = weight_dist_max / (weight_dist_max - weight_dist_min)
    if x >= weight_dist_max:
        w = weight_min_val
    elif weight_dist_max > x > weight_dist_min:
        w = a*x + b
    else:
        w = 1.0
    return w

# define the function computing distance with convolution filtres ---------
def convolution_filtre(path_1, path_2, timestep, weight_dist_max, weight_dist_min,
                       weight_min_val, filtre_size):

    distance = 0
    count_weights = 0
    total_accuracy = 0
    # loop on nearby time-steps
    for ti in range(timestep - int(filtre_size/2), timestep + int(filtre_size/2) + 1):
        # there is no padding, so if we encounter values outside of boundaries, we pass
        if ti < 0 or ti >= path_1.shape[0] or ti >= path_2.shape[0]:
            continue
        # similarly we pass if there are some undefined values
        if path_1[ti,0]==0 or path_1[ti,1]==0 or path_2[ti,0]==0 or path_2[ti,1]==0:
            continue
        # compute weights based on accuracy
        w1 = weight_accuracy(path_1[ti,2], weight_dist_max, weight_dist_min, weight_min_val)
        w2 = weight_accuracy(path_2[ti,2], weight_dist_max, weight_dist_min, weight_min_val)
        # try to replace with nearby values if strong innacuracy
        ti_path_1 = ti
        ti_path_2 = ti
        # check for w1
        if w1==weight_min_val:
            if ti>=1:
                w1_new = weight_accuracy(path_1[ti-1,2], weight_dist_max, weight_dist_min, weight_min_val)
                if w1_new>w1 and path_1[ti-1,0]!=0 and path_1[ti-1,1]!=0:
                    w1 = w1_new
                    ti_path_1 = ti - 1
            if ti<path_1.shape[0]-1:
                w1_new = weight_accuracy(path_1[ti+1,2], weight_dist_max, weight_dist_min, weight_min_val)
                if w1_new>w1 and path_1[ti+1,0]!=0 and path_1[ti+1,1]!=0:
                    w1 = w1_new
                    ti_path_1 = ti + 1
        # check for w2
        if w2==weight_min_val:
            if ti>1:
                w2_new = weight_accuracy(path_2[ti-1,2], weight_dist_max, weight_dist_min, weight_min_val)
                if w2_new>w2 and path_2[ti-1,0]!=0 and path_2[ti-1,1]!=0:
                    w2 = w2_new
                    ti_path_2 = ti - 1
            if ti<path_2.shape[0]-1:
                w2_new =  weight_accuracy(path_2[ti+1,2], weight_dist_max, weight_dist_min, weight_min_val)
                if w2_new>w2 and path_2[ti+1,0]!=0 and path_2[ti+1,1]!=0:
                    w2 = w2_new
                    ti_path_2 = ti + 1
        # compute weights and distances
        count_weights += w1 * w2
        distance += w1*w2*haversine_distance(path_1[ti_path_1,0],path_1[ti_path_1,1],path_2[ti_path_2,0],path_2[ti_path_2,1])
        total_accuracy += w1*w2*(path_1[ti_path_1,2] + path_2[ti_path_2,2])
    # return distance estimations
    if count_weights != 0:
        dist_estimate = distance/count_weights
        dist_min = (distance-total_accuracy)/count_weights
        dist_max = (distance+total_accuracy)/count_weights
        return (dist_estimate, max(0,dist_min), dist_max)
    else:
        return (1e9,1e9,1e9)

    
def convolution(t1, t2, dist_thresh=100, weight_dist_max = 100, weight_dist_min = 10,
                weight_min_val = 0.05, filtre_size = 2):

    if isinstance(t1, pd.DataFrame):
        t1 = t1[["latitude", "longitude", "accuracy"]].to_numpy()

    if isinstance(t2, pd.DataFrame):
        t2 = t2[["latitude","longitude", "accuracy"]].to_numpy()

    # dictionary of edge data -------------------------------------------------
    contact_details = {'timesteps_in_contact': [],
                   'dists': [],
                   'accuracy': [],
                   'locations': [],
                   'dists_min' : [],
                   'dists_max' : []}
    
    # loop on all time steps for the two trajectories -------------------------
    for row_idx in range(t1.shape[0]):
        
        if t1[ row_idx, 0 ] == 0 or t1[ row_idx, 1 ] == 0 or t2[ row_idx, 0 ] == 0 or t2[ row_idx, 1 ] == 0:
            continue
        
        dist, dist_min, dist_max = convolution_filtre(t1, t2, row_idx, weight_dist_max, 
                                                      weight_dist_min, weight_min_val, filtre_size)
        
        if dist_min > dist_thresh:
            continue

        contact_details['timesteps_in_contact'].append(row_idx)
        contact_details['dists'].append(dist)
        contact_details['dists_min'].append(dist_min)
        contact_details['dists_max'].append(dist_max)
        contact_details['accuracy'].append((t1[row_idx,2], t2[row_idx,2]))
        contact_details['locations'].append([t1[row_idx,0],t1[row_idx,1]])

    return contact_details