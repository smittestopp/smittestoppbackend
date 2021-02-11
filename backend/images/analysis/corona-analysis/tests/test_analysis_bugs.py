import pytest
from datetime import datetime
from corona.analysis import run_analysis_pipeline, default_parameters

# Global test settings
output_formats = ["html"]  # uncomment to get html reports

time_from = datetime(2020, 4, 9, 12, 0, 0)
time_to = datetime(2020, 4, 11, 18, 0, 0)
cases = [("82e78c5e5c9245d69c5494db0e89576a", time_from, time_to)]
@pytest.mark.parametrize("uuid, time_from, time_to", cases)
def xtest_bugs(uuid, time_from, time_to):
    default_parameters.params["filter_options"]["dist_thresh"] = 10
    run_analysis_pipeline(uuid, output_formats=output_formats, timeFrom=time_from, timeTo=time_to, include_maps="interactive", html_filename_prefix="bugs_")
