// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
import './linked_with';

frappe.ui.form.Toolbar = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.refresh();
		this.add_update_button_on_dirty();
		this.setup_editable_title();
	},
	refresh: function() {
		this.make_menu();
		this.set_title();
		this.page.clear_user_actions();
		this.show_title_as_dirty();
		this.set_primary_action();

		if(this.frm.meta.hide_toolbar) {
			this.page.hide_menu();
		} else {
			if(this.frm.doc.__islocal) {
				this.page.hide_menu();
				this.print_icon && this.print_icon.addClass("hide");
			} else {
				this.page.show_menu();
				this.print_icon && this.print_icon.removeClass("hide");
			}
		}
	},
	set_title: function() {
		if(this.frm.meta.title_field) {
			let title_field = (this.frm.doc[this.frm.meta.title_field] || "").toString().trim();
			var title = strip_html(title_field || this.frm.docname);
			if(this.frm.doc.__islocal || title === this.frm.docname || this.frm.meta.autoname==="hash") {
				this.page.set_title_sub("");
			} else {
				this.page.set_title_sub(this.frm.docname);
				this.page.$sub_title_area.css("cursor", "copy");
				this.page.$sub_title_area.on('click', (event) => {
					event.stopImmediatePropagation();
					frappe.utils.copy_to_clipboard(this.frm.docname);
				});
			}
		} else {
			var title = this.frm.docname;
		}

		var me = this;
		title = __(title);
		this.page.set_title(title);
		if(this.frm.meta.title_field) {
			frappe.utils.set_title(title + " - " + this.frm.docname);
		}
		this.page.$title_area.toggleClass("editable-title",
			!!(this.is_title_editable() || this.can_rename()));

		this.set_indicator();
	},
	is_title_editable: function() {
		let title_field = this.frm.meta.title_field;
		let doc_field = this.frm.get_docfield(title_field);

		if (title_field
			&& this.frm.perm[0].write
			&& !this.frm.doc.__islocal
			&& doc_field.fieldtype === "Data"
			&& !doc_field.read_only) {
			return true;
		} else {
			return false;
		}
	},
	can_rename: function() {
		return this.frm.perm[0].write && this.frm.meta.allow_rename && !this.frm.doc.__islocal;
	},
	show_unchanged_document_alert: function() {
		frappe.show_alert({
			indicator: "yellow",
			message: __("Unchanged")
		});
	},
	rename_document_title(new_name, new_title, merge=false) {
		const docname = this.frm.doc.name;
		const title_field = this.frm.meta.title_field || '';
		const doctype = this.frm.doctype;

		let confirm_message=null;

		if (new_name) {
			const warning = __("This cannot be undone");
			const message = __("Are you sure you want to merge {0} with {1}?", [docname.bold(), new_name.bold()]);
			confirm_message = `${message}<br><b>${warning}<b>`;
		}

		let rename_document = () => {
			return frappe.xcall("frappe.model.rename_doc.update_document_title", {
				doctype,
				docname,
				new_name,
				title_field,
				old_title: this.frm.doc[title_field],
				new_title,
				merge
			}).then(new_docname => {
				if (new_name != docname) {
					$(document).trigger("rename", [doctype, docname, new_docname || new_name]);
					if (locals[doctype] && locals[doctype][docname]) delete locals[doctype][docname];
				}
				this.frm.reload_doc();
			});
		};

		return new Promise((resolve, reject) => {
			if (new_title === this.frm.doc[title_field] && new_name === docname) {
				this.show_unchanged_document_alert();
				resolve();
			} else if (merge) {
				frappe.confirm(confirm_message, () => {
					rename_document().then(resolve).catch(reject);
				}, reject);
			} else {
				rename_document().then(resolve).catch(reject);
			}
		});
	},
	setup_editable_title: function () {
		let me = this;

		this.page.$title_area.find(".title-text").on("click", () => {
			let fields = [];
			let docname = me.frm.doc.name;
			let title_field = me.frm.meta.title_field || '';

			// check if title is updatable
			if (me.is_title_editable()) {
				let title_field_label = me.frm.get_docfield(title_field).label;

				fields.push({
					label: __("New {0}", [__(title_field_label)]),
					fieldname: "title",
					fieldtype: "Data",
					reqd: 1,
					default: me.frm.doc[title_field]
				});
			}

			// check if docname is updatable
			if (me.can_rename()) {
				fields.push(...[{
					label: __("New Name"),
					fieldname: "name",
					fieldtype: "Data",
					reqd: 1,
					default: docname
				}, {
					label: __("Merge with existing"),
					fieldname: "merge",
					fieldtype: "Check",
					default: 0
				}]);
			}

			// create dialog
			if (fields.length > 0) {
				let d = new frappe.ui.Dialog({
					title: __("Rename"),
					fields: fields
				});
				d.show();
				d.set_primary_action(__("Rename"), (values) => {
					d.disable_primary_action();
					this.rename_document_title(values.name, values.title, values.merge)
						.then(() => {
							d.hide();
						})
						.catch(() => {
							d.enable_primary_action();
						});
				});
			}
		});
	},
	get_dropdown_menu: function(label) {
		return this.page.add_dropdown(label);
	},
	set_indicator: function() {
		if(this.frm.save_disabled)
			return;

		var indicator = frappe.get_indicator(this.frm.doc);
		if(indicator) {
			this.page.set_indicator(indicator[0], indicator[1]);
		} else {
			this.page.clear_indicator();
		}
	},
	make_menu: function() {
		this.page.clear_icons();
		this.page.clear_menu();
		var me = this;
		var p = this.frm.perm[0];
		var docstatus = cint(this.frm.doc.docstatus);
		var is_submittable = frappe.model.is_submittable(this.frm.doc.doctype)
		var issingle = this.frm.meta.issingle;
		var print_settings = frappe.model.get_doc(":Print Settings", "Print Settings")
		var allow_print_for_draft = cint(print_settings.allow_print_for_draft);
		var allow_print_for_cancelled = cint(print_settings.allow_print_for_cancelled);

		// Print
		if(!is_submittable || docstatus == 1  ||
			(allow_print_for_cancelled && docstatus == 2)||
			(allow_print_for_draft && docstatus == 0)) {
			if(frappe.model.can_print(null, me.frm) && !issingle) {
				this.page.add_menu_item(__("Print"), function() {
					me.frm.print_doc();}, true);
				this.print_icon = this.page.add_action_icon("fa fa-print", function() {
					me.frm.print_doc();
				});
			}
		}

		// email
		if(frappe.model.can_email(null, me.frm) && me.frm.doc.docstatus < 2) {
			this.page.add_menu_item(__("Email"), function() {
				me.frm.email_doc();
			}, true, {
				shortcut: 'Ctrl+E',
				condition: () => !this.frm.is_new()
			});
		}

		// go to field modal
		this.page.add_menu_item(__("Jump to field"), function() {
			me.show_jump_to_field_dialog();
		}, true, 'Ctrl+J');

		// Linked With
		if(!me.frm.meta.issingle) {
			this.page.add_menu_item(__('Links'), function() {
				me.show_linked_with();
			}, true)
		}

		// copy
		if(in_list(frappe.boot.user.can_create, me.frm.doctype) && !me.frm.meta.allow_copy) {
			this.page.add_menu_item(__("Duplicate"), function() {
				me.frm.copy_doc();
			}, true);
		}

		// rename
		if(this.can_rename()) {
			this.page.add_menu_item(__("Rename"), function() {
				me.frm.rename_doc();
			}, true);
		}

		// reload
		this.page.add_menu_item(__("Reload"), function() {
			me.frm.reload_doc();
		}, true);

		// delete
		if((cint(me.frm.doc.docstatus) != 1) && !me.frm.doc.__islocal
			&& frappe.model.can_delete(me.frm.doctype)) {
			this.page.add_menu_item(__("Delete"), function() {
				me.frm.savetrash();
			}, true, {
				shortcut: 'Shift+Ctrl+D',
				condition: () => !this.frm.is_new()
			});
		}

		if (frappe.user_roles.includes("System Manager") && me.frm.meta.issingle === 0) {
			let is_doctype_form = me.frm.doctype === 'DocType';
			let doctype = is_doctype_form ? me.frm.docname : me.frm.doctype;
			let is_doctype_custom = is_doctype_form ? me.frm.doc.custom : false;

			if (doctype != 'DocType' && !is_doctype_custom) {
				this.page.add_menu_item(__("Customize"), function() {
					if (me.frm.meta && me.frm.meta.custom) {
						frappe.set_route('Form', 'DocType', doctype);
					} else {
						frappe.set_route('Form', 'Customize Form', {
							doc_type: doctype
						});
					}
				}, true);
			}

			if (frappe.boot.developer_mode===1 && !is_doctype_form) {
				// edit doctype
				this.page.add_menu_item(__("Edit DocType"), function() {
					frappe.set_route('Form', 'DocType', me.frm.doctype);
				}, true);
			}
		}

		// Auto Repeat
		if(this.can_repeat()) {
			this.page.add_menu_item(__("Repeat"), function(){
				frappe.utils.new_auto_repeat_prompt(me.frm);
			}, true);
		}

		// New
		if(p[CREATE] && !this.frm.meta.issingle) {
			this.page.add_menu_item(__("New {0}", [__(me.frm.doctype)]), function() {
				frappe.new_doc(me.frm.doctype, true);
			}, true, {
				shortcut: 'Ctrl+B',
				condition: () => !this.frm.is_new()
			});
		}

		// Navigate
		if(!this.frm.is_new() && !issingle) {
			this.page.add_action_icon("fa fa-chevron-left prev-doc", function() {
				me.frm.navigate_records(1);
			});
			this.page.add_action_icon("fa fa-chevron-right next-doc", function() {
				me.frm.navigate_records(0);
			});
		}
	},
	can_repeat: function() {
		return this.frm.meta.allow_auto_repeat
			&& !this.frm.is_new()
			&& !this.frm.doc.auto_repeat;
	},
	can_save: function() {
		return this.get_docstatus()===0;
	},
	can_submit: function() {
		return this.get_docstatus()===0
			&& !this.frm.doc.__islocal
			&& !this.frm.doc.__unsaved
			&& this.frm.perm[0].submit
			&& !this.has_workflow();
	},
	can_update: function() {
		return this.get_docstatus()===1
			&& !this.frm.doc.__islocal
			&& this.frm.perm[0].submit
			&& this.frm.doc.__unsaved
	},
	can_cancel: function() {
		return this.get_docstatus()===1
			&& this.frm.perm[0].cancel
			&& !this.read_only;
	},
	can_amend: function() {
		return this.get_docstatus()===2
			&& this.frm.perm[0].amend
			&& !this.read_only;
	},
	has_workflow: function() {
		if(this._has_workflow === undefined)
			this._has_workflow = frappe.get_list("Workflow", {document_type: this.frm.doctype}).length;
		return this._has_workflow;
	},
	get_docstatus: function() {
		return cint(this.frm.doc.docstatus);
	},
	show_linked_with: function() {
		if(!this.frm.linked_with) {
			this.frm.linked_with = new frappe.ui.form.LinkedWith({
				frm: this.frm
			});
		}
		this.frm.linked_with.show();
	},
	set_primary_action: function(dirty) {
		if (!dirty) {
			// don't clear actions menu if dirty
			this.page.clear_user_actions();
		}

		var status = this.get_action_status();
		if (status) {
			// When moving from a page with status amend to another page with status amend
			// We need to check if document is already amend specifically and hide
			// or clear the menu actions accordingly

			if (status !== this.current_status && status === 'Amend') {
				let doc = this.frm.doc;
				frappe.xcall('frappe.client.is_document_amended', {
					'doctype': doc.doctype,
					'docname': doc.name
				}).then(is_amended => {
					if (is_amended) {
						this.page.clear_actions();
						return;
					}
					this.set_page_actions(status);
				});
			} else {
				this.set_page_actions(status);
			}
		} else {
			this.page.clear_actions();
			this.current_status = null;
		}
	},
	get_action_status: function() {
		var status = null;
		if (this.frm.page.current_view_name==='print' || this.frm.hidden) {
			status = "Edit";
		} else if (this.can_submit()) {
			status = "Submit";
		} else if (this.can_save()) {
			if (!this.frm.save_disabled) {
				//Show the save button if there is no workflow or if there is a workflow and there are changes
				if (this.has_workflow() ? this.frm.doc.__unsaved : true) {
					status = "Save";
				}
			}
		} else if (this.can_update()) {
			status = "Update";
		} else if (this.can_cancel()) {
			status = "Cancel";
		} else if (this.can_amend()) {
			status = "Amend";
		}
		return status;
	},
	set_page_actions: function(status) {
		var me = this;
		this.page.clear_actions();

		if(status!== 'Edit') {
			var perm_to_check = this.frm.action_perm_type_map[status];
			if(!this.frm.perm[0][perm_to_check]) {
				return;
			}
		}

		if(status === "Edit") {
			this.page.set_primary_action(__("Edit"), function() {
				me.frm.page.set_view('main');
			}, 'octicon octicon-pencil');
		} else if(status === "Cancel") {
			this.page.set_secondary_action(__(status), function() {
				me.frm.savecancel(this);
			}, "octicon octicon-circle-slash");
		} else {
			var click = {
				"Save": function() {
					return me.frm.save('Save', null, this);
				},
				"Submit": function() {
					return me.frm.savesubmit(this);
				},
				"Update": function() {
					return me.frm.save('Update', null, this);
				},
				"Amend": function() {
					return me.frm.amend_doc();
				}
			}[status];

			var icon = {
				"Save": "octicon octicon-check",
				"Submit": "octicon octicon-lock",
				"Update": "octicon octicon-check",
				"Amend": "octicon octicon-split"
			}[status];

			this.page.set_primary_action(__(status), click, icon);
		}

		this.current_status = status;
	},
	add_update_button_on_dirty: function() {
		var me = this;
		$(this.frm.wrapper).on("dirty", function() {
			me.show_title_as_dirty();

			// clear workflow actions
			me.frm.page.clear_actions_menu();

			// enable save action
			if(!me.frm.save_disabled) {
				me.set_primary_action(true);
			}
		});
	},
	show_title_as_dirty: function() {
		if(this.frm.save_disabled)
			return;

		if(this.frm.doc.__unsaved) {
			this.page.set_indicator(__("Not Saved"), "orange");
		}

		$(this.frm.wrapper).attr("data-state", this.frm.doc.__unsaved ? "dirty" : "clean");
	},

	show_jump_to_field_dialog() {
		let visible_fields_filter = f =>
			!['Section Break', 'Column Break'].includes(f.df.fieldtype)
			&& !f.df.hidden
			&& f.disp_status !== 'None';

		let fields = this.frm.fields
			.filter(visible_fields_filter)
			.map(f => ({ label: f.df.label, value: f.df.fieldname }));

		let dialog = new frappe.ui.Dialog({
			title: __('Jump to field'),
			fields: [
				{
					fieldtype: 'Autocomplete',
					fieldname: 'fieldname',
					label: __('Select Field'),
					options: fields,
					reqd: 1
				}
			],
			primary_action_label: __('Go'),
			primary_action: ({ fieldname }) => {
				dialog.hide();
				this.frm.scroll_to_field(fieldname);
			}
		});

		dialog.show();
	}
})
