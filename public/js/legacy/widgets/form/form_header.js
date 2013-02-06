// Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
// 
// MIT License (MIT)
// 
// Permission is hereby granted, free of charge, to any person obtaining a 
// copy of this software and associated documentation files (the "Software"), 
// to deal in the Software without restriction, including without limitation 
// the rights to use, copy, modify, merge, publish, distribute, sublicense, 
// and/or sell copies of the Software, and to permit persons to whom the 
// Software is furnished to do so, subject to the following conditions:
// 
// The above copyright notice and this permission notice shall be included in 
// all copies or substantial portions of the Software.
// 
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
// INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
// PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
// HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
// CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
// OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
// 

// features
// --------
// toolbar - standard and custom
// label - saved, submitted etc
// save / submit button toggle based on "saved" or not
// highlight and fade name based on refresh

_f.FrmHeader = Class.extend({
	init: function(parent, frm) {
		this.appframe = new wn.ui.AppFrame(parent, null, frm.meta.module)
		this.$w = this.appframe.$w;
		this.frm = frm;
		
		this.appframe.add_home_breadcrumb();
		this.appframe.add_module_breadcrumb(frm.meta.module)
		
		if(!frm.meta.issingle) {
			this.appframe.add_list_breadcrumb(frm.meta.name)
		}
		this.appframe.add_breadcrumb("icon-file");
	},
	refresh: function() {
		var title = this.frm.docname;
		if(title.length > 30) {
			title = title.substr(0,30) + "...";
		}
		this.appframe.set_title(title, wn._(this.frm.docname));
		this.refresh_labels();
		this.refresh_toolbar();
		this.refresh_timestamps();
	},
	refresh_timestamps: function() {
		this.$w.find(".avatar").remove();
		
		var doc = this.frm.doc;
		if(doc.__islocal || !doc.owner || !doc.modified_by) 
			return;
		
		$(repl('<span class="avatar avatar avatar-small">\
			<img title="%(created_by)s" src="%(avatar_created)s"/></span>\
			<span class="avatar avatar avatar-small">\
			<img title="%(modified_by)s" src="%(avatar_modified)s"/></span>', {
				created_by: wn.user_info(doc.owner).fullname,
				avatar_created: wn.utils.get_file_link(wn.user_info(doc.owner).image),
				modified_by: wn.user_info(doc.modified_by).fullname,
				avatar_modified: wn.utils.get_file_link(wn.user_info(doc.modified_by).image),
		})).insertAfter(this.$w.find(".appframe-title"));
		
		this.$w.find(".avatar:eq(0)").popover({
			trigger:"hover",
			title: wn._("Created By"),
			content: wn.user_info(this.frm.doc.owner).fullname 
				+" on "+ dateutil.str_to_user(this.frm.doc.creation)
		});

		this.$w.find(".avatar:eq(1)").popover({
			trigger:"hover",
			title: wn._("Modified By"),
			content: wn.user_info(this.frm.doc.modified_by).fullname 
				+" on "+ dateutil.str_to_user(this.frm.doc.modified)
		});
		
		this.$w.find('.avatar img').centerImage();
	},	
	refresh_labels: function() {
		var me = this;
		this.frm.doc = wn.model.get_doc(this.frm.doc.doctype, this.frm.doc.name);
		var labinfo = {
			0: [wn._('Saved'), 'label-success'],
			1: [wn._('Submitted'), 'label-info'],
			2: [wn._('Cancelled'), 'label-important']
		}[cint(this.frm.doc.docstatus)];
		
		if(labinfo[0]==wn._('Saved') && this.frm.meta.is_submittable) {
			labinfo[0]=wn._('Saved, to Submit');
		}
		
		if(this.frm.doc.__unsaved || this.frm.doc.__islocal) {
			labinfo[0] = wn._('Not Saved');
			labinfo[1] = 'label-warning'
		}

		this.set_label(labinfo);
		
		// show update button if unsaved
		if(this.frm.doc.__unsaved && cint(this.frm.doc.docstatus)==1 && this.frm.perm[0][SUBMIT]) {
			this.appframe.add_button('Update', function() { 
				me.frm.save('Update', null, this);
			}, '').html(wn._('Update'))
		}
		
		this.set_primary_button();
	},
	set_label: function(labinfo) {
		this.$w.find('.label').remove();
		if(this.frm.meta.hide_toolbar || this.frm.save_disabled) 
			return;
		$(repl('<span class="label %(lab_class)s">\
			%(lab_status)s</span>', {
				lab_status: labinfo[0],
				lab_class: labinfo[1]
			})).appendTo(this.$w.find('.appframe-subject'))
	},
	refresh_toolbar: function() {
		// clear
		var me = this;
		this.appframe.clear_buttons();

		if(this.frm.meta.hide_toolbar) {
			this.frm.save_disabled = true;
			return;
		}
		
		var p = this.frm.perm[0];

		// Edit
		if(this.frm.meta.read_only_onload && !this.frm.doc.__islocal) {
			this.appframe.add_button('Print View', function() { 
				me.frm.last_view_is_edit[me.frm.docname] = 0;				
				me.frm.refresh(); }, 'icon-print' ).html(wn._('Print View'));	
		}

		var docstatus = cint(this.frm.doc.docstatus);
		
		// Save
		if(docstatus==0 && p[WRITE] && !this.read_only) {
			this.appframe.add_button('Save', function() { 
				me.frm.save('Save', null, this);}, 'icon-save');
			this.appframe.buttons['Save'].addClass("btn-save")
				.html("<i class='icon-save'></i> "+wn._("Save"));
		}

		// Submit
		if(!wn.model.get("Workflow", {document_type: me.frm.doctype}).length) {
			if(docstatus==0 && p[SUBMIT] && (!me.frm.doc.__islocal))
				this.appframe.add_button('Submit', function() { 
					me.frm.savesubmit(this);}, 'icon-lock').html(wn._('Submit'));

			// Cancel
			if(docstatus==1  && p[CANCEL])
				this.appframe.add_button('Cancel', function() { 
					me.frm.savecancel(this) }, 'icon-remove').html(wn._('Cancel'));

			// Amend
			if(docstatus==2  && p[AMEND])
				this.appframe.add_button('Amend', function() { 
					me.frm.amend_doc() }, 'icon-pencil').html(wn._('Amend'));
		}
		this.set_primary_button();
	},
	set_primary_button: function() {
		if(!this.appframe.toolbar)
			return;

		var buttons = this.appframe.buttons;

		// highlight save
		this.appframe.toolbar.find("button").removeClass("btn-info");
		if(buttons["Save"]) {
			buttons["Save"].addClass("btn-info");
		}

		// highlight submit button
		if(buttons["Submit"] && !this.frm.doc.__unsaved) {
			this.appframe.toolbar.find("button").removeClass("btn-info");
			buttons["Submit"].addClass("btn-info");
		// highlight update button
		} else if(buttons["Update"] && this.frm.doc.__unsaved) {
			this.appframe.toolbar.find("button").removeClass("btn-info");
			buttons["Update"].addClass("btn-info");
		}
	},
	hide_close: function() {
		this.$w.find('.close').toggle(false);
	}
})
