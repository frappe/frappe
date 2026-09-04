// Copyright (c) 2018, Frappe Technologies and contributors
// For license information, please see license.txt

const DATE_BASED_EVENTS = ["Days Before", "Days After"];

frappe.notification = {
	setup_fieldname_select: function (frm) {
		// get the doctype to update fields
		if (!frm.doc.document_type) {
			return;
		}

		frappe.model.with_doctype(frm.doc.document_type, function () {
			let get_select_options = function (df, parent_field) {
				// Append parent_field name along with fieldname for child table fields
				let select_value = parent_field ? df.fieldname + "," + parent_field : df.fieldname;
				let path = parent_field ? parent_field + " > " + df.fieldname : df.fieldname;

				return {
					value: select_value,
					label: path + " (" + __(df.label, null, df.parent) + ")",
				};
			};

			let get_date_change_options = function (fieldtypes) {
				let date_options = $.map(fields, function (d) {
					return fieldtypes.includes(d.fieldtype) ? get_select_options(d) : null;
				});
				// append creation and modified date to Date Change field
				return date_options.concat([
					{ value: "creation", label: `creation (${__("Created On")})` },
					{ value: "modified", label: `modified (${__("Last Modified Date")})` },
				]);
			};
			let get_receiver_fields = function (
				fields,
				is_extra_receiver_field = (_) => {
					return false;
				}
			) {
				// finds receiver fields from the fields or any child table
				// by default finds any link to the User doctype
				// however an additional optional predicate can be passed as argument
				// to find additional fields
				let is_receiver_field = function (df) {
					return (
						is_extra_receiver_field(df) ||
						(df.options == "User" && df.fieldtype == "Link") ||
						(df.options == "Customer" && df.fieldtype == "Link")
					);
				};
				let extract_receiver_field = function (df) {
					// Add recipients from child doctypes into select dropdown
					if (frappe.model.table_fields.includes(df.fieldtype)) {
						let child_fields = frappe.get_doc("DocType", df.options).fields;
						return $.map(child_fields, function (cdf) {
							return is_receiver_field(cdf)
								? get_select_options(cdf, df.fieldname)
								: null;
						});
					} else {
						return is_receiver_field(df) ? get_select_options(df) : null;
					}
				};
				return $.map(fields, extract_receiver_field);
			};

			let fields = frappe.get_doc("DocType", frm.doc.document_type).fields;
			let options = $.map(fields, function (d) {
				return frappe.model.no_value_type.includes(d.fieldtype)
					? null
					: get_select_options(d);
			});

			// set value changed options
			frm.set_df_property("value_changed", "options", [""].concat(options));
			frm.set_df_property("set_property_after_alert", "options", [""].concat(options));

			// set date changed options
			frm.set_df_property(
				"date_changed",
				"options",
				get_date_change_options(["Date", "Datetime"])
			);
			frm.set_df_property(
				"datetime_changed",
				"options",
				get_date_change_options(["Datetime"])
			);

			let receiver_fields = [];
			if (frm.doc.channel === "Email") {
				receiver_fields = get_receiver_fields(fields, function (df) {
					return df.options == "Email";
				});
			} else if (["WhatsApp", "SMS"].includes(frm.doc.channel)) {
				receiver_fields = get_receiver_fields(fields, function (df) {
					return df.options == "Phone" || df.options == "Mobile";
				});
			}

			// set email recipient options
			frm.fields_dict.recipients.grid.update_docfield_property(
				"receiver_by_document_field",
				"options",
				[""].concat(["owner"]).concat(receiver_fields)
			);

			// set options for "From Attach Field"
			let attach_fields = fields.filter((d) =>
				["Attach", "Attach Image"].includes(d.fieldtype)
			);
			let attach_options = $.map(attach_fields, function (d) {
				return get_select_options(d);
			});

			frm.set_df_property("from_attach_field", "options", [""].concat(attach_options));
		});
	},
	setup_example_message: function (frm) {
		let template = "";
		if (frm.doc.channel === "Email") {
			template = `<h5>Message Example</h5>

<pre><code class="language-xml">&lt;h3&gt;Order Overdue&lt;/h3&gt;

&lt;p&gt;Transaction {{ doc.name }} has exceeded Due Date. Please take necessary action.&lt;/p&gt;

&lt;!-- show last comment --&gt;
{% if comments %}
Last comment: {{ comments[-1].comment }} by {{ comments[-1].by }}
{% endif %}

&lt;h4&gt;Details&lt;/h4&gt;

&lt;ul&gt;
&lt;li&gt;Customer: {{ doc.customer }}&lt;/li&gt;
&lt;li&gt;Amount: {{ doc.grand_total }}&lt;/li&gt;
&lt;/ul&gt;
</code></pre>
			`;
		} else if (["Slack", "System Notification", "SMS"].includes(frm.doc.channel)) {
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
			const message_examples_field = frm.get_field("message_examples");
			message_examples_field.html(template);
			if (frm.doc.channel === "Email") {
				frappe.utils.highlight_pre(message_examples_field.$wrapper);
			}
		}
	},
	fetch_email_template: function (frm, template_name) {
		frappe.model.with_doc("Email Template", template_name, () => {
			const template = frappe.get_doc("Email Template", template_name);
			// `use_html` picks the column, but the other one holds the body when it is empty
			const body = template.use_html
				? template.response_html || template.response
				: template.response || template.response_html;

			if (!body) {
				frappe.msgprint({
					title: __("Empty Email Template"),
					message: __("{0} has no message to copy.", [
						frappe.utils.escape_html(template_name),
					]),
					indicator: "orange",
				});
				return;
			}

			const values = { subject: template.subject || "", message: body };
			// a hidden field is not copied, so an SMS takes only a Message
			const targets = Object.keys(values).filter((fieldname) => {
				const field = frm.get_field(fieldname);
				return field && field.get_status() !== "None";
			});
			const apply = () =>
				targets.forEach((fieldname) => frm.set_value(fieldname, values[fieldname]));

			const placeholder = frappe.meta.get_docfield("Notification", "message")?.default;
			const authored = targets.some(
				(fieldname) => frm.doc[fieldname] && frm.doc[fieldname] !== placeholder
			);
			if (!authored) {
				apply();
				return;
			}

			const labels = targets.map((fieldname) =>
				__(frappe.meta.get_docfield("Notification", fieldname).label)
			);
			frappe.confirm(
				__("Replace the current {0} with this template?", [
					frappe.utils.comma_and(labels),
				]),
				apply
			);
		});
	},
};

