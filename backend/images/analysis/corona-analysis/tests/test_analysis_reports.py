import pytest
from datetime import datetime
from corona.analysis import run_analysis_pipeline

# Global test settings
#output_formats = ["stdout"]  
output_formats = ["html", "dict"]  # uncomment to get html reports

time1_from = datetime(2020, 3, 31, 12, 0, 0)
time1_to = datetime(2020, 4, 10, 12, 0, 0)
time2_from = datetime(2020, 4, 6, 0, 0, 0)
time2_to = datetime(2020, 4, 16, 23, 0, 0)
cases = [("adabec7272cf11ea94e20edabf845fab", time1_from, time1_to),
         ("51d55d2472d011ea94e20edabf845fab", time1_from, time1_to),
         ("4577ff0a729411ea80ea42a51fad92d3", time2_from, time2_to),
         ("15e98c5e9be947c7b5a251a93dec0304", time2_from, time2_to),
         ("dd84433a729411ea80ea42a51fad92d3", time2_from, time2_to),
         ("40ea8878728e11ea86d7ee3617b084b4", time2_from, time2_to),
         ("82e78c5e5c9245d69c5494db0e89576a", time2_from, time2_to),
         #("a76d3f94768d11eaaf52c2297e005626", time2_from, time2_to),   # Note: This report takes a long time
         ("cb6e70a2726d11ea86d7ee3617b084b4", time2_from, time2_to),
         ("8f47935e5f10441f9a9eaae791fdc8f4", time2_from, time2_to),
         ("64decd0875ee11eaa2e65e8d493bf34f", time2_from, time2_to),
         ("2f9d945e4cca4b26b900acb7b3fefb8f", time2_from, time2_to),
         ("8fee8c5e3c304ef4acc7d1f694469a35", time2_from, time2_to),
         ("0be88c5e5e1a4907a1e12123b8e1677a", time2_from, time2_to),
         ("90868d5eb5e0482a89840663a0a6de56", time2_from, time2_to),
         ("d152905e8f4a4924a66336801faa3683", time2_from, time2_to),
         ("25508d5e8e134de9ae9a0555a4dc3943", time2_from, time2_to),
         ("a0ec8c5ed7ff412fac546363c6b0f21a", time2_from, time2_to),
         ("e86b8d5e8d77449dbbdaf42f6d373f1a", time2_from, time2_to),
         ("8f47935e5f10441f9a9eaae791fdc8f4", time2_from, time2_to)]


@pytest.mark.parametrize("uuid, time_from, time_to", cases)
def test_reports_individual(uuid, time_from, time_to):
    """ Runs a bunch of standard test cases as listed in the Google Drive (File named "test cases"), 
        and creates the html reports with individual contacts"""
    d = run_analysis_pipeline(uuid, output_formats=output_formats, daily_summary=False, 
                          timeFrom=time_from, timeTo=time_to, include_maps="interactive",
                          html_filename_prefix="individual_", testing=True)

    check_individual_report(d)
    

@pytest.mark.parametrize("uuid, time_from, time_to", cases)
def test_reports_daily_summary(uuid, time_from, time_to):
    """ Runs a bunch of standard test cases as listed in the Google Drive (File named "test cases"), 
        and creates the html reports with daily summary """
    d = run_analysis_pipeline(uuid, output_formats=output_formats, daily_summary=True, 
                          timeFrom=time_from, timeTo=time_to, include_maps="static",
                          html_filename_prefix="daily_")    

    check_daily_report(d)
   
    if d is None:
         return None
    
    for uuid in d:
        daily = d[uuid]['daily']
        # As strings
        keys = list(daily.keys())

        as_date = lambda string: datetime.strptime(string, '%Y-%m-%d')
        keys0 = sorted(keys, key=as_date)
        # Going in was ordered
        assert keys == keys0

        daily = d[uuid]['daily']
        # Reassembled it still is
        keys = list(daily.keys())

        assert keys == keys0


