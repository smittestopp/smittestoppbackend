import pytest

from datetime import datetime, timedelta
from corona.data import load_azure_data

cases = [
    ("dd84433a729411ea80ea42a51fad92d3", "2020-04-10 12:01:00", "2020-04-10 12:15:00", "still"),
    ("dd84433a729411ea80ea42a51fad92d3", "2020-04-11 15:22:00", "2020-04-11 16:00:00", "on_foot"),
    ("dd84433a729411ea80ea42a51fad92d3", "2020-04-12 10:05:00", "2020-04-12 10:20:00", "still"),
    ("dd84433a729411ea80ea42a51fad92d3", "2020-04-12 13:10:00", "2020-04-12 13:49:00", "on_foot"),
    ("dd84433a729411ea80ea42a51fad92d3", "2020-04-13 13:39:00", "2020-04-13 14:27:00", "vehicle"),
    ("4577ff0a729411ea80ea42a51fad92d3", "2020-04-10 12:55:00", "2020-04-10 13:00:00", "still"),
    ("15e98c5e9be947c7b5a251a93dec0304", "2020-04-10 13:40:00", "2020-04-10 15:00:00", "still"),
    ("82e78c5e5c9245d69c5494db0e89576a", "2020-04-11 07:01:00", "2020-04-11 07:18:00", "on_foot"),
    ("82e78c5e5c9245d69c5494db0e89576a", "2020-04-11 18:05:00", "2020-04-11 21:45:00", "still"),
    ("82e78c5e5c9245d69c5494db0e89576a", "2020-04-11 21:50:00", "2020-04-11 22:05:00", "on_foot"),
    ("a76d3f94768d11eaaf52c2297e005626", "2020-04-07 19:16:16", "2020-04-08 13:25:35", "still"),
    ("a76d3f94768d11eaaf52c2297e005626", "2020-04-08 09:20:54", "2020-04-08 11:00:00", "still"),
    ("64decd0875ee11eaa2e65e8d493bf34f", "2020-04-12 14:00:00", "2020-04-12 17:30:00", "vehicle"),
    ("64decd0875ee11eaa2e65e8d493bf34f", "2020-04-06 19:25:00", "2020-04-06 19:40:00", "vehicle"),
    ("8f47935e5f10441f9a9eaae791fdc8f4", "2020-04-13 14:18:00", "2020-04-13 14:40:00", "vehicle"),
    ("8f47935e5f10441f9a9eaae791fdc8f4", "2020-04-13 14:44:00", "2020-04-13 14:56:00", "vehicle"),
    ("8f47935e5f10441f9a9eaae791fdc8f4", "2020-04-13 15:04:00", "2020-04-13 15:11:00", "vehicle"),
    ("8f47935e5f10441f9a9eaae791fdc8f4", "2020-04-12 18:15:00", "2020-04-13 10:45:00", "still"),
    ("cb6e70a2726d11ea86d7ee3617b084b4", "2020-04-06 06:00:00", "2020-04-12 12:00:00", "still"),
    ("dd84433a729411ea80ea42a51fad92d3", "2020-04-13 13:39:00", "2020-04-13 14:27:00", "vehicle"),
    ("dd84433a729411ea80ea42a51fad92d3", "2020-04-13 09:30:00", "2020-04-13 10:59:00", "vehicle"),
    ("2f9d945e4cca4b26b900acb7b3fefb8f", "2020-04-15 05:40:00", "2020-04-15 07:10:00", "vehicle"),
    ("8fee8c5e3c304ef4acc7d1f694469a35", "2020-04-13 13:03:00", "2020-04-13 15:10:00", "on_foot"),
    ("8fee8c5e3c304ef4acc7d1f694469a35", "2020-04-10 11:40:00", "2020-04-10 12:10:00", "on_foot"),
    ("d152905e8f4a4924a66336801faa3683", "2020-04-14 14:00:00", "2020-04-14 14:40:00", "still"),
    ("25508d5e8e134de9ae9a0555a4dc3943", "2020-04-14 18:00:00", "2020-04-15 07:00:00", "still"),
    ("a0ec8c5ed7ff412fac546363c6b0f21a", "2020-04-13 18:00:00", "2020-04-13 19:10:00", "vehicle")
]

@pytest.mark.parametrize("uuid, time_from, time_to, truth", cases)
def test_speed_sql_function(uuid, time_from, time_to, truth):
    
    time_from = datetime.strptime(time_from, "%Y-%m-%d %H:%M:%S") - timedelta(hours=2)
    time_to = datetime.strptime(time_to, "%Y-%m-%d %H:%M:%S") - timedelta(hours=2)

    time_from = time_from.strftime("%Y-%m-%d %H:%M:%S") 
    time_to = time_to.strftime("%Y-%m-%d %H:%M:%S") 

    data = load_azure_data(
        query="SELECT * FROM getTrajectorySpeed('%s','%s','%s')" % (uuid, time_from, time_to)
    )

    if len(data) > 0: 
        data = data[uuid]
        most_common = data["transport"].mode().iloc[0]
        assert most_common == truth

# @pytest.mark.parametrize("uuid, time_from, time_to, truth", cases)
# def test_other_sql_function(uuid, time_from, time_to, truth):

#     data = load_azure_data(
#         query="SELECT * FROM getOtherstrajectories ('%s','%s','%s', 100, 0, 0) ORDER BY 1,2 ASC" % (uuid, time_from, time_to)
#     )

#     if len(data) > 0: 
#         data = data[uuid]
#         most_common = data["transport"].mode().iloc[0]
#         assert most_common == truth