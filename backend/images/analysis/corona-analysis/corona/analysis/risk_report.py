
from jinja2 import Environment, PackageLoader, select_autoescape
import datetime

import corona
from corona import logger
from corona.analysis.default_parameters import params
from corona.utils import convert_seconds, default_to_regular
from corona.analysis.contact_list import ContactList
from corona.analysis.dict_filter import fhi_filter_dict
from corona.analysis.dict_filter import nested_dict


class RiskReport(object):
    """ Class takes a contact graph from which it can create risk report
    from user ids. """

    def __init__(self, uuid, contacts, device_info, include_maps=None, testing = False):
        """ Creates a risk report for the provided uuid.

        :param patient_uuid: UUID of the patient for who to create the report.
        :param graph_contact_results: A GraphContactResult object containing all contact information
        :param device_info: dict uuid -> List of device info tuples
        :param include_maps: Specifies which types of maps to include in the report. Valid options are  None, "static" or "interactive".
        :param testing: If true, reports will contain all contacts (i.e. code is in testing mode)
        """

        self.uuid = uuid
        self.contacts = contacts
        self.device_info = device_info
        self.include_maps = include_maps
        self.testing = testing

    def __str__(self):
        s = ""

        for (uuid1, uuid2), contact_list in self.contacts.items():
            s += "\n" + "="*80 + "\n"
            s += f"Person {uuid2} has been in contact with {uuid1}\n"
            s += str(contact_list)
            s += "="*80 + "\n"

        return s

    def to_dict(self):
        """ Returns a dictionary with the information from the report with each contact listed individually

        :return: A dictionary of the form:

        {<<uuid of contact>>: {
            'gps_contacts' : <<output of to_dict() call on gps contact list>> (if existing),
            'bluetooth_contacts' : <<output of to_dict() call on BT contact list>> (if existing),
            'bar_plot' : <<bar plot containing summary of gps and bluetooth contact details>>
            ...
            }
        <<uuid of contact>>: {
            'gps_contacts' : <<output of to_dict() call on gps contact list>> (if existing),
            'bluetooth_contacts' : <<output of to_dict() call on BT contact list>> (if existing),
            'bar_plot' : <<bar plot containing summary of gps and bluetooth contact details>>,
        ...
        }
        """
        dic = nested_dict()
        for (uuid1, uuid2), contact_list in self.contacts.items():
            if not contact_list.include_in_report() and not self.testing:
                continue
            gps_contacts = contact_list.filter(contact_type="gps")
            bt_contacts = contact_list.filter(contact_type="bluetooth")
            if not gps_contacts.empty():
                dic[uuid2]['gps_contacts'] = gps_contacts.to_dict(include_plots = self.include_maps,include_hist=True)
            if not bt_contacts.empty():
                dic[uuid2]['bt_contacts'] = bt_contacts.to_dict(include_plots = self.include_maps)
            dic[uuid2]['cumulative'] = contact_list.to_dict(include_individual_contacts=False, include_bar_plot=self.include_maps)

        # Sign it off
        # NOTE: version info should be top level but perhpas too many
        # things on our as well as FHI side depend on assumption that dic.keys()
        # is only uuid
        for uuid in dic.keys():
            dic[uuid]['version_info']['pipeline'] = corona.__VERSION__
            dic[uuid]['version_info']['device'] = self.device_info[uuid]
        return dic


    def to_dict_daily(self):
        """ Returns a dictionary representation of the report where contacts are aggregated on a daily basis.

        :return: A dictionary of the form:

        {<<uuid of contact>>: {
            "bluetooth_cumulative_risk_score": 10.0,
            "gps_cumulative_risk_score": 10.0,
            "categorical_risk": "medium",
            "bluetooth_cumulative_duration": 210.0,
            "gps_cumulative_duration": 210.0,
            "number_of_contacts": 3,
            "points_of_interest": "residential, school",

            "2020-04-10": {
                'gps_contacts' : <<output of to_dict() call on gps contact list>> (if existing),
                'bluetooth_contacts' : <<output of to_dict() call on BT contact list>> (if existing),
                'bar_plot' : <<bar plot containing summary of gps and bluetooth contact details>>
                },
            "2020-04-11": { ...
            }
        }
        <<uuid of contact>>: {
            "bluetooth_cumulative_risk_score": 10.0,
            ...
        ...
        }
        """

        # Create a default dic where we can append without creating keys
        dic = nested_dict()

        n = 0
        N = len(self.contacts.keys())

        for (_, uuid2), contact_list in self.contacts.items():

            logger.info(f"Generating report {n+1}/{N}")
            n += 1

            if not contact_list.include_in_report() and not self.testing:
                logger.info("Contact does not match the FHI requirements... skipping")
                continue
            logger.info("Contact matches the FHI requirements... adding to report")
            gps_contacts = contact_list.filter(contact_type="gps")
            bt_contacts = contact_list.filter(contact_type="bluetooth")
            dic[uuid2]["cumulative"]["all_contacts"] = contact_list.to_dict(include_individual_contacts=False, include_bar_plot=True)
            dic[uuid2]["cumulative"]['gps_contacts'] = gps_contacts.to_dict(include_individual_contacts=False,include_hist=True)
            dic[uuid2]["cumulative"]['bt_contacts'] = bt_contacts.to_dict(include_individual_contacts=False)

            daily_contacts = contact_list.split_by_days()
            for day, contact_list_day in daily_contacts.items():
                # After splitting we need to check again that all contacts have the required min_duration
                gps_contacts_day = contact_list_day.filter(contact_type="gps",min_duration=params["min_duration"])
                bt_contacts_day = contact_list_day.filter(contact_type="bluetooth",min_duration=params["bt_min_duration"])
                all_contacts_day = ContactList(gps_contacts_day + bt_contacts_day)
                dic[uuid2]['daily'][day.isoformat()]['all_contacts'] = all_contacts_day.to_dict(include_individual_contacts=False, include_bar_plot=False, include_summary_plot = self.include_maps)
                dic[uuid2]['daily'][day.isoformat()]['gps_contacts'] = gps_contacts_day.to_dict(include_individual_contacts=False,include_hist=True)
                dic[uuid2]['daily'][day.isoformat()]['bt_contacts'] = bt_contacts_day.to_dict(include_individual_contacts=False)

            # Enrich the cumulative info for uuid2 by how many days were spent with _
            daily = dic[uuid2]['daily']
            gps_days = set(day for day in daily if daily[day]['gps_contacts']['number_of_contacts'])
            bt_days = set(day for day in daily if daily[day]['bt_contacts']['number_of_contacts'])
            contact_days = gps_days | bt_days

            dic[uuid2]['cumulative']['all_contacts']['days_in_contact'] = len(contact_days)
            dic[uuid2]['cumulative']['gps_contacts']['days_in_contact'] = len(gps_days)
            dic[uuid2]['cumulative']['bt_contacts']['days_in_contact'] = len(bt_days)

        # defaultdict to defaultdict
        dic = fhi_filter_dict(dic)
        # Sign it off
        # NOTE: version info should be top level but perhpas too many
        # things on our as well as FHI side depend on assumption that dic.keys()
        # is only uuid
        for uuid in dic.keys():
            dic[uuid]['version_info']['pipeline'] = corona.__VERSION__
            dic[uuid]['version_info']['device'] = self.device_info[uuid]

        # NOTE: at this point ordering of entries in dic is not guaranteed
        # to be the same as in original dic (where events where ordered by time)
        dic = default_to_regular(dic)

        # Sort daily
        # {uuid: {'cumulative': ...,
        #         'daily': {'date0': x,
        #                   'date1': y}}}
        as_date = lambda string: datetime.datetime.strptime(string, '%Y-%m-%d')
        # Assure ordering of dates
        uuids = list(dic.keys())
        for uuid in uuids:
            dates = dic[uuid]['daily'].keys()  # As strings
            dic[uuid]['daily'] = {date: dic[uuid]['daily'][date] for date in sorted(dates, key=as_date)}

        return dic


    def to_html(self, filename, daily_summary=False):
        """ Generates a HTML representation of the report and saves it to filename

        :param filename: The filename where the report should be saved.
        :param daily_summary: If True, the contacts are aggregated on  a daily basis, otherwise each contact is reported independently._dist_thresh_
        """

        env = Environment(
        loader=PackageLoader('corona', 'templates'),
        autoescape=select_autoescape(['html', 'xml'])
        )
        # Expose some functions to the template engine
        env.globals['convert_seconds'] = convert_seconds
        env.globals['set'] = set

        if daily_summary:
            #self.include_maps=False
            data = self.to_dict_daily()
            template = env.get_template('risk_report_daily.html')
        else:
            data = self.to_dict()
            template = env.get_template('risk_report.html')

        if data:
            uuids = iter(data.keys())
            pipe_version = data[next(uuids)]['version_info']['pipeline']
            # Sanity check that we have same pipeline
            assert all(pipe_version == data[uuid]['version_info']['pipeline'] for uuid in uuids)
        else:
            # Empt data's pipa version is
            pipe_version = corona.__VERSION__

        html = template.render(
                patient=self.uuid,
                pipe_version=pipe_version,
                patient_device=self.device_info[self.uuid],
                data=data,
                analysis_options=params)

        with open(filename, "w") as f:
            f.write(html)
