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
// breadcrumbs
// save / submit button toggle based on "saved" or not
// highlight and fade name based on refresh

_f.FrmHeader = Class.extend({
	init: function(parent, frm) {
		this.appframe = new wn.ui.AppFrame(parent)
		this.appframe.$titlebar.append('</span>\
				<span class="breadcrumb-area"></span>');
		this.$w = this.appframe.$w;
	},
	refresh: function() {
		// refresh breadcrumbs
		wn.views.breadcrumbs($(this.$w.find('.breadcrumb-area')), 
			cur_frm.meta.module, cur_frm.meta.name, cur_frm.docname);
			
		this.refresh_labels();
		this.refresh_toolbar();
		
	},
	refresh_labels: function() {
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
			})).insertBefore(this.$w.find('.breadcrumb-area'))
	},
	refresh_toolbar: function() {
		// clear
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
			this.appframe.add_button('Save', function() { cur_frm.save('Save');}, '');
			this.appframe.buttons['Save'].addClass('btn-info');			
		}
		// Submit
		if(docstatus==0 && p[SUBMIT] && (!cur_frm.doc.__islocal))
			this.appframe.add_button('Submit', function() { cur_frm.savesubmit();}, 'icon-lock');

		// Update after sumit
		if(docstatus==1 && p[SUBMIT]) {
			this.appframe.add_button('Update', function() { cur_frm.saveupdate();}, '');
			if(!cur_frm.doc.__unsaved) this.appframe.buttons['Update'].toggle(false);
		}

		// Cancel
		if(docstatus==1  && p[CANCEL])
			this.appframe.add_button('Cancel', function() { cur_frm.savecancel() }, 'icon-remove');

		// Amend
		if(docstatus==2  && p[AMEND])
			this.appframe.add_button('Amend', function() { cur_frm.amend_doc() }, 'icon-pencil');

	},
	show: function() {
	},
	hide: function() {
		
	},
	hide_close: function() {
		this.$w.find('.close').toggle(false);
	}
})
