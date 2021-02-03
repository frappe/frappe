// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
frappe.provide('frappe.views');
frappe.provide("frappe.interaction_settings");

frappe.views.InteractionComposer = class InteractionComposer {
	constructor(opts) {
		$.extend(this, opts);
		this.make();
	}

	make() {
		let me = this;
		me.dialog = new frappe.ui.Dialog({
			title: (me.title || me.subject || __("New Activity")),
			no_submit_on_enter: true,
			fields: me.get_fields(),
			primary_action_label: __('Create'),
			primary_action: function() {
				me.create_action();
			}
		});

		$(document).on("upload_complete", function(event, attachment) {
			if(me.dialog.display) {
				let wrapper = $(me.dialog.fields_dict.select_attachments.wrapper);

				// find already checked items
				let checked_items = wrapper.find('[data-file-name]:checked').map(function() {
					return $(this).attr("data-file-name");
				});

				// reset attachment list
				me.render_attach();

				// check latest added
				checked_items.push(attachment.name);

				$.each(checked_items, function(i, filename) {
					wrapper.find('[data-file-name="'+ filename +'"]').prop("checked", true);
				});
			}
		});
		me.prepare();
		me.dialog.show();
	}

	get_fields() {
		let me = this;
		let interaction_docs = Object.keys(get_doc_mappings());

		let fields = [
			{label:__("Reference"), fieldtype:"Select",
				fieldname:"interaction_type", options: interaction_docs,
				reqd: 1,
				onchange: () => {
					let values = me.get_values();
					me.get_fields().forEach(field => {
						if (field.fieldname != "interaction_type") {
							me.dialog.set_df_property(field.fieldname, "reqd", 0);
							me.dialog.set_df_property(field.fieldname, "hidden", 0);
						}
					});
					me.set_reqd_hidden_fields(values);
					me.get_event_categories();
				}
			},
			{label:__("Category"), fieldtype:"Select",
				fieldname:"category", options: "", hidden: 1},
			{label:__("Public"), fieldtype:"Check",
				fieldname:"public", default: "1"},
			{fieldtype: "Column Break"},
			{label:__("Date"), fieldtype:"Datetime",
				fieldname:"due_date"},
			{label:__("Assigned To"), fieldtype:"Link",
				fieldname:"assigned_to", options:"User"},
			{fieldtype: "Section Break"},
			{label:__("Summary"), fieldtype:"Data",
				fieldname:"summary"},
			{fieldtype: "Section Break"},
			{fieldtype:"Text Editor", fieldname:"description"},
			{fieldtype: "Section Break"},
			{label:__("Select Attachments"), fieldtype:"HTML",
				fieldname:"select_attachments"}
		];

		return fields;

	}

	get_event_categories() {
		let me = this;
		frappe.model.with_doctype('Event', () => {
			let categories = frappe.meta.get_docfield("Event", "event_category").options.split("\n");
			me.dialog.get_input("category").empty().add_options(categories);
		});
	}

	prepare() {
		this.setup_attach();
	}

	set_reqd_hidden_fields(values) {
		let me = this;
		if (values&&"interaction_type" in values) {
			let doc_mapping = get_doc_mappings();
			doc_mapping[values.interaction_type]["reqd_fields"].forEach(value => {
				me.dialog.set_df_property(value, 'reqd', 1);
			});

			doc_mapping[values.interaction_type]["hidden_fields"].forEach(value => {
				me.dialog.set_df_property(value, 'hidden', 1);
			});
		}
	}

	setup_attach() {
		var fields = this.dialog.fields_dict;
		var attach = $(fields.select_attachments.wrapper);

		if (!this.attachments) {
			this.attachments = [];
		}

		let args = {
			folder: 'Home/Attachments',
			on_success: attachment => this.attachments.push(attachment)
		};

		if (this.frm) {
			args = {
				doctype: this.frm.doctype,
				docname: this.frm.docname,
				folder: 'Home/Attachments',
				on_success: attachment => {
					this.frm.attachments.attachment_uploaded(attachment);
					this.render_attach();
				}
			};
		}

		$("<h6 class='text-muted add-attachment' style='margin-top: 12px; cursor:pointer;'>"
			+__("Select Attachments")+"</h6><div class='attach-list'></div>\
			<p class='add-more-attachments'>\
			<a class='text-muted small'><i class='octicon octicon-plus' style='font-size: 12px'></i> "
			+__("Add Attachment")+"</a></p>").appendTo(attach.empty());
		attach
			.find(".add-more-attachments a")
			.on('click',() => new frappe.ui.FileUploader(args));
		this.render_attach();
	}

	render_attach(){
		let fields = this.dialog.fields_dict;
		let attach = $(fields.select_attachments.wrapper).find(".attach-list").empty();

		let files = [];
		if (this.attachments && this.attachments.length) {
			files = files.concat(this.attachments);
		}
		if (cur_frm) {
			files = files.concat(cur_frm.get_files());
		}

		if(files.length) {
			$.each(files, function(i, f) {
				if (!f.file_name) return;
				f.file_url = frappe.urllib.get_full_url(f.file_url);

				$(repl('<p class="checkbox">'
					+	'<label><span><input type="checkbox" data-file-name="%(name)s"></input></span>'
					+		'<span class="small">%(file_name)s</span>'
					+	' <a href="%(file_url)s" target="_blank" class="text-muted small">'
					+		'<i class="fa fa-share" style="vertical-align: middle; margin-left: 3px;"></i>'
					+ '</label></p>', f))
					.appendTo(attach);
			});
		}
	}

	create_action() {
		let me = this;
		let btn = me.dialog.get_primary_btn();

		let form_values = this.get_values();
		if(!form_values) return;

		let selected_attachments =
			$.map($(me.dialog.wrapper).find("[data-file-name]:checked"), function(element){
				return $(element).attr("data-file-name");
			});

		me.create_interaction(btn, form_values, selected_attachments);
	}

	get_values() {
		let me = this;
		let values = this.dialog.get_values(true);
		if (values) {
			values["reference_doctype"] = me.frm.doc.doctype;
			values["reference_document"] = me.frm.doc.name;
		}

		return values;
	}

	create_interaction(btn, form_values, selected_attachments) {
		let me = this;
		me.dialog.hide();

		let field_map = get_doc_mappings();
		let interaction_values = {};
		Object.keys(form_values).forEach(value => {
			interaction_values[field_map[form_values.interaction_type]["field_map"][value]] = form_values[value];
		});

		if ("event_type" in interaction_values){
			interaction_values["event_type"] = (form_values.public == 1) ? "Public" : "Private";
		}
		if (interaction_values["doctype"] == "Event") {
			interaction_values["event_participants"] = [{"reference_doctype": form_values.reference_doctype,
				"reference_docname": form_values.reference_document}];
		}
		if (!("owner" in interaction_values)){
			interaction_values["owner"] = frappe.session.user;
		}
		return frappe.call({
			method:"frappe.client.insert",
			args: { doc: interaction_values},
			btn: btn,
			callback: function(r) {
				if(!r.exc) {
					frappe.show_alert({
						message: __("{0} created successfully", [form_values.interaction_type]),
						indicator: 'green'
					});
					if ("assigned_to" in form_values) {
						me.assign_document(r.message, form_values["assigned_to"]);
					}

					if (selected_attachments) {
						me.add_attachments(r.message, selected_attachments);
					}
					if (cur_frm) {
						cur_frm.reload_doc();
					}
				} else {
					frappe.msgprint(__("There were errors while creating the document. Please try again."));
				}
			}
		});

	}

	assign_document(doc, assignee) {
		if (doc.doctype != "ToDo") {
			frappe.call({
				method:'frappe.desk.form.assign_to.add',
				args: {
					doctype: doc.doctype,
					name: doc.name,
					assign_to: JSON.stringify([assignee]),
				},
				callback:function(r) {
					if(!r.exc) {
						frappe.show_alert({
							message: __("The document has been assigned to {0}", [assignee]),
							indicator: 'green'
						});
						return;
					} else {
						frappe.show_alert({
							message: __("The document could not be correctly assigned"),
							indicator: 'orange'
						});
						return;
					}
				}
			});
		}

	}

	add_attachments(doc, attachments) {
		frappe.call({
			method:'frappe.utils.file_manager.add_attachments',
			args: {
				doctype: doc.doctype,
				name: doc.name,
				attachments: JSON.stringify(attachments)
			},
			callback:function(r) {
				if(!r.exc) {
					return;
				} else {
					frappe.show_alert({
						message: __("The attachments could not be correctly linked to the new document"),
						indicator: 'orange'
					});
					return;
				}
			}
		});

	}
};

function get_doc_mappings() {
	const doc_map = {
		"Event": {
			"field_map": {
				"interaction_type": "doctype",
				"summary": "subject",
				"description": "description",
				"category": "event_category",
				"due_date": "starts_on",
				"public": "event_type"
			},
			"reqd_fields": ["summary", "due_date"],
			"hidden_fields": []
		} ,
		"ToDo": {
			"field_map": {
				"interaction_type": "doctype",
				"description": "description",
				"due_date": "date",
				"reference_doctype": "reference_type",
				"reference_document": "reference_name",
				"assigned_to": "owner"
			},
			"reqd_fields": ["description"],
			"hidden_fields": ["public", "category"]
		}
	};

	return doc_map;
}
