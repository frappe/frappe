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

wn.provide("wn.ui.form");

wn.ui.form.Attachments = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
	},
	make: function() {
		var me = this;
		this.wrapper = $('<div>\
			<div class="alert-list"></div>\
		</div>').appendTo(this.parent);
		this.$list = this.wrapper.find(".alert-list");

		this.parent.find(".btn").click(function() {
			me.new_attachment();
		})
	},
	max_reached: function() {
		// no of attachments
		var n = this.frm.doc.file_list ? this.frm.doc.file_list.split('\n').length : 0;
		
		// button if the number of attachments is less than max
		if(n < this.frm.meta.max_attachments || !this.frm.meta.max_attachments) {
			return false;
		}
		return true;
	},
	refresh: function() {
		if(this.frm.doc.__islocal || !this.frm.meta.allow_attach) {
			this.parent.toggle(false);
			return;
		}
		this.parent.toggle(true);
		
		this.$list.empty();

		var fl = this.get_filelist();

		// add attachment objects
		for(var i=0; i<fl.length; i++) {
			this.add_attachment(fl[i])
		}
	},
	get_filelist: function() {
 		return this.frm.doc.file_list ? this.frm.doc.file_list.split('\n') : [];
	},
	add_attachment: function(fileinfo) {
		fileinfo = fileinfo.split(',')
		filename = fileinfo[0];
		fileid = fileinfo[1];
		
		var me = this;
		$(repl('<div class="alert alert-info"><span style="display: inline-block; width: 90%;\
			text-overflow: ellipsis; white-space: nowrap; overflow: hidden;">\
				<i class="icon icon-file"></i> <a href="%(href)s"\
					target="_blank" title="%(filename)s">%(filename)s</a></span><a href="#" class="close">&times;</a>\
			</div>', {
				filename: filename,
				href: wn.utils.get_file_link(filename)
			}))
			.appendTo(this.$list)
			.find(".close")
			.data("fileid", fileid)
			.click(function() {
				var yn = confirm("Are you sure you want to delete the attachment?");
				if(!yn) return;
				
				var data = $(this).data("fileid");
				wn.call({
					method: 'webnotes.widgets.form.utils.remove_attach',
					args: {
						'fid': data, 
						dt: me.frm.doctype, 
						dn: me.frm.docname 
					},
					callback: function(r,rt) {
						me.frm.doc.modified = r.message;
						me.remove_fileid(data);
						me.frm.refresh();
					}
				});
				return false;
			});
	},
	new_attachment: function() {
		if(!this.dialog) {
			this.dialog = new wn.ui.Dialog({
				title:'Upload Attachment',
				width: 400
			})
			$y(this.dialog.body, {margin:'13px'})
			this.dialog.make();
		}
		this.dialog.body.innerHTML = '';
		this.dialog.show();
			
		wn.upload.make({
			parent: this.dialog.body,
			args: {
				from_form: 1,
				doctype: this.frm.doctype,
				docname: this.frm.docname
			},
			callback: wn.ui.form.file_upload_done
		});
			
	},
	remove_fileid: function(fileid) {
		this.frm.doc.file_list = $.map(this.get_filelist(), function(f) {
			if(f.split(',')[1]!=fileid) return f;
		}).join('\n');		
	}
})


// this function will be called after the upload is done
// from webnotes.utils.file_manager
wn.ui.form.file_upload_done = function(doctype, docname, fileid, filename, at_id, new_timestamp) {
		
	// add to file_list
	var doc = locals[doctype][docname];
	if(doc.file_list) {
		var fl = doc.file_list.split('\n')
		fl.push(filename + ',' + fileid)
		doc.file_list = fl.join('\n');
	}
	else
		doc.file_list = filename + ',' + fileid;
	
	// update timestamp
	doc.modified = new_timestamp;
	
	// update file_list
	var frm = wn.views.formview[doctype].frm;
	frm.attachments.dialog.hide();
	msgprint('File Uploaded Sucessfully.');
	frm.refresh();
}
