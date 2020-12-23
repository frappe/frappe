frappe.provide('frappe.widget.utils');

frappe.widget.utils = {
	build_summary_item: function(summary) {
		let df = { fieldtype: summary.datatype };
		let doc = null;

		if (summary.datatype == "Currency") {
			df.options = "currency";
			doc = { currency: summary.currency };
		}

		let value = frappe.format(summary.value, df, null, doc);
		let indicator = summary.indicator
			? `indicator ${summary.indicator.toLowerCase()}`
			: "";

		return $(
			`<div class="summary-item"><span class="summary-label small text-muted ${indicator}">${
				summary.label
			}</span><h1 class="summary-value">${value}</h1></div>`
		);
	},
};

const map_defaults = {
	center: [19.0800, 72.8961],
	zoom: 13,
	tiles: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
	options: {
		attribution: '&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors'
	}
};

export { map_defaults };
