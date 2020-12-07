frappe.provide('frappe.utils');

Object.assign(frappe.utils, {
	build_summary_item(summary) {
		if (summary.type == "separator") {
			return $(`<div class="summary-separator">
				<div class="summary-value ${summary.color ? summary.color.toLowerCase() : 'text-muted'}">${summary.value}</div>
			</div>`);
		}
		let df = { fieldtype: summary.datatype };
		let doc = null;

		if (summary.datatype == "Currency") {
			df.options = "currency";
			doc = { currency: summary.currency };
		}

		let value = frappe.format(summary.value, df, { only_value: true }, doc);
		let color = summary.indicator ? summary.indicator.toLowerCase()
			: summary.color ? summary.color.toLowerCase() : '';

		return $(`<div class="summary-item">
			<span class="summary-label">${summary.label}</span>
			<div class="summary-value ${color}">${value}</div>
		</div>`);
	},
});