def check_individual_report(d):
    for uuid, main_dict in d.items():
        # We now have bt_contacts, gps_contacts, cumulative and version_info
        # The last one is irrelevant
        for key in main_dict:
            if key == 'version_info':
                continue

            contact = main_dict[key]

            assert 0 < contact["cumulative_duration"]                               
            assert 0 < contact["cumulative_risk_score"] 
            assert 0 <= contact["number_of_contacts"]
            assert 0 <= contact["median_distance"] < 100
            assert type(contact['points_of_interest']) == dict
            assert 0 <= contact["cumulative_duration_inside"] 
            assert 0 <= contact["cumulative_duration_outside"]
            assert 0 <= contact["cumulative_uncertain_duration"]
            assert contact["risk_cat"] in ["no","low", "medium", "high", "bt_below_15_min", "gps_only"]
            assert 0 <= contact["bt_close_duration"]
            assert 0 <= contact["bt_relatively_close_duration"]
            assert 0 <= contact["bt_very_close_duration"]
                  
            if "contact_details" in contact.keys():
                for contact_detail in contact["contact_details"]:
                    assert 0 < contact_detail["duration"] 
                    assert contact_detail["time_from"] < contact_detail["time_to"]
                    assert 0 <= contact_detail["median_distance"] < 100
                    assert 0 <= contact_detail["average_distance"] < 100
                    assert 0 <= contact_detail["average_accuracy"]
                    assert 0 <= contact_detail["duration_inside"] 
                    assert 0 <= contact_detail["duration_outside"]
                    assert 0 <= contact_detail["uncertain_duration"]
                    total_duration = (contact_detail["duration_inside"] + contact_detail["duration_outside"] + contact_detail["uncertain_duration"])  
                    if key == 'gps_contacts' or key == 'bt_contacts':
                        assert abs(contact_detail["duration"] - total_duration) < 0.00001   



def check_daily_report(d):
    for uuid, main_dict in d.items():
        for dict_type, sub_dict in main_dict.items():
            if dict_type == "cumulative":
                gps_bt_cummulative_risk_score = 0 
                for sub_type, summary_dict in sub_dict.items():
                    if sub_type in ["gps_contacts", "bt_contacts"]:
                        assert 0 <= summary_dict["cumulative_risk_score"]
                        gps_bt_cummulative_risk_score += summary_dict["cumulative_risk_score"]                        
                        assert 0 <= summary_dict["cumulative_duration"]
                    elif sub_type=="all_contacts":
                        assert summary_dict["risk_cat"] in ["no","low", "medium", "high", "bt_below_15_min", "gps_only"]
                        for x in [x for k,x in summary_dict['points_of_interest'].items()]:
                            assert 0 <= x
                        l = [x for k,x in summary_dict['points_of_interest'].items()]
                        if len(l) > 1:
                            assert not 'N/A' in l
                        assert 0 <= summary_dict["number_of_contacts"]
                # Check that at least one of the risk score for BT or GPS is larger than zero.                        
                assert gps_bt_cummulative_risk_score > 0
            if dict_type == "daily":
                for day, sub_daily_dict in sub_dict.items():
                    for sub_type, summary_dict in sub_daily_dict.items():
                        if sub_type == "all_contacts":
                           if "median_distance" in summary_dict:
                               assert 0 <= summary_dict["median_distance"] < 100 
                           for x in [x for k,x in summary_dict['points_of_interest'].items()]:
                               assert 0 <= x
                           l = [x for k,x in summary_dict['points_of_interest'].items()]
                           if len(l) > 1:
                               assert not 'N/A' in l
                        if sub_type in ["gps_contacts", "bt_contacts"]:
                           assert 0 <= summary_dict["number_of_contacts"]
                           assert 0 <= summary_dict["cumulative_duration"]
                           if "median_distance" in summary_dict:
                               assert 0 <= summary_dict["median_distance"] < 100 
                           if sub_type == "bt_contacts":
                               epsi = 0.0
                               assert 0 <= summary_dict["bt_close_duration"] <= summary_dict["cumulative_duration"]+epsi
                               assert 0 <= summary_dict["bt_relatively_close_duration"] <= summary_dict["cumulative_duration"]+epsi
                               assert 0 <= summary_dict["bt_very_close_duration"] <= summary_dict["cumulative_duration"]+epsi

