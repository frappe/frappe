import frappe
from frappe.utils import get_datetime

def execute():
	weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

	daily_events = frappe.get_list("Event", filters={"repeat_this_event": 1, "repeat_on": "Every Day"}, fields=["name", "starts_on"])
	weekly_events = frappe.get_list("Event", filters={"repeat_this_event": 1, "repeat_on": "Every Week"}, fields=["name", "starts_on"])
	monthly_events = frappe.get_list("Event", filters={"repeat_this_event": 1, "repeat_on": "Every Month"}, fields=["name", "starts_on"])
	yearly_events = frappe.get_list("Event", filters={"repeat_this_event": 1, "repeat_on": "Every Year"}, fields=["name", "starts_on"])

	frappe.reload_doc("desk", "doctype", "event")

	for daily_event in daily_events:
		"""
			Initially Daily Events had option to choose days, but now Weekly does,
			so just changing from Daily -> Weekly does the job
		"""
		frappe.db.set_value("Event", daily_event.name, "repeat_on", "Weekly")

	for weekly_event in weekly_events:
		"""
			Set WeekDay based on the starts_on so that event can repeat Weekly
		"""
		frappe.db.set_value("Event", weekly_event.name, "repeat_on", "Weekly")
		frappe.db.set_value("Event", weekly_event.name, weekdays[get_datetime(weekly_event.starts_on).weekday()], 1)

	for monthly_event in monthly_events:
		frappe.db.set_value("Event", monthly_event.name, "repeat_on", "Monthly")

	for yearly_event in yearly_events:
		frappe.db.set_value("Event", yearly_event.name, "repeat_on", "Yearly")