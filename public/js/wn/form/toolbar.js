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

		if(!this.frm.view_is_edit) {
			// print view
			this.show_print_toolbar();
		}

		this.show_title_as_dirty();

		if(this.frm.meta.hide_toolbar) {
			this.frm.save_disabled = true;
			return;
		}
		this.make_file_menu();
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

		this.make_infobar_docinfo_links();
		this.make_infobar_side_icons();
	},
	make_infobar_docinfo_links: function() {
		var me = this,
			docinfo = wn.model.docinfo[this.frm.doctype][this.frm.docname],
			comments = docinfo.comments.length,
			attachments = keys(docinfo.attachments).length,
			assignments = docinfo.assignments.length;
			
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
	make_infobar_side_icons: function() {
		var me = this;
		this.appframe.$w.find(".form-icon").remove();

		if(!this.frm.meta.issingle) {
			$('<i class="icon-arrow-right pull-right form-icon" title="Next Record"></i>')
				.click(function() {
					me.go_prev_next(false);
				})
				.appendTo(this.appframe.$w.find(".info-bar"));		

			$('<i class="icon-arrow-left pull-right form-icon" title="Previous Record"></i>')
				.click(function() {
					me.go_prev_next(true);
				})
				.appendTo(this.appframe.$w.find(".info-bar"));		
		}

		if(!me.frm.meta.allow_print) {
			$('<i class="icon-print pull-right form-icon" title="Print"></i>')
				.click(function() {
					me.frm.print_doc();
				})
				.appendTo(this.appframe.$w.find(".info-bar"));
		}
		
		if(!me.frm.meta.allow_email) {
			$('<i class="icon-envelope pull-right form-icon" title="Email"></i>')
				.click(function() {
					me.frm.email_doc();
				})
				.appendTo(this.appframe.$w.find(".info-bar"));		
		}
		
	},
	show_print_toolbar: function() {
		var me = this;
		this.appframe.add_button("Edit", function() {
			me.frm.edit_doc();
			return false;
		}, 'icon-pencil')
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
	set_docstatus_label: function() {
		var status_bar_parent = this.frm.appframe.$w.find(".status-bar").empty();
		if(this.frm.meta.is_submittable && !this.frm.doc.__islocal) {
			var status_bar = $("<h4>")
				.appendTo(status_bar_parent);

			switch(this.frm.doc.docstatus) {
				case 0:
					$('<span class="label"><i class="icon-unlock"> To Submit</span>')
						.appendTo(status_bar);
					break;
				case 1:
					$('<span class="label label-success"><i class="icon-lock"> Submitted</span>')
						.appendTo(status_bar);
					break;
				case 2:
					$('<span class="label label-danger"><i class="icon-remove"> Cancelled</span>')
						.appendTo(status_bar);
					break;
			}
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

		// Linked With
		if(!me.frm.doc.__islocal && !me.frm.meta.issingle) {
			this.appframe.add_dropdown_button("File", wn._('Linked With'), function() { 
				if(!me.frm.linked_with) {
					me.frm.linked_with = new wn.ui.form.LinkedWith({
						frm: me.frm
					});
				}
				me.frm.linked_with.show();
			}, "icon-link")
		}
		
		// copy
		if(in_list(profile.can_create, me.frm.doctype) && !me.frm.meta.allow_copy) {
			this.appframe.add_dropdown_button("File", wn._("Copy"), function() { 
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
	set_title_button: function() {
		var me = this;
		var docstatus = cint(this.frm.doc.docstatus);
		var p = this.frm.perm[0];
		var has_workflow = wn.model.get("Workflow", {document_type: me.frm.doctype}).length;

		// remove existing title buttons
		this.appframe.toolbar.find(".btn-title").remove();
		
		// Print Preview
		if(this.frm.meta.read_only_onload && !this.frm.doc.__islocal && this.frm.view_is_edit) {
			this.appframe.add_button(wn._('Preview'), function() { 
				me.frm.last_view_is_edit[me.frm.docname] = 0;
				me.frm.refresh(); }, 'icon-print');
		}
		
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
				this.appframe.add_button('Cancel', function() { 
					me.frm.savecancel(this) }, 'icon-remove');
			}
			else if(docstatus==2  && p[AMEND]) {
				this.appframe.add_button('Amend', function() { 
					me.frm.amend_doc() }, 'icon-pencil', true);
			}
		}
	},
	make_save_button: function() {
		if(this.frm.save_disabled)
			return;
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
		if(this.frm.save_disabled)
			return;

		this.appframe.get_title_area()
			.toggleClass("text-warning", this.frm.doc.__unsaved ? true : false);
		this.set_title_button();
		this.set_docstatus_label();
	},
	make_actions_menu: function() {
		if(this.actions_setup) return;
		var menu = this.get_dropdown_menu("Actions");
		this.actions_setup = true;
	},
	go_prev_next: function(prev) {
		var me = this;
		wn.call({
			method: "webnotes.widgets.form.utils.get_next",
			args: {
				doctype: me.frm.doctype,
				name: me.frm.docname,
				prev: prev ? 1 : 0
			},
			callback: function(r) {
				if(r.message)
					wn.set_route("Form", me.frm.doctype, r.message);
			}
		});
	},
	
})