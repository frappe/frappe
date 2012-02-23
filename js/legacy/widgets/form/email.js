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
			'dn':cur_frm.docname
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
		
		// validate email ids
		var email_list = emailto.split(/[,|;]/);
		var valid = 1;
		for(var i=0;i<email_list.length;i++){
			if(!validate_email(email_list[i])) {
				msgprint('error:'+email_list[i] + ' is not a valid email id');
				valid = 0;
			}
		}
		
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
		hide_autosuggest();
	}

	d.make_body([
		 ['Data','To','Example: abc@hotmail.com, xyz@yahoo.com']
		,['Select','Format']
		,['Data','Subject']
		,['Data','From','Optional']
		,['Check','Send With Attachments','Will send all attached documents (if any)']
		,['Text','Message']
		,['Button','Send',email_go]]
	);

	d.widgets['From'].value = (user_email ? user_email:'');
	
	$td(d.rows['Format'].tab,0,1).cur_sel = d.widgets['Format'];
	
    // ---- add auto suggest ---- 
    var opts = { script: '', json: true, maxresults: 10 };

	wn.require('lib/js/legacy/widgets/autosuggest.js');

    var as = new AutoSuggest(d.widgets['To'], opts);
    as.custom_select = function(txt, sel) {
      // ---- add to the last comma ---- 
      var r = '';
      var tl = txt.split(',');
      for(var i=0;i<tl.length-1;i++) r=r+tl[i]+',';
      r = r+(r?' ':'')+sel;
      if(r[r.length-1]==NEWLINE) r=substr(0,r.length-1);
      return r;
    }
    
    var emailto = d.widgets['To']

    as.set_input_value = function(new_txt) {
      if(emailto.value && emailto.value.indexOf(',')!=-1) {
        var txt = emailto.value.split(',');
        txt.splice(txt.length - 1, 1, new_txt);
        for(var i=0;i<txt.length-1;i++) txt[i] = strip(txt[i]);
        emailto.value = txt.join(', ');
      } else {
        emailto.value = new_txt;	
      }
    }
    
    // ---- override server call ---- 
    as.doAjaxRequest = function(txt) {
      var pointer = as; var q = '';
      
      // ---- get last few letters typed ---- 
      var last_txt = txt.split(',');
      last_txt = last_txt[last_txt.length-1];
      
      // ---- show options ---- 
      var call_back = function(r,rt) {
        as.aSug = [];
        if(!r.cl) return;
        for (var i=0;i<r.cl.length;i++) {
          as.aSug.push({'id':r.cl[i], 'value':r.cl[i], 'info':''});
        }
        as.createList(as.aSug);
      }
      $c('webnotes.utils.email_lib.get_contact_list',{'select':_e.email_as_field, 'from':_e.email_as_dt, 'where':_e.email_as_in, 'txt':(last_txt ? strip(last_txt) : '%')},call_back);
      return;
    }
	
	var sel;

	_e.dialog = d;
}

