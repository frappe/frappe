wn.provide("wn.ui.form");
wn.ui.form.Toolbar = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
		this.add_update_button_on_dirty();
		this.appframe.add_module_icon(this.frm.meta.module);
		this.appframe.set_views_for(this.frm.meta.name, "form");
	},
	make: function() {
		this.appframe.clear_buttons();
		this.set_title();
		this.set_title_image();
		this.show_title_as_dirty();

		if(this.frm.meta.hide_toolbar) {
			this.frm.save_disabled = true;
			return;
		}

		this.make_file_menu();
		this.make_view_menu();
		if(!this.frm.view_is_edit) {
			// print view
			this.show_print_toolbar();
		}
		this.show_infobar();
	},
	refresh: function() {
		this.make();
	},
	set_title: function() {
		var title = this.frm.docname;
		if(title.length > 30) {
			title = title.substr(0,30) + "...";
		}
		this.appframe.set_title(title, wn._(this.frm.docname));
	},
	show_infobar: function() {
		/* docs:
		Render info bar that shows timestamp, # of comments, # of attachments etc.
		only if saved doc. (doc.__islocal is falsy)
		*/
		var me = this;
		this.appframe.clear_infobar();
		if(this.frm.doc.__islocal)
			return;
		this.appframe.add_infobar(
			wn.user.full_name(this.frm.doc.modified_by) + " / " + comment_when(this.frm.doc.modified), function() {
			msgprint("Created By: " + wn.user.full_name(me.frm.doc.owner) + "<br>" +
				"Created On: " + dateutil.str_to_user(me.frm.doc.creation) + "<br>" +
				"Last Modified By: " + wn.user.full_name(me.frm.doc.modified_by) + "<br>" +
				"Last Modifed On: " + dateutil.str_to_user(me.frm.doc.modified), "History");
		})

		var comments = JSON.parse(this.frm.doc.__comments || "[]").length,
			attachments = keys(JSON.parse(this.frm.doc.file_list || "{}")).length,
			assignments = JSON.parse(this.frm.doc.__assign_to || "[]").length;
			
		var $li1 = this.appframe.add_infobar(comments + " " + (comments===1 ? 
			wn._("Comment") : wn._("Comments")),
			function() {
				$('html, body').animate({
					scrollTop: $(me.frm.wrapper).find(".form-comments").offset().top
				}, 2000);
			});
		comments > 0 && $li1.addClass("bold");

		var $li2 = this.appframe.add_infobar(attachments + " " + (attachments===1 ? 
			wn._("Attachment") : wn._("Attachments")),
			function() {
				$('html, body').animate({
					scrollTop: $(me.frm.wrapper).find(".form-attachments").offset().top
				}, 2000);
			});
		attachments > 0 && $li2.addClass("bold");
		
		var $li3 = this.appframe.add_infobar(assignments + " " + (assignments===1 ? 
			wn._("Assignment") : wn._("Assignments")),
			function() {
				$('html, body').animate({
					scrollTop: $(me.frm.wrapper).find(".form-assignments").offset().top
				}, 2000);
			})
		assignments > 0 && $li3.addClass("bold");
		
	},
	show_print_toolbar: function() {
		var me = this;
		this.appframe.add_button("Edit", function() {
			me.frm.edit_doc();
			return false;
		})
		this.frm.$print_view_select = 
			this.appframe.add_select("Print Format", this.frm.print_formats)
				.val(this.frm.print_formats[0])
				.change(function() {
					me.frm.refresh_print_layout();
				});
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
	},
	set_title_button: function() {
		var me = this;
		var docstatus = cint(this.frm.doc.docstatus);
		var p = this.frm.perm[0];
		var has_workflow = wn.model.get("Workflow", {document_type: me.frm.doctype}).length;

		// remove existing title buttons
		this.appframe.toolbar.find(".btn-title").remove();
		
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
	}
})