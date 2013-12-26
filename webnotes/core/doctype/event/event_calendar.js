wn.views.calendar["Event"] = {
	field_map: {
		"start": "starts_on",
		"end": "ends_on",
		"id": "name",
		"allDay": "all_day",
		"title": "subject",
		"status": "event_type",
	},
	style_map: {
		"Public": "success",
		"Private": "info"
	},
	get_events_method: "webnotes.core.doctype.event.event.get_events"
}