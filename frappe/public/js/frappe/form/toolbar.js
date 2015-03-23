// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.ui.form");
frappe.ui.form.Toolbar = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make_menu();
		this.refresh();
		this.add_update_button_on_dirty();
	},
	refresh: function() {
		this.set_title();
		this.page.clear_user_actions();
		this.show_title_as_dirty();
		this.set_primary_action();
		this.refresh_star();

		if(this.frm.meta.hide_toolbar) {
			this.page.hide_menu();
		} else {
			if(this.frm.doc.__islocal) {
				this.page.hide_menu();
				this.print_icon && this.print_icon.addClass("hide");
				this.star_icon.addClass("hide");
			} else {
				this.page.show_menu();
				this.print_icon && this.print_icon.removeClass("hide");
				this.star_icon.removeClass("hide");
			}
		}
	},
	set_title: function() {
		if(this.frm.meta.title_field) {
			var title = (this.frm.doc[this.frm.meta.title_field] || "").trim() || __(this.frm.docname);
			if(this.frm.doc.__islocal || title === this.frm.docname || this.frm.meta.autoname==="hash") {
				this.page.set_title_sub("");
			} else {
				this.page.set_title_sub(this.frm.docname);
			}
		} else {
			var title = __(this.frm.docname);
		}
		var me = this;
		this.page.set_title(title);
		if(this.frm.meta.title_field) {
			document.title = title + " - " + this.frm.docname;
		}
		this.set_indicator();
	},
	get_dropdown_menu: function(label) {
		return this.page.add_dropdown(label);
	},
	set_indicator: function() {
		var indicator = frappe.get_indicator(this.frm.doc);
		if(indicator) {
			this.page.set_indicator(indicator[0], indicator[1]);
		} else {
			this.page.clear_indicator();
		}
	},
	refresh_star: function() {
		this.star_icon.toggleClass("text-extra-muted not-starred", !frappe.ui.is_starred(this.frm.doc))
			.attr("data-doctype", this.frm.doctype).attr("data-name", this.frm.doc.name);
	},
	make_menu: function() {
		var me = this;
		var p = this.frm.perm[0];
		var docstatus = cint(this.frm.doc.docstatus);

		// Print
		if(frappe.model.can_print(null, me.frm)) {
			this.page.add_menu_item(__("Print"), function() {
				me.frm.print_doc();}, true);
			this.print_icon = this.page.add_action_icon("icon-print", function() {
				me.frm.print_doc();});
		}

		// star
		this.star_icon = this.page.add_action_icon("icon-star", function() {
			frappe.ui.toggle_star(me.star_icon, me.frm.doctype, me.frm.doc.name);
		}).removeClass("text-muted").find(".icon-star").addClass("star-action");

		// email
		if(frappe.model.can_email(null, me.frm)) {
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
		if(me.frm.meta.allow_rename && me.frm.perm[0].write) {
			this.page.add_menu_item(__("Rename"), function() {
				me.frm.rename_doc();}, true);
		}

		// reload
		this.page.add_menu_item(__("Reload"), function() {
			me.frm.reload_doc();}, true);

		// delete
		if((cint(me.frm.doc.docstatus) != 1) && !me.frm.doc.__islocal
			&& frappe.model.can_delete(me.frm.doctype)) {
			this.page.add_menu_item(__("Delete"), function() {
				me.frm.savetrash();}, true);
		}

		// New
		if(p[CREATE] && !this.frm.meta.issingle) {
			this.page.add_menu_item(__("New {0}", [__(me.frm.doctype)]), function() {
				new_doc(me.frm.doctype);}, true);
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
			&& !this.read_only
			&& !this.has_workflow();
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

		status = this.get_action_status();
		if (status) {
			if (status !== this.current_status) {
				this.set_page_actions(status);
			}
		} else {
			this.page.clear_actions();
		}
	},
	get_action_status: function() {
		var status = null;
		if (this.can_submit()) {
			status = "Submit";
		} else if (this.can_save()) {
			if (!this.frm.save_disabled) {
				status = "Save";
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

		var perm_to_check = this.frm.action_perm_type_map[status];
		if(!this.frm.perm[0][perm_to_check]) {
			return;
		}

		if(status == "Cancel") {
			this.page.set_secondary_action(__(status), function() {
				me.frm.savecancel(this);
			}, "octicon octicon-circle-slash");
		} else {
			var click = {
				"Save": function() {
					me.frm.save('Save', null, this);
				},
				"Submit": function() {
					me.frm.savesubmit(this);
				},
				"Update": function() {
					me.frm.save('Update', null, this);
				},
				"Amend": function() {
					me.frm.amend_doc();
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
			this.page.set_secondary_action('Cancel', function() {
				me.frm.savecancel(this) }, 'icon-ban-circle');
		} else if(docstatus==2 && p[AMEND]) {
			this.page.set_secondary_action('Amend', function() {
				me.frm.amend_doc() }, 'icon-pencil', true);
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
