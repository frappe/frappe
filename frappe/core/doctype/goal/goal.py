# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.desk.form.meta import get_meta
from frappe.utils import add_to_date, add_hours, add_days, add_weeks, add_months, add_years, formatdate

class Goal(Document):
    def fetch_fields(self):
        if not self.source:
            return

        meta = frappe.get_meta(self.source)

        return {
            "source_filter": meta.get_list_fields(),
            "based_on": [d.fieldname for d in meta.get_numeric_fields() +
                meta.get_currency_fields()]
        }

    def validate(self):
        # Check for conflicting goals
        pass

    def on_update(self):
        form_meta = get_meta(self.source)
        form_meta.load_goals()

def get_doc_count(doctype, filters = {}, time_slot = []):
    if filters is None:
        filters = {}
    if time_slot:
        filters["creation"] = ('between', time_slot)
    return len(frappe.get_list(doctype, filters=filters))

def get_value_aggregation(doctype, field, filters = {}, time_slot = []):
    if filters is None:
        filters = {}
    if time_slot:
        filters["creation"] = ('between', time_slot)
    field_value_list = [d[field] for d in frappe.get_list(doctype,
        fields = [field], filters=filters)]

    return sum(field_value_list)

def get_count_summary(doctype, frequency, count, filters = {}):
    summaries = []
    for t in get_time_slots(frequency, int(count)):
        summaries.append({
            "day": formatdate((t[1]), "dd/M"),
            "value": get_doc_count(doctype, filters, t)
        })
    return summaries

def get_aggregation_summary(doctype, field, frequency, count, filters = {}):
    summaries = []
    for t in get_time_slots(frequency, int(count)):
        summaries.append({
            "day": formatdate((t[1]), "dd/M"),
            "value": get_value_aggregation(doctype, field, filters, t)
        })
    return summaries

def get_time_slots(frequency, count, start = ""):
    '''Create 'count' number of time slots for given freqency and start date
        Eg: For "Daily",
        [
            [start, end],
            [start, end],
            ...
        ]
    '''

    time_slots = []
    s = start or frappe.utils.today()
    s = add_days(s, 1)

    add_duration_map = {
        "Hourly": add_days, # change
        "Daily": add_days,
        "Weekly": add_weeks,
        "Monthly": add_months,
        "Annually": add_years
    }

    for i in xrange(0, count):
        if frequency == "Daily":
            j = i
        else:
            j = i+1
        time_slots.append([
            add_duration_map[frequency](s, -j),
            add_duration_map[frequency](s, -i)
        ])

    return time_slots

def get_goals(doctype):
    # Arrange fetched goals as:
    # goal_summaries = {
    #     "Daily": {
    #     },
    #     "Weekly": {
    #         "count": [
    #             {
    #                 "frequency": "Weekly",
    #                 "break_up_freq": "Daily",
    #                 "type": "count",

    #                 "filters": {},
    #                 "target": 10,
    #                 "current_value": 4, doc_count: 4
    #                 "break_up": [
    #                     {"time_slot": t, "value": 2},
    #                     {}, ...
    #                 ]
    #             }, {} ...
    #         ],
    #         "aggregation": [
    #             {
    #                 "frequency": "Weekly",
    #                 "break_up_freq": "Daily",
    #                 "type": "sum",
    #                 "based_on": "",

    #                 "average_goal": 16  # (or sum_goal) if exists, to highlight
    #                                     # for the same based_on and filters

    #                 "filters": {},
    #                 "target": 120,
    #                 "current_value": 40,  # always sum
    #                 "average": 5

    #                 "doc_count": 8,        # for average, show here too
    #                 "break_up": [
    #                     {"time_slot": t, "value": 15},
    #                     {}, ...
    #                 ]
    #             }, {} ...
    #         ],
    #     }, ...
    # }

    frequency_map = {
        "Daily": {"break_up": "Hourly", "break_up_count": 24},
        "Weekly": {"break_up": "Daily", "break_up_count": 17},
        "Monthly": {"break_up": "Daily", "break_up_count": 30},
        "Annually": {"break_up": "Monthly", "break_up_count": 12},
    }
    frequencies = frequency_map.keys()

    goals = frappe.get_list(
        'Goal', fields=['source_filter', 'frequency', 'type_of_aggregation',
            'based_on', 'target'], filters={'source': doctype})

    goal_summaries = {}
    for f in frequencies:
        goal_summaries[f] = {"count": [], "aggregation": []}

    for g in goals:
        freq = g["frequency"]
        break_up_freq = frequency_map[freq]["break_up"]
        break_up_count = frequency_map[freq]["break_up_count"]
        filters = g["source_filter"]
        doc_count = get_count_summary(doctype, freq, 1,
                filters)[0]["value"]

        goal = {
            "doctype": doctype,
            "frequency": freq,
            "break_up_freq": break_up_freq,
            "type": g["type_of_aggregation"],

            "filters": filters,
            "target": g["target"],
            "doc_count": doc_count
        }
        if(g["type_of_aggregation"] == "Count"):
            goal["current_value"] = goal["doc_count"]
            goal["break_up"] = get_count_summary(doctype, break_up_freq,
                break_up_count, filters)
            goal["history"] = get_count_summary(doctype, freq,
                20, filters)
            goal_summaries[g["frequency"]]["count"].append(goal)
        else:
            sum_value = get_aggregation_summary(doctype,
                g["based_on"], freq, 1, filters)[0]["value"]

            goal["based_on"] = frappe.unscrub(g["based_on"])
            goal["current_value"] = sum_value
            goal["break_up"] = get_aggregation_summary(doctype, g["based_on"],
                break_up_freq, break_up_count, filters)
            goal["history"] = get_aggregation_summary(doctype, g["based_on"], freq,
                20, filters)
            goal["average"] = sum_value / doc_count
            goal_summaries[g["frequency"]]["aggregation"].append(goal)

    return goal_summaries

@frappe.whitelist()
def get_doctype_goals():

    # To cache
    doctypes = list(set([d.source for d in frappe.get_list("Goal", fields=["source"])]))
    all_goals = {}
    for d in doctypes:
        all_goals[d] = get_goals(d)

    return all_goals
