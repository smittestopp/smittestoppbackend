import pytest
import json
from datetime import datetime
from dateutil.parser import isoparse
from corona.analysis import run_analysis_pipeline
from pprint import pprint

unit_cases = [
        {"case_id": "66",
         "contact_type": "bt",
         "uuid": "dd84433a729411ea80ea42a51fad92d3",
         "time_from": datetime(2020, 4, 10, 10, 1, 0),
         "time_to": datetime(2020, 4, 10, 10, 15, 0), 
         "other_uuids": ["9b55b50c729411ea80ea42a51fad92d3"],  
         "activity": "staying inside",
        }
        ]


@pytest.mark.parametrize("case", unit_cases)
def test_unit(case):
    d = run_analysis_pipeline(case["uuid"], daily_summary=False, output_formats=["dict"], timeFrom=case["time_from"], timeTo=case["time_to"], html_filename_prefix=f"{case['case_id']}_", include_maps="interactive", testing = True)

    for other_uuid in case["other_uuids"]:

        # Check that we identified the contact
        assert other_uuid in d.keys()

        contacts = d[other_uuid][f"{case['contact_type']}_contacts"]

        assert contacts["number_of_contacts"] == 1
        c1 = contacts["contact_details"][0]

        assert isoparse(c1["time_from"]) > case["time_from"]
        assert isoparse(c1["time_to"]) < case["time_to"]

        #if case["activity"]=="staying inside":
        #    assert c1["duration"] == c1["duration_inside"]


@pytest.mark.parametrize("case", unit_cases)
def test_unit_daily(case):
    d = run_analysis_pipeline(case["uuid"], daily_summary=True, output_formats=["html", "dict"], timeFrom=case["time_from"], timeTo=case["time_to"], html_filename_prefix=f"daily_{case['case_id']}_", include_maps="interactive", testing = True)

   
def strip_values(d): 
     for k, v in d.items(): 
         if isinstance(v, dict): 
             strip_values(v) 
         else: 
             d[k] = "" 

@pytest.mark.parametrize("case", unit_cases[:1])
def test_generate_output_structure(case):
    d = run_analysis_pipeline(case["uuid"], daily_summary=True, output_formats=[ "dict"], timeFrom=case["time_from"], timeTo=case["time_to"], html_filename_prefix=f"daily_{case['case_id']}_", include_maps="interactive", testing = True)
    strip_values(d)
    with open('output_structure.json', 'w') as outfile:
        json.dump(d, outfile, indent=4)