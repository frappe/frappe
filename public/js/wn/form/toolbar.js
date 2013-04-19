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
		this.set_title_button();
		this.show_title_as_dirty();
	},
	get_dropdown_menu: function(label) {
		return this.appframe.add_dropdown(label);
	},
	make_file_menu: function() {
		var me = this;
		var menu = this.get_dropdown_menu("File");
		var p = this.frm.perm[0];
		var docstatus = cint(this.frm.doc.docstatus);

		// New
		if(p[CREATE]) {
			this.appframe.add_dropdown_button("File", "New " + me.frm.doctype, function() { 
				new_doc(me.frm.doctype);}, 'icon-plus');
		}

		// Save
		if(docstatus==0 && p[WRITE] && !this.read_only) {
			this.appframe.add_dropdown_button("File", "Save", function() { 
				me.frm.save('Save', null, this);}, 'icon-save');
		}
		
		// Print
		if(!(me.frm.doc.__islocal || me.frm.meta.allow_print)) {
			this.appframe.add_dropdown_button("File", "Print...", function() { 
				me.frm.print_doc();}, 'icon-print');
		}

		// email
		if(!(me.frm.doc.__islocal || me.frm.meta.allow_email)) {
			this.appframe.add_dropdown_button("File", "Email...", function() { 
				me.frm.email_doc();}, 'icon-envelope');
		}
		
		// copy
		if(in_list(profile.can_create, me.frm.doctype) && !me.frm.meta.allow_copy) {
			this.appframe.add_dropdown_button("File", "Make Copy", function() { 
				me.frm.copy_doc();}, 'icon-file');
		}
		
		// rename
		if(me.frm.meta.allow_rename && me.frm.perm[0][WRITE]) {
			this.appframe.add_dropdown_button("File", "Rename...", function() { 
				me.frm.rename_doc();}, 'icon-retweet');
		}
		
		// delete
		if((cint(me.frm.doc.docstatus) != 1) && !me.frm.doc.__islocal 
			&& wn.model.can_delete(me.frm.doctype)) {
			this.appframe.add_dropdown_button("File", "Delete", function() { 
				me.frm.savetrash();}, 'icon-remove-sign');
		}
		
	},
	make_view_menu: function() {
		var me = this;
		var menu = this.get_dropdown_menu("View");
		// Edit
		if(this.frm.meta.read_only_onload && !this.frm.doc.__islocal) {
			this.appframe.add_dropdown_button("View", 'Print View', function() { 
				me.frm.last_view_is_edit[me.frm.docname] = 0;
				me.frm.refresh(); }, 'icon-print');
		}

		if(this.frm.meta.read_only_onload && !this.frm.doc.__islocal) {
			this.appframe.add_dropdown_button("View", 'Edit', function() { 
				me.frm.last_view_is_edit[me.frm.docname] = 1;
				me.frm.refresh(); }, 'icon-edit');
		}
		
		// Linked With
		if(!me.frm.doc.__islocal && !me.frm.meta.issingle) {
			this.appframe.add_dropdown_button("View", 'Linked With', function() { 
				if(!me.frm.linked_with) {
					me.frm.linked_with = new wn.ui.form.LinkedWith({
						frm: me.frm
					});
				}
				me.frm.linked_with.show();
			}, "icon-link")
		}
	},
	set_title_button: function() {
		var me = this;
		this.appframe.$w.find(".title-button-area").empty();
		var docstatus = cint(this.frm.doc.docstatus);
		var p = this.frm.perm[0];

		if(!wn.model.get("Workflow", {document_type: me.frm.doctype}).length) {
			if(docstatus==0 && p[SUBMIT] && (!me.frm.doc.__islocal)) {
				this.appframe.add_title_button('Submit', function() { 
					me.frm.savesubmit(this);}, 'icon-lock');
			}
			else if(docstatus==0) {
				this.appframe.add_title_button('Save', function() { 
					me.frm.save('Save', null, this);}, 'icon-save');
			}
			else if(docstatus==1  && p[CANCEL]) {
				this.appframe.add_title_button('Cancel', function() { 
					me.frm.savecancel(this) }, 'icon-remove');
			}
			else if(docstatus==2  && p[AMEND]) {
				this.appframe.add_title_button('Amend', function() { 
					me.frm.amend_doc() }, 'icon-pencil');
			}
		}
	},
	add_update_button_on_dirty: function() {
		var me = this;
		$(this.frm.wrapper).on("dirty", function() {
			me.show_title_as_dirty();
			
			// show update button if unsaved
			var docstatus = cint(me.frm.doc.docstatus);
			if(me.frm.doc.__unsaved && docstatus==1 && me.frm.perm[0][SUBMIT]) {
				me.appframe.add_dropdown_button("File", "Update", function() { 
					me.frm.save('Update', null, me);
				}, '').html(wn._('Update'))
			}
		})
	},
	show_title_as_dirty: function() {
		if(this.frm.doc.__unsaved) {
			this.appframe.get_title_area().addClass("text-warning");
		} else {
			this.appframe.get_title_area().removeClass("text-warning");
		}
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