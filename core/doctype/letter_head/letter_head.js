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

cur_frm.cscript.refresh = function(doc) {	
	if (doc.docstatus) hide_field('steps');
	
	var has_attachments = !$.isEmptyObject(cur_frm.attachments.get_attachments());
	
	cur_frm.set_intro("");
	if(doc.__islocal) {
		cur_frm.set_intro("Step 1: Set the name and save.");
	} else {
		if(has_attachments) {
			cur_frm.set_intro("Step 2: Upload your letter head image / set html content directly");
			cur_frm.add_custom_button("Upload", function() {
				cur_frm.attachments.add_attachment();
			}, 'icon-upload');
		}
	}
	
	if(has_attachments && !doc.content) {
		cur_frm.cscript['set_from_image'](doc);
	}
	
	if(doc.content) {
		cur_frm.cscript.content(doc);
	}
}

cur_frm.cscript.content = function(doc) {
	$(cur_frm.fields_dict.preview.wrapper).html("<p>Preview:</p><hr>" + doc.content + "<hr>");	
}

cur_frm.cscript['set_from_image'] = function(doc, dt, dn) {
	if(!cur_frm.get_files().length) {
		msgprint('Please attach an image file first');
		return;
	}
	if(doc.content) {
		if(!confirm('Are you sure you want to overwrite the existing HTML?'))
			return;
	}
	
	

	var file_name = cur_frm.get_files()[0];

	if(!in_list(['gif','jpg','jpeg','png'], file_name.split('.')[1].toLowerCase())) {
		msgprint("Please upload a web friendly (GIF, JPG or PNG) image file for the letter head");
		return;
	}

	img_link = '<div><img src="files/'+ file_name + '"/></div>'
	
	doc.content = img_link;
	refresh_field('content');
	cur_frm.cscript.content(doc);
}
