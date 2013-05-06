wn.provide("wn.ui.form");
wn.ui.form.Toolbar = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
		this.add_update_button_on_dirty();
	},
	make: function() {
		if(this.frm.meta.hide_toolbar) {
			this.frm.save_disabled = true;
			return;
		}
		this.appframe.clear_buttons();
		this.make_file_menu();
		this.make_view_menu();
		this.set_title_image();
		this.show_title_as_dirty();
	},
	get_dropdown_menu: function(label) {
		return this.appframe.add_dropdown(label);
	},
	set_title_image: function() {
		var img = this.frm.appframe.$w.find('.title-status-img').toggle(false);
		if(this.frm.doc.docstatus==1) {
			img.attr("src", "lib/images/ui/submitted.png").toggle(true);
		}
		else if(this.frm.doc.docstatus==2) {
			img.attr("src", "lib/images/ui/cancelled.png").toggle(true);
		}
	},
	make_file_menu: function() {
		var me = this;
		var p = this.frm.perm[0];
		var docstatus = cint(this.frm.doc.docstatus);

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
		
		// copy
		if(in_list(profile.can_create, me.frm.doctype) && !me.frm.meta.allow_copy) {
			this.appframe.add_dropdown_button("File", wn._("Make Copy"), function() { 
				me.frm.copy_doc();}, 'icon-file');
		}
		
		// rename
		if(me.frm.meta.allow_rename && me.frm.perm[0][WRITE]) {
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
	make_view_menu: function() {
		var me = this;
		// Edit
		if(this.frm.meta.read_only_onload && !this.frm.doc.__islocal) {
			this.appframe.add_dropdown_button("View", wn._('Print View'), function() { 
				me.frm.last_view_is_edit[me.frm.docname] = 0;
				me.frm.refresh(); }, 'icon-print');
		}

		if(this.frm.meta.read_only_onload && !this.frm.doc.__islocal) {
			this.appframe.add_dropdown_button("View", wn._('Edit'), function() { 
				me.frm.last_view_is_edit[me.frm.docname] = 1;
				me.frm.refresh(); }, 'icon-edit');
		}
		
		// Linked With
		if(!me.frm.doc.__islocal && !me.frm.meta.issingle) {
			this.appframe.add_dropdown_button("View", wn._('Linked With'), function() { 
				if(!me.frm.linked_with) {
					me.frm.linked_with = new wn.ui.form.LinkedWith({
						frm: me.frm
					});
				}
				me.frm.linked_with.show();
			}, "icon-link")
		}
		
		if(!this.frm.meta.issingle) {
			this.appframe.add_menu_divider("View");
			this.appframe.add_dropdown_button("View", 
				wn._(this.frm.doctype) + ' ' + wn._('List'), function() { 
					wn.set_route("List", me.frm.doctype);
				}, 'icon-list');

			this.appframe.add_dropdown_button("View", 
				wn._(this.frm.doctype) + ' ' + wn._('Report View'), function() { 
					wn.set_route("Report2", me.frm.doctype);
				}, 'icon-table');
		}
		
	},
	set_title_button: function() {
		var me = this;
		this.appframe.$w.find(".title-button-area").empty();
		var docstatus = cint(this.frm.doc.docstatus);
		var p = this.frm.perm[0];
		var has_workflow = wn.model.get("Workflow", {document_type: me.frm.doctype}).length;

		if(has_workflow && (this.frm.doc.__islocal || this.frm.doc.__unsaved)) {
			this.make_save_button();
		} else if(!has_workflow) {
			if(docstatus==0 && p[SUBMIT] && (!me.frm.doc.__islocal) 
				&& (!me.frm.doc.__unsaved)) {
				this.appframe.add_button('Submit', function() { 
					me.frm.savesubmit(this);}, 'icon-lock', true).addClass("btn-primary");
			}
			else if(docstatus==0) {
				this.make_save_button();
			}
			else if(docstatus==1  && p[CANCEL]) {
				this.appframe.add_dropdown_button("File", 'Cancel', function() { 
					me.frm.savecancel(this) }, 'icon-remove');
			}
			else if(docstatus==2  && p[AMEND]) {
				this.appframe.add_button('Amend', function() { 
					me.frm.amend_doc() }, 'icon-pencil', true);
			}
		}
	},
	make_save_button: function() {
		var me = this;
		this.appframe.add_button('Save', function() { 
			me.frm.save('Save', null, this);}, 'icon-save', true).addClass("btn-primary");
	},
	add_update_button_on_dirty: function() {
		var me = this;
		$(this.frm.wrapper).on("dirty", function() {
			me.show_title_as_dirty();
			
			// show update button if unsaved
			var docstatus = cint(me.frm.doc.docstatus);
			if(docstatus==1 && me.frm.perm[0][SUBMIT] 
				&& !me.appframe.$w.find(".action-update").length) {
				me.appframe.add_button("Update", function() { 
					me.frm.save('Update', null, me);
				}, 'icon-save', true).addClass("btn-primary action-update");
			}
		})
	},
	show_title_as_dirty: function() {
		this.appframe.get_title_area()
			.toggleClass("text-warning", this.frm.doc.__unsaved ? true : false);
		this.set_title_button();
	},
	make_actions_menu: function() {
		if(this.actions_setup) return;
		var menu = this.get_dropdown_menu("Actions");
		this.actions_setup = true;
	},
	refresh: function() {
		this.make();
	}
})