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

_f.FrmHeader = function(parent, frm) {
	var me = this;
	this.wrapper = $a(parent, 'div');
	if(frm.meta.in_dialog) $y(this.wrapper, {marginLeft:'8px', marginRight:'8px'});

	this.page_head = new PageHeader(this.wrapper);
	
	// doctype
	this.dt_area = $a(this.page_head.main_head, 'h1', '', {marginRight:'8px', display:'inline'})
	
	// name
	var div = $a(null, 'div', '', {marginBottom:'4px'}); 
	
	this.page_head.lhs.insertBefore(div, this.page_head.sub_head);
	this.dn_area = $a(div, 'span', '', {fontSize:'14px', fontWeight:'normal', marginRight:'8px'})
	
	// status
	this.status_area = $a(div, 'span', '', {marginRight:'8px', marginBottom:'2px', cursor:'pointer', textShadow:'none'})

	// timestamp
	this.timestamp_area = $a($a(div,'div','',{marginTop:'3px'}), 'span', 'field_description', {fontSize:'11px'});
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
				}, 1, 'ui-icon-document', 1
			);
		else
			this.page_head.add_button('Print View', function() { 
				cur_frm.is_editable[cur_frm.docname] = 0;				
				cur_frm.refresh(); }, 1, 'ui-icon-document' );	
	}

	
	// Save
	if(cur_frm.editable && cint(cur_frm.doc.docstatus)==0 && p[WRITE])
		this.page_head.add_button('Save', function() { cur_frm.save('Save');}, 1, 'ui-icon-disk',1);
	
	// Submit
	if(cint(cur_frm.doc.docstatus)==0 && p[SUBMIT] && (!cur_frm.doc.__islocal))
		this.page_head.add_button('Submit', function() { cur_frm.savesubmit(); }, 0, 'ui-icon-locked');

	// Update after sumit
	if(cint(cur_frm.doc.docstatus)==1 && p[SUBMIT]) {
		this.update_btn = this.page_head.add_button('Update', function() { cur_frm.saveupdate(); }, 1, 'ui-icon-disk', 1);
		if(!cur_frm.doc.__unsaved) $dh(this.update_btn);
	}
	
	// Cancel
	if(cint(cur_frm.doc.docstatus)==1  && p[CANCEL])
		this.page_head.add_button('Cancel', function() { cur_frm.savecancel() }, 0, 'ui-icon-closethick');

	// Amend
	if(cint(cur_frm.doc.docstatus)==2  && p[AMEND])
		this.page_head.add_button('Amend', function() { cur_frm.amend_doc() }, 0, 'ui-icon-scissors');

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

/*_f.FrmHeader.prototype.refresh_comments = function() {
	var n = cint(cur_frm.n_comments[cur_frm.doc.name]);
	if(this.comment_btn && !cur_frm.doc.__islocal)
		this.comment_btn.innerHTML = 'Comments ('+n+')';
}*/

// refresh heading and labels
// -------------------------------------------------------------------

_f.FrmHeader.prototype.get_timestamp = function(doc) {
	var scrub_date = function(d) {
		if(d)t=d.split(' ');else return '';
		return dateutil.str_to_user(t[0]) + ' ' + t[1];
	}
	
	return repl("Created: %(c_by)s %(c_on)s %(m_by)s %(m_on)s", 
		{c_by:doc.owner
		,c_on:scrub_date(doc.creation ? doc.creation:'')
		,m_by:doc.modified_by?(' | Modified: '+doc.modified_by):''
		,m_on:doc.modified ? ('on '+scrub_date(doc.modified)) : ''} );
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
			$(submit_btn).removeClass('btn-info');
		} else {
			$(submit_btn).addClass('btn-info');
			$(save_btn).removeClass('btn-info');
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
	
	// sub title
	this.dn_area.innerHTML = '';
	if(!f.meta.issingle)
		this.dn_area.innerHTML = f.docname;

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

	// timestamp
	this.timestamp_area.innerHTML = me.get_timestamp(doc);	
}
