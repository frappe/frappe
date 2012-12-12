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
		
		if(!frm.meta.issingle) {
			this.appframe.add_tab(frm.doctype + " List", 0.5, function() {
				wn.set_route("List", frm.doctype);
			});
		}
		this.appframe.add_module_tab(frm.meta.module);		
	},
	refresh: function() {
		this.appframe.set_title(this.frm.docname);
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
			content: wn.user_info(this.frm.doc.owner).fullname.bold() 
				+" on "+ dateutil.str_to_user(this.frm.doc.creation)
		});

		this.$w.find(".avatar:eq(1)").popover({
			trigger:"hover",
			title: wn._("Modified By"),
			content: wn.user_info(this.frm.doc.modified_by).fullname.bold() 
				+" on "+ dateutil.str_to_user(this.frm.doc.modified)
		});
		
		this.$w.find('.avatar img').centerImage();
	},	
	refresh_labels: function() {
		cur_frm.doc = get_local(cur_frm.doc.doctype, cur_frm.doc.name);
		var labinfo = {
			0: ['Saved', 'label-success'],
			1: ['Submitted', 'label-info'],
			2: ['Cancelled', 'label-important']
		}[cint(cur_frm.doc.docstatus)];
		
		if(labinfo[0]=='Saved' && cur_frm.meta.is_submittable) {
			labinfo[0]='Saved, to Submit';
		}
		
		if(cur_frm.doc.__unsaved || cur_frm.doc.__islocal) {
			labinfo[0] = 'Not Saved';
			labinfo[1] = 'label-warning'
		}

		this.set_label(labinfo);
		
		// show update button if unsaved
		if(cur_frm.doc.__unsaved && cint(cur_frm.doc.docstatus)==1 && this.appframe.buttons['Update']) {
			this.appframe.buttons['Update'].toggle(true);
		}
		
	},
	set_label: function(labinfo) {
		this.$w.find('.label').remove();
		$(repl('<span class="label %(lab_class)s">\
			%(lab_status)s</span>', {
				lab_status: labinfo[0],
				lab_class: labinfo[1]
			})).insertBefore(this.$w.find('.appframe-title'))
	},
	refresh_toolbar: function() {
		// clear
		
		if(cur_frm.meta.hide_toolbar) {
			$('.appframe-toolbar').toggle(false);
			return;
		}
		
		this.appframe.clear_buttons();
		var p = cur_frm.get_doc_perms();

		// Edit
		if(cur_frm.meta.read_only_onload && !cur_frm.doc.__islocal) {
			if(!cur_frm.editable)
				this.appframe.add_button('Edit', function() { 
					cur_frm.edit_doc();
				},'icon-pencil');
			else
				this.appframe.add_button('Print View', function() { 
					cur_frm.is_editable[cur_frm.docname] = 0;				
					cur_frm.refresh(); }, 'icon-print' );	
		}

		var docstatus = cint(cur_frm.doc.docstatus);
		// Save
		if(docstatus==0 && p[WRITE]) {
			this.appframe.add_button('Save', function() { 
				cur_frm.save('Save', null, this);}, '');
			this.appframe.buttons['Save'].addClass('btn-info').text("Save (Ctrl+S)");			
		}
		// Submit
		if(docstatus==0 && p[SUBMIT] && (!cur_frm.doc.__islocal))
			this.appframe.add_button('Submit', function() { 
				cur_frm.savesubmit(this);}, 'icon-lock');

		// Update after sumit
		if(docstatus==1 && p[SUBMIT]) {
			this.appframe.add_button('Update', function() { 
				cur_frm.save('Update', null, this);
			}, '');
			if(!cur_frm.doc.__unsaved) this.appframe.buttons['Update'].toggle(false);
		}

		// Cancel
		if(docstatus==1  && p[CANCEL])
			this.appframe.add_button('Cancel', function() { 
				cur_frm.savecancel(this) }, 'icon-remove');

		// Amend
		if(docstatus==2  && p[AMEND])
			this.appframe.add_button('Amend', function() { 
				cur_frm.amend_doc() }, 'icon-pencil');
			
		// Help
		if(cur_frm.meta.description) {
			this.appframe.add_help_button(wn.markdown('#### ' + cur_frm.doctype + '\n\n'
				+ cur_frm.meta.description));
		}

	},
	show: function() {
	},
	hide: function() {
		
	},
	hide_close: function() {
		this.$w.find('.close').toggle(false);
	}
})