frappe.ui.form.on("Notification", {
	onload: function (frm) {
		frm.set_query("document_type", function () {
			if (DATE_BASED_EVENTS.includes(frm.doc.event)) return;

			return {
				filters: {
					istable: 0,
				},
			};
		});
		frm.set_query("print_format", function () {
			return {
				filters: {
					doc_type: frm.doc.document_type,
				},
			};
		});
	},
	refresh: function (frm) {
		frappe.notification.setup_fieldname_select(frm);
		frappe.notification.setup_example_message(frm);

		frm.add_fetch("sender", "email_id", "sender_email");
		frm.set_query("sender", () => {
			return {
				filters: {
					enable_outgoing: 1,
				},
			};
		});
		frm.get_field("is_standard").toggle(frappe.boot.developer_mode);
		frm.trigger("event");
		if (frm.doc.document_type) {
			frm.add_custom_button(__("Preview"), () => {
				const args = {
					doc: frm.doc,
					doctype: frm.doc.document_type,
					preview_fields: [
						{
							label: __("Meets Condition?"),
							fieldtype: "Data",
							method: "preview_meets_condition",
						},
						{ label: __("Subject"), fieldtype: "Data", method: "preview_subject" },
						{ label: __("Message"), fieldtype: "Code", method: "preview_message" },
					],
				};
				let dialog = new frappe.views.RenderPreviewer(args);
				return dialog;
			});
		}

		frm.trigger("set_up_filters_editor");
	},
	document_type: function (frm) {
		frappe.notification.setup_fieldname_select(frm);
		frm.trigger("set_up_filters_editor");
	},
	fetch_email_template: function (frm) {
		const dialog = new frappe.ui.Dialog({
			title: __("Fetch from Email Template"),
			fields: [
				{
					fieldname: "email_template",
					fieldtype: "Link",
					label: __("Email Template"),
					options: "Email Template",
					reqd: 1,
					get_query: () => {
						return {
							query: "frappe.email.doctype.email_template.email_template.get_email_templates",
							filters: { reference_doctype: frm.doc.document_type },
						};
					},
				},
			],
			primary_action_label: __("Fetch"),
			primary_action: ({ email_template }) => {
				dialog.hide();
				frappe.notification.fetch_email_template(frm, email_template);
			},
		});
		dialog.show();
	},
	view_properties: function (frm) {
		frappe.route_options = { doc_type: frm.doc.document_type };
		frappe.set_route("Form", "Customize Form");
	},
	event: function (frm) {
		if (!DATE_BASED_EVENTS.includes(frm.doc.event) || frm.is_new()) return;

		frm.add_custom_button(__("Get Alerts for Today"), function () {
			frappe.call({
				method: "frappe.email.doctype.notification.notification.get_documents_for_today",
				args: {
					notification: frm.doc.name,
				},
				callback: function (r) {
					if (r.message && r.message.length > 0) {
						frappe.msgprint(r.message.toString());
					} else {
						frappe.msgprint(__("No alerts for today"));
					}
				},
			});
		});
	},
	channel: function (frm) {
		frm.toggle_reqd("recipients", frm.doc.channel == "Email");
		frappe.notification.setup_fieldname_select(frm);
		frappe.notification.setup_example_message(frm);
		if (frm.doc.channel === "SMS" && frm.doc.__islocal) {
			frm.set_df_property(
				"channel",
				"description",
				`To use SMS Channel, initialize <a href="/desk/sms-settings">SMS Settings</a>.`
			);
		} else {
			frm.set_df_property("channel", "description", ` `);
		}
	},
	condition_type: function (frm) {
		if (frm.doc.condition_type === "Filters") {
			frm.set_value("condition", "");
		} else {
			frm.set_value("filters", "");
		}

		frm.trigger("set_up_filters_editor");
	},
	set_up_filters_editor(frm) {
		const parent = frm.get_field("filters_editor").$wrapper;
		parent.empty();

		if (!frm.doc.document_type || frm.doc.condition_type !== "Filters") {
			return;
		}

		const filters =
			frm.doc.filters && frm.doc.filters !== "[]" ? JSON.parse(frm.doc.filters) : [];

		frappe.model.with_doctype(frm.doc.document_type, () => {
			const filter_group = new frappe.ui.FilterGroup({
				parent: parent,
				doctype: frm.doc.document_type,
				on_change: () => {
					frappe.model.set_value(
						frm.doc.doctype,
						frm.doc.name,
						"filters",
						JSON.stringify(filter_group.get_filters())
					);
				},
			});

			filter_group.add_filters_to_filter_group(filters);
		});
	},
});
