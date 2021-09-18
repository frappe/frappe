// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Assignment Rule', {
	refresh: function(frm) {
		frm.trigger('setup_assignment_days_buttons');
		frm.trigger('set_options');
		// refresh description
		frm.events.rule(frm);
	},

	setup: function(frm) {
		frm.set_query("document_type", () => {
			return {
				filters: {
					name: ["!=", "ToDo"]
				}
			};
		});
	},

	document_type: function(frm) {
		frm.trigger('set_options');
	},

	setup_assignment_days_buttons: function(frm) {
		const labels = ['Weekends', 'Weekdays', 'All Days'];
		let get_days = (label) => {
			const weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
			const weekends = ['Saturday', 'Sunday'];
			return {
				'All Days': weekdays.concat(weekends),
				'Weekdays': weekdays,
				'Weekends': weekends,
			}[label];
		};

		let set_days = (e) => {
			frm.clear_table('assignment_days');
			const label = $(e.currentTarget).text();
			get_days(label).forEach((day) =>
				frm.add_child('assignment_days', { day: day })
			);
			frm.refresh_field('assignment_days');
		};

		labels.forEach(label =>
			frm.fields_dict['assignment_days'].grid.add_custom_button(
				label,
				set_days,
				'top'
			)
		);
	},

	rule: function(frm) {
		const description_map = {
			'Round Robin': __('Assign one by one, in sequence'),
			'Load Balancing': __('Assign to the one who has the least assignments'),
			'Based on Field': __('Assign to the user set in this field'),
		};
		frm.get_field('rule').set_description(description_map[frm.doc.rule]);
	},

	set_options(frm) {
		const doctype = frm.doc.document_type;
		frm.set_fields_as_options(
			'field',
			doctype,
			(df) => ['Dynamic Link', 'Data'].includes(df.fieldtype)
				|| (df.fieldtype == 'Link' && df.options == 'User'),
			[{ label: 'Owner', value: 'owner' }]
		);
		if (doctype) {
			frm.set_fields_as_options(
				'due_date_based_on',
				doctype,
				(df) => ['Date', 'Datetime'].includes(df.fieldtype)
			).then(options => frm.set_df_property('due_date_based_on', 'hidden', !options.length));
		}
	},
});
