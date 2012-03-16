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

// FrmDialog - twin of FrmContainer
// =======================================================================
_f.frm_dialog = null;
_f.calling_doc_stack = [];
_f.temp_access = {};

_f.FrmDialog = function() {
	var me = this;
	this.last_displayed = null;

	var d = new Dialog(640, null, 'Edit Row');
	this.body = $a(d.body, 'div', 'dialog_frm');
	$y(d.body, {backgroundColor:'#EEE'});
	d.done_btn_area = $a(d.body, 'div', '', {margin:'8px'});

	// done button
	me.on_complete = function() { 

		if(me.table_form) {
			// table form, just hide the dialog (saving will be done with the parent)
			me.dialog.hide();
		} else {
			// form in dialog, so save it
			var callback = function(r) {
				var dn = cur_frm.docname;
				if(!r.exc) {
					// check if there is another dialog open?
					me.dialog.hide();
				}

				// callback
				if(me.on_save_callback)
					me.on_save_callback(dn);
			}
			cur_frm.save('Save', callback);
		}
	}

	// set title onshow
	// -------------------------------------------
	d.onshow = function() {
		// set the dialog title
		d.done_btn_area.innerHTML = '';
		d.done_btn = $btn(d.done_btn_area, 'Save', null, null, 'green');
		d.done_btn.onclick = function() { me.on_complete() };
		if(me.table_form) {
			d.set_title("Editing Row #" + (_f.cur_grid_ridx+1));
			d.done_btn.innerHTML = 'Done Editing';
		} else {
			d.set_title(cur_frm.doctype==cur_frm.doctype ? (cur_frm.doctype) : (cur_frm.doctype + ': ' + cur_frm.docname));
			d.done_btn.innerHTML = 'Save';
		}
	}

	// on hide, refresh grid or call onsave
	// -------------------------------------------
	d.onhide = function() {
		// if called from grid, refresh the row
		if(_f.cur_grid)
			_f.cur_grid.refresh_row(_f.cur_grid_ridx, me.dn);
		
		// set the new global cur_frm (if applicable)
		if(wn.container.page.frm) {
			cur_frm = wn.container.page.frm;
		}
	}
	this.dialog = d;
}