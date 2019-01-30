// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.ui.form");
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
			var title = strip_html((this.frm.doc[this.frm.meta.title_field] || "").trim() || this.frm.docname);
			if(this.frm.doc.__islocal || title === this.frm.docname || this.frm.meta.autoname==="hash") {
				this.page.set_title_sub("");
			} else {
				this.page.set_title_sub(this.frm.docname);
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
		if (this.frm.meta.title_field==="title"
			&& this.frm.perm[0].write
			&& !this.frm.get_docfield("title").options
			&& !this.frm.doc.__islocal) {
			return true;
		} else {
			return false;
		}
	},
	can_rename: function() {
		return this.frm.perm[0].write && this.frm.meta.allow_rename && !this.frm.doc.__islocal;
	},
	setup_editable_title: function() {
		var me = this;
		this.page.$title_area.find(".title-text").on("click", function() {
			if(me.is_title_editable()) {
				frappe.prompt({fieldname: "title", fieldtype:"Data",
					label: __("Title"), reqd: 1, "default": me.frm.doc.title },
					function(data) {
						if(data.title) {
							me.frm.set_value("title", data.title);
							if(!me.frm.doc.__islocal) {
								me.frm.save_or_update();
							} else {
								me.set_title();
							}
						}
					}, __("Edit Title"), __("Update"));
			}
			if(me.can_rename()) {
				me.frm.rename_doc();
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
					me.frm.print_doc();});
			}
		}

		// email
		if(frappe.model.can_email(null, me.frm) && me.frm.doc.docstatus < 2) {
			this.page.add_menu_item(__("Email"), function() {
				me.frm.email_doc();}, true);
		}

		// Linked With
		if(!me.frm.meta.issingle) {
			this.page.add_menu_item(__('Links'), function() {
				me.show_linked_with();
			}, true)
		}

		// copy
		if(in_list(frappe.boot.user.can_create, me.frm.doctype) && !me.frm.meta.allow_copy) {
			this.page.add_menu_item(__("Duplicate"), function() {
				me.frm.copy_doc();}, true);
		}

		// rename
		if(this.can_rename()) {
			this.page.add_menu_item(__("Rename"), function() {
				me.frm.rename_doc();}, true);
		}

		// reload
		this.page.add_menu_item(__("Reload"), function() {
			me.frm.reload_doc();}, true);

		// add to desktop
		if(me.frm.meta.issingle) {
			this.page.add_menu_item(__('Add to Desktop'), function () {
				frappe.add_to_desktop(me.frm.doctype, me.frm.doctype);
			}, true);
		}

		// delete
		if((cint(me.frm.doc.docstatus) != 1) && !me.frm.doc.__islocal
			&& frappe.model.can_delete(me.frm.doctype)) {
			this.page.add_menu_item(__("Delete"), function() {
				me.frm.savetrash();}, true);
		}

		if(frappe.user_roles.includes("System Manager")) {
			this.page.add_menu_item(__("Customize"), function() {
				frappe.set_route("Form", "Customize Form", {
					doc_type: me.frm.doctype
				})
			}, true);

			if (frappe.boot.developer_mode===1 && me.frm.meta.issingle) {
				// edit doctype
				this.page.add_menu_item(__("Edit DocType"), function() {
					frappe.set_route('Form', 'DocType', me.frm.doctype);
				}, true);
			}
		}

		// feedback
		if(!this.frm.doc.__unsaved) {
			if(is_submittable && docstatus == 1) {
				this.page.add_menu_item(__("Request Feedback"), function() {
					var feedback = new frappe.utils.Feedback();
					feedback.manual_feedback_request(me.frm.doc);
				}, true)
			}
		}

		// New
		if(p[CREATE] && !this.frm.meta.issingle) {
			this.page.add_menu_item(__("New {0} (Ctrl+B)", [__(me.frm.doctype)]), function() {
				frappe.new_doc(me.frm.doctype, true);}, true);
		}
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
			if (status !== this.current_status) {
				this.set_page_actions(status);
			}
		} else {
			this.page.clear_actions();
			this.current_status = null
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
	make_cancel_amend_button: function() {
		var me = this;
		var docstatus = cint(this.frm.doc.docstatus);
		var p = this.frm.perm[0];
		var has_workflow = this.has_workflow();

		if(has_workflow) {
			return;
		} else if(docstatus==1 && p[CANCEL]) {
			this.page.set_secondary_action(__('Cancel'), function() {
				me.frm.savecancel(this) }, 'fa fa-ban-circle');
		} else if(docstatus==2 && p[AMEND]) {
			this.page.set_secondary_action(__('Amend'), function() {
				me.frm.amend_doc() }, 'fa fa-pencil', true);
		}
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
	}
})
