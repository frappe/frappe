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

cur_frm.cscript.doc_type = function(doc, dt, dn) {
	$c_obj(make_doclist(dt, dn), 'get', '', function(r, rt) {
		cur_frm.refresh();
	});
}

cur_frm.cscript.onload = function(doc, dt, dn) {
	$('div.grid_tbarlinks').parent().toggle(false);
	cur_frm.add_fields_help();
}

cur_frm.cscript.refresh = function(doc, dt, dn) {
	cur_frm.frm_head.appframe.clear_buttons();

	cur_frm.add_custom_button('Update', function() {
		if(cur_frm.fields_dict['doc_type'].value) {
			$c_obj(make_doclist(dt, dn), 'post', '', function(r, rt) {
				if(r.exc) {
					msgprint(r.exc);
				} else {
					if(r.server_messages) { cur_frm.cscript.doc_type(doc, doc.doctype, doc.name); }
				cur_frm.frm_head.set_label(['Saved', 'label-success']);				
				}
			});	
		}
	},1);
	
	cur_frm.add_custom_button('Refresh Form', function() {
		cur_frm.cscript.doc_type(doc, dt, dn);
	}, 1);
	
	cur_frm.add_custom_button('Reset to defaults', function() {
		cur_frm.confirm('This will <b>remove the customizations</b> defined for this form.<br /><br />' 
		+ 'Are you sure you want to <i>reset to defaults</i>?', doc, dt, dn);
	}, 1);

	if(!doc.doc_type) {
		var frm_head = cur_frm.frm_head.appframe;
		$(frm_head.buttons['Update']).attr('disabled', true);
		$(frm_head.buttons['Refresh Form']).attr('disabled', true);
		$(frm_head.buttons['Reset to defaults']).attr('disabled', true);
	}

	cur_frm.cscript.hide_allow_attach(doc, dt, dn);
}

cur_frm.cscript.hide_allow_attach = function(doc, dt, dn) {
	var allow_attach_list = ['Website Settings', 'Web Page', 'Timesheet', 'Ticket',
		'Support Ticket', 'Supplier', 'Style Settings', 'Stock Reconciliation',
		'Stock Entry', 'Serial No', 'Sales Order', 'Sales Invoice',
		'Quotation', 'Question', 'Purchase Receipt', 'Purchase Order',
		'Project', 'Profile', 'Production Order', 'Product', 'Print Format',
		'Price List', 'Purchase Invoice', 'Page', 'Module Def',
		'Maintenance Visit', 'Maintenance Schedule', 'Letter Head',
		'Leave Application', 'Lead', 'Journal Voucher', 'Item', 'Purchase Request',
		'Expense Claim', 'Opportunity', 'Employee', 'Delivery Note',
		'Customer Issue', 'Customer', 'Contact Us Settings', 'Company',
		'Blog', 'BOM', 'About Us Settings'];
	
	if(inList(allow_attach_list, doc.doc_type)) {
		unhide_field('allow_attach');
	} else {
		hide_field('allow_attach');
	}
}

cur_frm.confirm = function(msg, doc, dt, dn) {
	var d = new wn.widgets.Dialog({
		title: 'Reset To Defaults',
		width: 500
	});

	$y(d.body, {padding: '32px', textAlign: 'center'});

	$a(d.body, 'div', '', '', msg);

	var button_wrapper = $a(d.body, 'div');
	$y(button_wrapper, {paddingTop: '15px'});
	
	var proceed_btn = $btn(button_wrapper, 'Proceed', function() {
		$c_obj(make_doclist(dt, dn), 'delete', '', function(r, rt) {
			//console.log(arguments);
			if(r.exc) {
				msgprint(r.exc);
			} else {
				cur_frm.confirm.dialog.hide();
				cur_frm.refresh();
				cur_frm.frm_head.set_label(['Saved', 'label-success']);
			}
		});	
	});

	$y(proceed_btn, {marginRight: '20px', fontWeight: 'bold'});

	var cancel_btn = $btn(button_wrapper, 'Cancel', function() {
		cur_frm.confirm.dialog.hide();
	});

	$(cancel_btn).addClass('btn-small btn-info');
	$y(cancel_btn, {fontWeight: 'bold'});

	cur_frm.confirm.dialog = d;
	d.show();
}


cur_frm.add_fields_help = function() {
	$(cur_frm.grids[0].parent).before(
		'<div style="padding: 10px">\
			<a id="fields_help" class="link_type">Help</a>\
		</div>');
	$('#fields_help').click(function() {
		var d = new wn.widgets.Dialog({
			title: 'Help: Field Properties',
			width: 600
		});

		var help =
			"<table cellspacing='25'>\
				<tr>\
					<td><b>Label</b></td>\
					<td>Set the display label for the field</td>\
				</tr>\
				<tr>\
					<td><b>Type</b></td>\
					<td>Change type of field. (Currently, Type change is \
						allowed among 'Currency and Float')</td>\
				</tr>\
				<tr>\
					<td width='25%'><b>Options</b></td>\
					<td width='75%'>Specify the value of the field</td>\
				</tr>\
				<tr>\
					<td><b>Perm Level</b></td>\
					<td>\
						Assign a permission level to the field.<br />\
						(Permissions can be managed via Setup &gt; Permission Manager)\
					</td>\
				</tr>\
				<tr>\
					<td><b>Width</b></td>\
					<td>\
						Width of the input box<br />\
						Example: <i>120px</i>\
					</td>\
				</tr>\
				<tr>\
					<td><b>Reqd</b></td>\
					<td>Mark the field as Mandatory</td>\
				</tr>\
				<tr>\
					<td><b>In Filter</b></td>\
					<td>Use the field to filter records</td>\
				</tr>\
				<tr>\
					<td><b>Hidden</b></td>\
					<td>Hide field in form</td>\
				</tr>\
				<tr>\
					<td><b>Print Hide</b></td>\
					<td>Hide field in Standard Print Format</td>\
				</tr>\
				<tr>\
					<td><b>Report Hide</b></td>\
					<td>Hide field in Report Builder</td>\
				</tr>\
				<tr>\
					<td><b>Allow on Submit</b></td>\
					<td>Allow field to remain editable even after submission</td>\
				</tr>\
				<tr>\
					<td><b>Depends On</b></td>\
					<td>\
						Show field if a condition is met<br />\
						Example: <code>eval:doc.status=='Cancelled'</code>\
						 on a field like \"reason_for_cancellation\" will reveal \
						\"Reason for Cancellation\" only if the record is Cancelled.\
					</td>\
				</tr>\
				<tr>\
					<td><b>Description</b></td>\
					<td>Show a description below the field</td>\
				</tr>\
				<tr>\
					<td><b>Default</b></td>\
					<td>Specify a default value</td>\
				</tr>\
				<tr>\
					<td></td>\
					<td><a class='link_type' \
							onclick='cur_frm.fields_help_dialog.hide()'\
							style='color:grey'>Press Esc to close</a>\
					</td>\
				</tr>\
			</table>"
		
		$y(d.body, {padding: '32px', textAlign: 'center', lineHeight: '200%'});

		$a(d.body, 'div', '', {textAlign: 'left'}, help);

		d.show();

		cur_frm.fields_help_dialog = d;

	});
}
