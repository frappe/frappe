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

	shorten_number(number, country) {
		country = (country == 'India') ? country : '';
		const number_system = get_number_system(country);
		let x = Math.abs(Math.round(number));
		for (const map of number_system) {
			const condition = map.condition ? map.condition(x) : x >= map.divisor;
			if (condition) {
				return (number / map.divisor).toFixed(2) + ' ' + map.symbol;
			}
		}
		return number.toFixed(2);
	},

	get_number_system(country) {
		let number_system_map = {
			'India':
				[{
					divisor: 1.0e+7,
					symbol: 'Cr'
				},
				{
					divisor: 1.0e+5,
					symbol: 'Lakh'
				}],
			'':
				[{
					divisor: 1.0e+12,
					symbol: 'T'
				},
				{
					divisor: 1.0e+9,
					symbol: 'B'
				},
				{
					divisor: 1.0e+6,
					symbol: 'M'
				},
				{
					divisor: 1.0e+3,
					symbol: 'K',
					condition: (num) => num.toFixed().length > 5
				}]
		};
		return number_system_map[country];
	}
});