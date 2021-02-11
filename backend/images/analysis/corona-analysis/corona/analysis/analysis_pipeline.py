from datetime import datetime, timedelta, timezone
import sys
import json
import matplotlib
from threading import current_thread

from corona import logger
from corona.analysis import RiskReport
from corona.analysis.contact_graph import GPSContactGraph, BTContactGraph
from corona.analysis.default_parameters import params
from corona.analysis.logger import log_contacts
from corona.config import __CONFIG__ as config

#from profilehooks import profile
#@profile
def run_analysis_pipeline(patient_uuid, output_formats=["dict"], daily_summary=True,
                          timeFrom=None,
                          timeTo=None,
                          request_id=None,
                          html_filename_prefix="", include_maps="static", testing=False):
    """ Runs the analysis pipeline and returns the risk report.

        :param patient_uuid: UUID of the patient to be analysed
        :param output_format: The output format of the report. Valid options are "dict, html, stdout".
        :param daily_summary: If True, the contacts are aggregated on  a daily basis, otherwise each contact is reported independently._dist_thresh_
        :param timeFrom: The start time of the analysis. If None, the pipeline runs the analysis for the last days as specified in default_parameters.py.
        :param timeTo: The end time of the analysis. If None, UTC now will be used.
        :param html_filename_prefix: Only valid if output_format includes "html". A prefix string that for the filename._dist_thresh_
        :param include_maps: Specifies which types of maps to include in the report. Valid options are  None, "static" or "interactive".
        :param testing: Boolean flag - if true reports also contacts that do not satisfy the criteria defined by FHI
    """

    if request_id:
        context_name = str(request_id)
    else:
        context_name = str(patient_uuid)

    calling_thread = current_thread()
    calling_thread_name = calling_thread.name
    calling_thread.name = context_name
    try:
        # Set parameters
        assert set(output_formats).issubset(("dict", "html", "stdout"))
        patient_uuid = patient_uuid.lower()  # UUIDs are always lower characters by convention
        set_analysis_period(params, timeFrom, timeTo)

        logger.info("Running analysis pipeline with following parameters and config (extracts): "
                    f"Params={json.dumps(params, default=str)} "
                    f"Config={json.dumps(config.loggable_params(), default=str)}")

        # We only render matplotlib images, so we can use the agg backend.
        matplotlib.use('Agg')

        # Build contact graphs
        gps_contact_graph = GPSContactGraph([patient_uuid], params)
        bt_contact_graph = BTContactGraph([patient_uuid], params)

        # Extract contacts results
        gps_results = gps_contact_graph.contacts_with(patient_uuid)
        bt_results = bt_contact_graph.contacts_with(patient_uuid)

        all_results = bt_results + gps_results

        # Gather device infos of uuids in graph
        device_info = gps_contact_graph.node_device_info.copy()
        device_info.update(bt_contact_graph.node_device_info)

        # Log all contacts anonymously
        log_contacts(patient_uuid, all_results.contacts, device_info, add_random_salt=True)

        # Create report
        report = RiskReport(patient_uuid, all_results.contacts, device_info, include_maps, testing)

        # Return report in the requested format
        if "html" in output_formats:
            filename = f"{html_filename_prefix}report_{patient_uuid}_dist_thresh_{params['filter_options']['dist_thresh']}.html"
            report.to_html(filename, daily_summary)
            logger.info("Analysis pipeline finished")
        if "stdout" in output_formats:
            logger.info(report)
            logger.info("Analysis pipeline finished")
        if "dict" in output_formats:
            if daily_summary:
                d = report.to_dict_daily()
            else:
                d = report.to_dict()
            logger.info("Analysis pipeline finished")
            return d
    finally:
        calling_thread.name = calling_thread_name


def set_analysis_period(params, timeFrom, timeTo):
    """ Sets the flags params["timeFrom"] and params["timeTo"] """
    if timeTo is not None:
        params["timeTo"] = timeTo
    else:
        params["timeTo"] = datetime.utcnow().replace(microsecond=0)

    if timeFrom is not None:
        params["timeFrom"] = timeFrom
        params["analysis_duration_in_days"] = (params['timeTo'] - params['timeFrom']).days
    else:
        params["timeFrom"] = (params["timeTo"] - timedelta(days=params["analysis_duration_in_days"])).replace(microsecond=0)

    # Ensure that we work in UTC timezone - this should not really be necessary if we work with
    # time-aware DateTime objects, but letæ's be on the safe side
    params["timeFrom"] = params["timeFrom"].astimezone(timezone.utc)
    params["timeTo"] = params["timeTo"].astimezone(timezone.utc)

    logger.info(f"Analysis period: {params['timeFrom'].isoformat()} - {params['timeTo'].isoformat()}")
