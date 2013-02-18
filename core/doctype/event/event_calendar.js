wn.views.calendar["Event"] = wn.views.Calendar.extend({
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
	get_events_method: "core.doctype.event.event.get_events"
})