// Copyright (c) 2018, Frappe Technologies and contributors
// For license information, please see license.txt

this.frm.add_fetch('sender', 'email_id', 'sender_email');

this.frm.fields_dict.sender.get_query = function() {
	return {
		filters: {
			enable_outgoing: 1
		}
	};
};

frappe.notification = {
	setup_fieldname_select: function(frm) {
		// get the doctype to update fields
		if (!frm.doc.document_type) {
			return;
		}

		frappe.model.with_doctype(frm.doc.document_type, function() {
			let get_select_options = function(df, parent_field) {
				// Append parent_field name along with fieldname for child table fields
				let select_value = parent_field ? df.fieldname + ',' + parent_field : df.fieldname;

				return {
					value: select_value,
					label: df.fieldname + ' (' + __(df.label) + ')'
				};
			};

			let get_date_change_options = function() {
				let date_options = $.map(fields, function(d) {
					return d.fieldtype == 'Date' || d.fieldtype == 'Datetime'
						? get_select_options(d)
						: null;
				});
				// append creation and modified date to Date Change field
				return date_options.concat([
					{ value: 'creation', label: `creation (${__('Created On')})` },
					{ value: 'modified', label: `modified (${__('Last Modified Date')})` }
				]);
			};

			let fields = frappe.get_doc('DocType', frm.doc.document_type).fields;
			let options = $.map(fields, function(d) {
				return in_list(frappe.model.no_value_type, d.fieldtype)
					? null : get_select_options(d);
			});

			// set value changed options
			frm.set_df_property('value_changed', 'options', [''].concat(options));
			frm.set_df_property(
				'set_property_after_alert',
				'options',
				[''].concat(options)
			);

			// set date changed options
			frm.set_df_property('date_changed', 'options', get_date_change_options());

			let receiver_fields = [];
			if (frm.doc.channel === 'Email') {
				receiver_fields = $.map(fields, function(d) {

					// Add User and Email fields from child into select dropdown
					if (d.fieldtype == 'Table') {
						let child_fields = frappe.get_doc('DocType', d.options).fields;
						return $.map(child_fields, function(df) {
							return df.options == 'Email' ||
								(df.options == 'User' && df.fieldtype == 'Link')
								? get_select_options(df, d.fieldname) : null;
						});
					// Add User and Email fields from parent into select dropdown
					} else {
						return d.options == 'Email' ||
							(d.options == 'User' && d.fieldtype == 'Link')
							? get_select_options(d) : null;
					}
				});
			} else if (in_list(['WhatsApp', 'SMS'], frm.doc.channel)) {
				receiver_fields = $.map(fields, function(d) {
					return d.options == 'Phone' ? get_select_options(d) : null;
				});
			}

			// set email recipient options
			frm.fields_dict.recipients.grid.update_docfield_property(
				'receiver_by_document_field',
				'options',
				[''].concat(["owner"]).concat(receiver_fields)
			);
		});
	},
	setup_example_message: function(frm) {
		let template = '';
		if (frm.doc.channel === 'Email') {
			template = `<h5>Message Example</h5>

<pre>&lt;h3&gt;Order Overdue&lt;/h3&gt;

&lt;p&gt;Transaction {{ doc.name }} has exceeded Due Date. Please take necessary action.&lt;/p&gt;

&lt;!-- show last comment --&gt;
{% if comments %}
Last comment: {{ comments[-1].comment }} by {{ comments[-1].by }}
{% endif %}

&lt;h4&gt;Details&lt;/h4&gt;

&lt;ul&gt;
&lt;li&gt;Customer: {{ doc.customer }}
&lt;li&gt;Amount: {{ doc.grand_total }}
&lt;/ul&gt;
</pre>
			`;
		} else if (in_list(['Slack', 'System Notification', 'SMS'], frm.doc.channel)) {
			template = `<h5>Message Example</h5>

<pre>*Order Overdue*

Transaction {{ doc.name }} has exceeded Due Date. Please take necessary action.

<!-- show last comment -->
{% if comments %}
Last comment: {{ comments[-1].comment }} by {{ comments[-1].by }}
{% endif %}

*Details*

• Customer: {{ doc.customer }}
• Amount: {{ doc.grand_total }}
</pre>`;
		}
		if (template) {
			frm.set_df_property('message_examples', 'options', template);
		}

	}
};

frappe.ui.form.on('Notification', {
	onload: function(frm) {
		frm.set_query('document_type', function() {
			return {
				filters: {
					istable: 0
				}
			};
		});
		frm.set_query('print_format', function() {
			return {
				filters: {
					doc_type: frm.doc.document_type
				}
			};
		});
	},
	refresh: function(frm) {
		frappe.notification.setup_fieldname_select(frm);
		frappe.notification.setup_example_message(frm);
		frm.get_field('is_standard').toggle(frappe.boot.developer_mode);
		frm.trigger('event');
	},
	document_type: function(frm) {
		frappe.notification.setup_fieldname_select(frm);
	},
	view_properties: function(frm) {
		frappe.route_options = { doc_type: frm.doc.document_type };
		frappe.set_route('Form', 'Customize Form');
	},
	event: function(frm) {
		if (in_list(['Days Before', 'Days After'], frm.doc.event)) {
			frm.add_custom_button(__('Get Alerts for Today'), function() {
				frappe.call({
					method:
						'frappe.email.doctype.notification.notification.get_documents_for_today',
					args: {
						notification: frm.doc.name
					},
					callback: function(r) {
						if (r.message) {
							frappe.msgprint(r.message);
						} else {
							frappe.msgprint(__('No alerts for today'));
						}
					}
				});
			});
		}
	},
	channel: function(frm) {
		frm.toggle_reqd('recipients', frm.doc.channel == 'Email');
		frappe.notification.setup_fieldname_select(frm);
		frappe.notification.setup_example_message(frm);
		if (frm.doc.channel === 'SMS' && frm.doc.__islocal) {
			frm.set_df_property('channel',
				'description', `To use SMS Channel, initialize <a href="/app/sms-settings">SMS Settings</a>.`);
		} else {
			frm.set_df_property('channel', 'description', ` `);
		}
	}
});
