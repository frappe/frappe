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

// EMAIL

// Autosuggest defaults
_e.email_as_field = 'email_id';
_e.email_as_dt = 'Contact';
_e.email_as_in = 'email_id,contact_name';

sendmail = function(emailto, emailfrom, cc, subject, message, fmt, with_attachments) {
	var fn = function(html) {
		$c('webnotes.utils.email_lib.send_form', {
			'sendto':emailto, 
			'sendfrom': emailfrom?emailfrom:'',
			'cc':cc?cc:'',
			'subject':subject,
			'message':replace_newlines(message),
			'body':html,
			'full_domain': wn.urllib.get_base_url(),
			'with_attachments':with_attachments ? 1 : 0,
			'dt':cur_frm.doctype,
			'dn':cur_frm.docname,
			'customer': cur_frm.doc.customer || '',
			'supplier': cur_frm.doc.supplier || ''
			}, 
			function(r, rtxt) { 
				//
			}
		);
	}
	
	// build print format
	_p.build(fmt, fn);
}

_e.make = function() {
	var d = new Dialog(440, 440, "Send Email");

	var email_go = function() {
		var emailfrom = d.widgets['From'].value;
		var emailto = d.widgets['To'].value;
		
		if(!emailfrom)
			emailfrom = user_email;
		
		emailto = emailto.replace(/ /g, "");
		// validate email ids
		var email_list = emailto.split(/[,|;]/);
		var valid = 1;
		for(var i=0;i<email_list.length;i++){
			if(!email_list[i]) {
				email_list.splice(i, 1);
			} else if(!validate_email(email_list[i])) {
				msgprint('error:'+email_list[i] + ' is not a valid email id');
				valid = 0;
			}
		}	
		emailto = email_list.join(",");
		
		// validate from
		if(emailfrom && !validate_email(emailfrom)) {
			msgprint('error:'+ emailfrom + ' is not a valid email id. To change the default please click on Profile on the top right of the screen and change it.');
			return;
		}
		
		if(!valid)return;
			
		var cc= emailfrom;
		
		if(!emailfrom) { 
			emailfrom = wn.control_panel.auto_email_id; 
			cc = ''; 
		}
		sendmail(emailto, emailfrom, emailfrom, d.widgets['Subject'].value, d.widgets['Message'].value, sel_val(cur_frm.print_sel), d.widgets['Send With Attachments'].checked);
		_e.dialog.hide();
	}

	d.onhide = function() {
		
	}

	d.make_body([
		 ['Data','To','Example: abc@hotmail.com, xyz@yahoo.com']
		,['Select','Format']
		,['Data','Subject']
		,['Data','From']
		,['Check','Send With Attachments','Will send all attached documents (if any)']
		,['Text','Message']
		,['Button','Send',email_go]]
	);

	d.widgets['From'].value = user_email;
	$(d.widgets["From"]).attr("disabled", "disabled").addClass("disp_area");
	
	$td(d.rows['Format'].tab,0,1).cur_sel = d.widgets['Format'];
	
	function split( val ) {
		return val.split( /,\s*/ );
	}
	function extractLast( term ) {
		return split(term).pop();
	}


	$(d.widgets['To'])
		.bind( "keydown", function(event) {
			if (event.keyCode === $.ui.keyCode.TAB &&
					$(this).data( "autocomplete" ).menu.active ) {
				event.preventDefault();
			}
		})	
		.autocomplete({
			source: function(request, response) {
				wn.call({
					method:'webnotes.utils.email_lib.get_contact_list',
					args: {
						'select': _e.email_as_field, 
						'from': _e.email_as_dt, 
						'where': _e.email_as_in, 
						'txt': extractLast(request.term).value || '%'
					},
					callback: function(r) {
						response($.ui.autocomplete.filter(
							r.cl || [], extractLast(request.term)));
					}
				});
			},
			focus: function() {
				// prevent value inserted on focus
				return false;
			},
			select: function( event, ui ) {
				var terms = split( this.value );
				// remove the current input
				terms.pop();
				// add the selected item
				terms.push( ui.item.value );
				// add placeholder to get the comma-and-space at the end
				terms.push( "" );
				this.value = terms.join( ", " );
				return false;
			}
		});

	_e.dialog = d;
}

