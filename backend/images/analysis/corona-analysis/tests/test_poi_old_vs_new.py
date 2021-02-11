import pytest
import time
from collections import Counter
from pandas._testing import assert_frame_equal

from corona.data import load_azure_data
import corona.preprocessing.trajectory as trj
import corona.map.poi as poi

from datetime import datetime

time1_from = datetime(2020, 3, 31, 12, 0, 0)
time1_to = datetime(2020, 4, 10, 12, 0, 0)
# time2_from = datetime(2020, 4, 6, 0, 0, 0)
# time2_to = datetime(2020, 4, 16, 23, 0, 0)

test_cases = [
    #("15e98c5e9be947c7b5a251a93dec0304", "2020-04-11 06:40:30", "2020-04-11 10:53:47"), # missing uuid for now
    #("15e98c5e9be947c7b5a251a93dec0304", "2020-04-11 06:40:30", "2020-04-11 11:07:57"),  # missing uuid for now
    #("97ea8c5e72ae4b5892e4deeb0d4a095a", "2020-04-11 06:40:30", "2020-04-11 10:53:47"), # missing uuid for now
    # TODO: Agree to disagree?
    # ("8fee8c5e3c304ef4acc7d1f694469a35", "2020-04-14 15:23:13", "2020-04-14 20:45:21"),
    #("8f47935e5f10441f9a9eaae791fdc8f4", "2020-04-13 15:23:06", "2020-04-13 21:48:06"), # missing uuid for now
    #("2539935e2a8446efaaae9c52e143370b", "2020-04-13 15:23:06", "2020-04-13 21:48:06"), # missing uuid for now
    # Additional, time-consuming
    # ("0be88c5e5e1a4907a1e12123b8e1677a", time2_from, time2_to),
    # ("90868d5eb5e0482a89840663a0a6de56", time2_from, time2_to),
    # ("d152905e8f4a4924a66336801faa3683", time2_from, time2_to),
    # ("25508d5e8e134de9ae9a0555a4dc3943", time2_from, time2_to),
    # ("40ea8878728e11ea86d7ee3617b084b4", time2_from, time2_to),
    #("a0ec8c5ed7ff412fac546363c6b0f21a", time2_from, time2_to),
    #("e86b8d5e8d77449dbbdaf42f6d373f1a", time2_from, time2_to),
    ("adabec7272cf11ea94e20edabf845fab", time1_from, time1_to),
    #("51d55d2472d011ea94e20edabf845fab", time1_from, time1_to),
    #("4577ff0a729411ea80ea42a51fad92d3", time2_from, time2_to),
    #("dd84433a729411ea80ea42a51fad92d3", time2_from, time2_to),
    #("82e78c5e5c9245d69c5494db0e89576a", time2_from, time2_to),
]


types_of_amenities = ['all_buildings', 'amenity_all', 'public_transport', 'offices', 'shop_generalstores']


@pytest.mark.parametrize("uuid, time_from, time_to", test_cases)
def test_similarity(uuid, time_from, time_to):
    new_t_start = time.time()
    contact_df_new, poi_df_new, contact_counts_new = new_get_pois_contacted_with_points(uuid, time_from, time_to, False)
    new_t_end = time.time()

    old_t_start = time.time()
    contact_df_old, poi_df_old, contact_counts_old = old_get_pois_contacted_with_points(uuid, time_from, time_to)
    old_t_end = time.time()

    new_t_mt_start = time.time()
    contact_df_new_mt, poi_df_new_mt, contact_counts_new_mt = new_get_pois_contacted_with_points(uuid, time_from, time_to, True)
    new_t_mt_end = time.time()

    print("")
    print("Time for the new method    (s) = ", (new_t_end - new_t_start))
    print("Time for the old method    (s) = ", (old_t_end - old_t_start))
    print("Time for the new method mt (s) = ", (new_t_mt_end - new_t_mt_start))

    assert_frame_equal(contact_df_new, contact_df_new_mt)
    assert_frame_equal( poi_df_new, poi_df_new_mt)

    assert_frame_equal(contact_df_old, contact_df_new)
    assert_frame_equal(poi_df_old, poi_df_new)

    assert ((contact_counts_old - contact_counts_new) == Counter()) and (
                (contact_counts_new - contact_counts_old) == Counter())
    assert ((contact_counts_new - contact_counts_new_mt) == Counter()) and (
                (contact_counts_new_mt - contact_counts_new_mt) == Counter())


def old_get_pois_contacted_with_points(user, start_time, end_time):
    data = load_data(user, start_time, end_time)
    tr = trj.extract_trajectories_by_chunks(data[user], chunk_size=len(data[user]))
    contact_df_1, poi_df_1, contact_counts_1 = poi.get_pois_contacted_with_points(
        tr[0], types_of_amenities, -1, 100, column_name="accuracy")

    return contact_df_1, poi_df_1, contact_counts_1


def new_get_pois_contacted_with_points(user, start_time, end_time, mt=True):
    data = load_data(user, start_time, end_time)
    tr = trj.extract_trajectories_by_chunks(data[user], chunk_size=len(data[user]))
    contact_df_1, poi_df_1, contact_counts_1 = poi.get_pois_contacted_with_points_v3(
        tr[0], types_of_amenities, -1, 100, column_name="accuracy", mt=mt)

    return contact_df_1, poi_df_1, contact_counts_1


def load_data(user, start_time, end_time):
    query = "select * from getTrajectorySpeed('%s', '%s', '%s')" % (user, start_time, end_time)
    data = load_azure_data(query=query, outlier_threshold=100)

    return data
