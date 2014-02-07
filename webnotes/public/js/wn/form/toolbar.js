// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

wn.provide("wn.ui.form");
wn.ui.form.Toolbar = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
		this.add_update_button_on_dirty();
		this.appframe.add_module_icon(this.frm.meta.module, this.frm.doctype);
		this.appframe.set_views_for(this.frm.meta.name, "form");
	},
	make: function() {
		this.set_title();
		this.show_title_as_dirty();

		if(this.frm.meta.hide_toolbar) {
			this.appframe.set_title_right();
			this.frm.save_disabled = true;
			this.appframe.iconbar.hide();
		} else {
			this.appframe.iconbar.clear(1)
			this.make_file_menu();
			this.make_cancel_amend_button();
			this.set_title_right();
			this.show_infobar();
			if(this.frm.doc.__islocal) {
				this.appframe.iconbar.hide(2);
				this.appframe.iconbar.hide(3);
			} else {
				this.appframe.iconbar.show(2);
				this.appframe.iconbar.show(3);
			}
		}
	},
	refresh: function() {
		this.make();
	},
	set_title: function() {
		if(this.frm.meta.title_field) {
			var title = this.frm.doc[this.frm.meta.title_field] || wn._(this.frm.docname);
		} else {
			var title = wn._(this.frm.docname);
		}
		var me = this;
		this.appframe.set_title(title);
		
		if(this.frm.meta.issingle) {
			this.appframe.set_title_left('<i class="icon-angle-left"></i> ' + wn._(this.frm.meta.module), 
				function() { wn.set_route(wn.modules[me.frm.meta.module].link); });
		} else {
			this.appframe.set_title_left('<i class="icon-angle-left"></i> ' + wn._(this.frm.doctype), 
				function() { wn.set_route("List", me.frm.doctype); });
		}
	},
	show_infobar: function() {
		/* docs:
		Render info bar that shows timestamp, # of comments, # of attachments etc.
		only if saved doc. (doc.__islocal is falsy)
		*/
		if(this.infobar) 
			this.infobar.refresh();
		else
			this.infobar = new wn.ui.form.InfoBar({appframe:this.appframe, frm:this.frm});
	},
	get_dropdown_menu: function(label) {
		return this.appframe.add_dropdown(label);
	},
	get_lock_status: function() {
		if(this.frm.meta.is_submittable && !this.frm.doc.__islocal) {
			switch(this.frm.doc.docstatus) {
				case 0:
					return ' <i class="icon-unlock text-muted" title="Not Submitted">';
				case 1:
					return ' <i class="icon-lock text-primary" title="Submitted">';
				case 2:
					return ' <i class="icon-remove text-danger" title="Cancelled">';
			}
		} else {
			return "";
		}
	},
	make_file_menu: function() {
		var me = this;
		var p = this.frm.perm[0];
		var docstatus = cint(this.frm.doc.docstatus);

		$(".custom-menu").remove();

		// New
		if(p[CREATE]) {
			this.appframe.add_dropdown_button("File", wn._("New") + " " 
				+ wn._(me.frm.doctype), function() { 
				new_doc(me.frm.doctype);}, 'icon-plus');
		}

		// Save
		if(docstatus==0 && p[WRITE] && !this.read_only) {
			this.appframe.add_dropdown_button("File", wn._("Save"), function() { 
				me.frm.save('Save', null, this);}, 'icon-save');
		}
		
		// Submit
		if(docstatus==0 && !this.frm.doc.__unsaved && p[SUBMIT] && !this.read_only) {
			this.appframe.add_dropdown_button("File", wn._("Submit"), function() { 
				me.frm.savesubmit(this);}, 'icon-lock');
		}
		
		// Cancel
		if(this.can_cancel()) {
			this.appframe.add_dropdown_button("File", wn._("Cancel"), function() { 
				me.frm.savecancel(this);}, 'icon-remove');
		}
		
		// Amend
		if(this.can_amend()) {
			this.appframe.add_dropdown_button("File", wn._("Amend"), function() { 
				me.frm.amend_doc();}, 'icon-pencil');
		}
		
		// Print
		if(!(me.frm.doc.__islocal || me.frm.meta.allow_print)) {
			this.appframe.add_dropdown_button("File", wn._("Print..."), function() { 
				me.frm.print_doc();}, 'icon-print');
		}

		// email
		if(!(me.frm.doc.__islocal || me.frm.meta.allow_email)) {
			this.appframe.add_dropdown_button("File", wn._("Email..."), function() { 
				me.frm.email_doc();}, 'icon-envelope');
		}

		// Linked With
		if(!me.frm.doc.__islocal && !me.frm.meta.issingle) {
			this.appframe.add_dropdown_button("File", wn._('Linked With'), function() { 
				me.show_linked_with();
			}, "icon-link")
		}
		
		// copy
		if(in_list(profile.can_create, me.frm.doctype) && !me.frm.meta.allow_copy) {
			this.appframe.add_dropdown_button("File", wn._("Copy"), function() { 
				me.frm.copy_doc();}, 'icon-file');
		}
		
		// rename
		if(me.frm.meta.allow_rename && me.frm.perm[0].write) {
			this.appframe.add_dropdown_button("File", wn._("Rename..."), function() { 
				me.frm.rename_doc();}, 'icon-retweet');
		}
		
		// delete
		if((cint(me.frm.doc.docstatus) != 1) && !me.frm.doc.__islocal 
			&& wn.model.can_delete(me.frm.doctype)) {
			this.appframe.add_dropdown_button("File", wn._("Delete"), function() { 
				me.frm.savetrash();}, 'icon-remove-sign');
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
			this._has_workflow = wn.model.get("Workflow", {document_type: this.frm.doctype}).length;
		return this._has_workflow;
	},
	get_docstatus: function() {
		return cint(this.frm.doc.docstatus);
	},
	show_linked_with: function() {
		if(!this.frm.linked_with) {
			this.frm.linked_with = new wn.ui.form.LinkedWith({
				frm: this.frm
			});
		}
		this.frm.linked_with.show();
	},
	set_title_right: function() {
		var me = this,
			current = this.appframe.get_title_right_text(),
			status = null;
		
		if(this.can_submit()) {
			status = "Submit";
		} else if(this.can_save()) {
			if(!this.frm.save_disabled) {
				status = "Save";
			}
		} else if(this.can_update()) {
			status = "Update";
		} else if(this.can_cancel()) {
			status = "Cancel";
		} else if(this.can_amend()) {
			status = "Amend";
		}
		
		if(status) {
			if(status!==current) {
				this.appframe.set_title_right(status, {
					"Save": function() { me.frm.save('Save', null, this); },
					"Submit": function() { me.frm.savesubmit(this); },
					"Update": function() { me.frm.save('Update', null, this); },
					"Cancel": function() { me.frm.savecancel(this); },
					"Amend": function() { me.frm.amend_doc(); }
				}[status], null, status==="Cancel" ? "btn-default" : "btn-primary");
			}
		} else {
			this.appframe.set_title_right();
		}

	},
	make_cancel_amend_button: function() {
		var me = this;
		var docstatus = cint(this.frm.doc.docstatus);
		var p = this.frm.perm[0];
		var has_workflow = this.has_workflow();
		
		if(has_workflow) {
			return;
		} else if(docstatus==1 && p[CANCEL]) {
			this.appframe.add_button('Cancel', function() { 
				me.frm.savecancel(this) }, 'icon-remove');
		} else if(docstatus==2 && p[AMEND]) {
			this.appframe.add_button('Amend', function() { 
				me.frm.amend_doc() }, 'icon-pencil', true);
		}
	},
	add_update_button_on_dirty: function() {
		var me = this;
		$(this.frm.wrapper).on("dirty", function() {
			me.show_title_as_dirty();
		})
	},
	show_title_as_dirty: function() {
		if(this.frm.save_disabled)
			return;

		this.appframe.get_title_area()
			.toggleClass("text-warning", this.frm.doc.__unsaved ? true : false)
		this.set_title();
		this.set_title_right();
	}
})