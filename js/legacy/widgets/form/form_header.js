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
		this.appframe.$titlebar.append('<span class="label-area"></span>\
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
			0: ['Draft', ''],
			1: ['Submitted', 'label-info'],
			2: ['Cancelled', 'label-important']
		}[cint(cur_frm.doc.docstatus)];
		
		if(cur_frm.doc.__unsaved) {
			labinfo[1] = 'label-warning'
		}
		
		this.$w.find('.label-area').html(repl('<span class="label %(lab_class)s">\
			%(lab_status)s</span>', {
				lab_status: labinfo[0],
				lab_class: labinfo[1]
			}));		
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
			this.appframe.add_button('Update', function() { cur_frm.savesubmit();}, '');
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

/*
_f.FrmHeader = function(parent, frm) {
	var me = this;
	this.wrapper = $a(parent, 'div');
	if(frm.meta.in_dialog) $y(this.wrapper, {marginLeft:'8px', marginRight:'8px'});

	this.page_head = new PageHeader(this.wrapper);
	wn.views.breadcrumbs(this.page_head.breadcrumbs, frm.meta.module, frm.meta.name);
	
	// doctype
	this.dt_area = $a(this.page_head.main_head, 'span', '', {marginRight:'8px', display:'inline'})
	
	// name
	var div = $a(null, 'div', '', {marginBottom:'4px'}); 
	
	this.page_head.wrapper.insertBefore(div, this.page_head.sub_head);
	this.dn_area = $a(div, 'span', '', {fontSize:'14px', fontWeight:'normal', marginRight:'8px', padding: '2px'})
	
	// status
	this.status_area = $a(div, 'span', '', {marginRight:'8px', marginBottom:'2px', cursor:'pointer', textShadow:'none'})
}
_f.FrmHeader.prototype.show = function() {  $ds(this.wrapper); }
_f.FrmHeader.prototype.hide = function() {  $dh(this.wrapper); }

// toolbar buttons
// =======================================================================

_f.FrmHeader.prototype.refresh= function() {

	var me = this;
	var p = cur_frm.get_doc_perms();
	
	this.page_head.clear_toolbar();

	// Edit
	if(cur_frm.meta.read_only_onload && !cur_frm.doc.__islocal) {
		if(!cur_frm.editable)
				this.page_head.add_button('Edit', function() { 
					cur_frm.edit_doc();
				}, 1, 'icon-pencil', 1
			);
		else
			this.page_head.add_button('Print View', function() { 
				cur_frm.is_editable[cur_frm.docname] = 0;				
				cur_frm.refresh(); }, 1, 'icon-print' );	
	}

	
	// Save
	if(cur_frm.editable && cint(cur_frm.doc.docstatus)==0 && p[WRITE])
		this.page_head.add_button('Save', function() { cur_frm.save('Save');}, 1, '',1);
	
	// Submit
	if(cint(cur_frm.doc.docstatus)==0 && p[SUBMIT] && (!cur_frm.doc.__islocal))
		this.page_head.add_button('Submit', function() { cur_frm.savesubmit(); }, 0, 'icon-lock');

	// Update after sumit
	if(cint(cur_frm.doc.docstatus)==1 && p[SUBMIT]) {
		this.update_btn = this.page_head.add_button('Update', function() { cur_frm.saveupdate(); }, 1, 'icon-ok', 1);
		if(!cur_frm.doc.__unsaved) $dh(this.update_btn);
	}
	
	// Cancel
	if(cint(cur_frm.doc.docstatus)==1  && p[CANCEL])
		this.page_head.add_button('Cancel', function() { cur_frm.savecancel() }, 0, 'icon-remove');

	// Amend
	if(cint(cur_frm.doc.docstatus)==2  && p[AMEND])
		this.page_head.add_button('Amend', function() { cur_frm.amend_doc() }, 0, 'icon-pencil');

}

_f.FrmHeader.prototype.show_toolbar = function() { $ds(this.wrapper); this.refresh(); }
_f.FrmHeader.prototype.hide_toolbar = function() { $dh(this.wrapper); }

// refresh toolbar
// -------------------------------------------------------------------

_f.FrmHeader.prototype.refresh_toolbar = function() {
	var m = cur_frm.meta;
	
	if(m.hide_heading || cur_frm.in_dialog) {
		// no heading... poof
		this.hide(); 
	} else {
		this.show();
		
		// with or without toolbar?
		if(m.hide_toolbar) { 
			this.hide_toolbar();
		} else {
			this.show_toolbar();
		}
	}
	//this.refresh_comments();
}


// make the status tag
// -------------------------------------------------------------------

_f.FrmHeader.prototype.get_status_tags = function(doc, f) {

	var make_tag = function(label, col) {
		var s= $a(null, 'span', '', {padding: '2px', backgroundColor:col, color:'#FFF', fontWeight:'bold', marginLeft:(f.meta.issingle ? '0px' : '8px'), fontSize:'11px'});
		$(s).css('-moz-border-radius','3px').css('-webkit-border-radius','3px')
		s.innerHTML = label;
		return s;
	}

	var sp1 = null; var sp2 = null;
	if(doc.__islocal) {
		label = 'Unsaved Draft'; col = '#F81';

	} else if(cint(doc.__unsaved)) {
		label = 'Not Saved'; col = '#F81';
		if(doc.docstatus==1 && this.update_btn) $ds(this.update_btn);

	} else if(cint(doc.docstatus)==0) {
		label = 'Saved'; col = '#0A1';

		// if submittable, show it
		if(f.get_doc_perms()[SUBMIT]) {
			sp2 = make_tag('To Be Submitted', '#888');
		}

	} else if(cint(doc.docstatus)==1) {
		label = 'Submitted'; col = '#44F';

	} else if(cint(doc.docstatus)==2) {
		label = 'Cancelled'; col = '#F44';
	}

	sp1 = make_tag(label, col);
	this.set_in_recent(doc, col);

	return [sp1, sp2];
}

// refresh "recent" tag colour
// -------------------------------------------------------------------

_f.FrmHeader.prototype.set_in_recent = function(doc, col) {
	var tn = $i('rec_'+doc.doctype+'-'+doc.name);
	if(tn)
		$y(tn,{backgroundColor:col}); 
}

// set the button color of save / submit
_f.FrmHeader.prototype.set_save_submit_color = function(doc) {
	
	var save_btn = this.page_head.buttons['Save'];
	var submit_btn = this.page_head.buttons['Submit'];
	
	if(cint(doc.docstatus)==0 && submit_btn && save_btn) {
		if(cint(doc.__unsaved)) {
			$(save_btn).addClass('btn-info');
			$(save_btn).find('i').addClass('icon-white');

			$(submit_btn).removeClass('btn-info');
			$(submit_btn).find('i').removeClass('icon-white');
		} else {
			$(submit_btn).addClass('btn-info');
			$(submit_btn).find('i').addClass('icon-white');

			$(save_btn).removeClass('btn-info');
			$(save_btn).find('i').removeClass('icon-white');
		}
	}
}

// refresh the labels!
// -------------------------------------------------------------------

_f.FrmHeader.prototype.refresh_labels = function(f) {
	var ph = this.page_head;
	var me = this;
	
	// main title
	this.dt_area.innerHTML = get_doctype_label(f.doctype);
	
	if(f.meta.issingle) $(this.dn_area).toggle(false);
	
	// sub title
	this.dn_area.innerHTML = '';
	if(!f.meta.issingle)
		this.dn_area.innerHTML = f.docname;
	
	$(this.dn_area)
		.removeClass('background-fade-in')
		.css('background-color', '#ff8')

	// get the doc
	var doc = locals[f.doctype][f.docname];
	
	// get the tags
	var sl = this.get_status_tags(doc, f);

	// set save, submit color
	this.set_save_submit_color(doc);

	// add the tags
	var t = this.status_area;
	t.innerHTML = '';
	t.appendChild(sl[0]);
	if(sl[1])t.appendChild(sl[1]);

	setTimeout('$(cur_frm.frm_head.dn_area).addClass("background-fade-in")\
	.css("background-color", "white")', 1500)
}

*/