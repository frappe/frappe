// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Assignment Rule', {
	onload: (frm) => {
		frm.trigger('set_due_date_field_options');
	},
	setup: function(frm) {
		frm.trigger('setup_assignment_days_buttons');
	},
	refresh: function(frm) {
		// refresh description
		frm.events.rule(frm);
		frm.trigger('set_field_options');
	},

	document_type: function(frm) {
		frm.trigger('set_field_options');
		frm.trigger('set_due_date_field_options');
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

		let get_button_html = (label) => `<button
			class="btn btn-xs btn-default pull-right"
			style="margin-bottom: 10px; margin-right: 5px">${__(
			label
		)}</button>`;

		const $wrapper = frm.get_field('assignment_days').$wrapper;
		$(`<div class="fetch-days-buttons">
				${labels.map(get_button_html).join('')}
		</div>`).prependTo($wrapper);

		frm.$wrapper.find('.fetch-days-buttons').on('click', '.btn', (e) => {
			frm.clear_table('assignment_days');
			const label = $(e.currentTarget).text();
			get_days(label).forEach((day) =>
				frm.add_child('assignment_days', { day: day })
			);
			frm.refresh_field('assignment_days');
		});
	},

	rule: function(frm) {
		const description_map = {
			'Round Robin': __('Assign one by one, in sequence'),
			'Load Balancing': __('Assign to the one who has the least assignments'),
			'Based on Field': __('Assign to the user set in this field'),
		};
		frm.get_field('rule').set_description(description_map[frm.doc.rule]);
	},

	set_field_options(frm) {
		let doctype = frm.doc.document_type;
		let user_link_fields = [{ label: 'Owner', value: 'owner' }];
		if (doctype) {
			frappe.model.with_doctype(doctype, () => {
				frappe.get_meta(doctype).fields.map((df) => {
					if (df.fieldtype == 'Link' && df.options == 'User') {
						user_link_fields.push({ label: df.label, value: df.fieldname });
					}
				});
				frm.set_df_property('field', 'options', user_link_fields);
			});
		}
	},
	set_due_date_field_options: (frm) => {
		let doctype = frm.doc.document_type;
		let datetime_fields = [];
		if (doctype) {
			frappe.model.with_doctype(doctype, () => {
				frappe.get_meta(doctype).fields.map((df) => {
					if (['Date', 'Datetime'].includes(df.fieldtype)) {
						datetime_fields.push({ label: df.label, value: df.fieldname });
					}
				});
				if (datetime_fields) {
					frm.set_df_property('due_date_based_on', 'options', datetime_fields);
				}
				frm.set_df_property('due_date_based_on', 'hidden', !datetime_fields.length);
			});
		}
	}
});
