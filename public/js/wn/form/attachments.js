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
			<div class="attachment-list"></div>\
			<button class="btn btn-default btn-small"><i class="icon-plus"></i></button>\
		</div>').appendTo(this.parent);
		this.$list = this.wrapper.find(".attachment-list");

		this.parent.find(".btn").click(function() {
			me.new_attachment();
		});
	},
	max_reached: function() {
		// no of attachments
		var n = keys(this.get_file_list()).length;
		
		// button if the number of attachments is less than max
		if(n < this.frm.meta.max_attachments || !this.frm.meta.max_attachments) {
			return false;
		}
		return true;
	},
	refresh: function() {
		var doc = this.frm.doc;
		if(doc.__islocal) {
			this.parent.toggle(false);
			return;
		}
		this.parent.toggle(true);
		this.parent.find(".btn").toggle(!this.max_reached());
		
		this.$list.empty();

		var file_list = this.get_file_list();
		var file_names = keys(file_list).sort();
		
		// add attachment objects
		for(var i=0; i<file_names.length; i++) {
			this.add_attachment(file_names[i], file_list);
		}
		
		// refresh select fields with options attach_files:
		this.refresh_attachment_select_fields();
	},
	get_file_list: function() {
 		return this.frm.doc.file_list ? JSON.parse(this.frm.doc.file_list) : {};
	},
	add_attachment: function(filename, file_list) {
		var fileid = file_list[filename];
		
		var me = this;
		$(repl('<div class="alert alert-info"><span style="display: inline-block; width: 90%;\
			text-overflow: ellipsis; white-space: nowrap; overflow: hidden;">\
				<i class="icon-file"></i> <a href="%(href)s"\
					target="_blank" title="%(filename)s">%(filename)s</a></span><a href="#" class="close">&times;</a>\
			</div>', {
				filename: filename,
				href: wn.utils.get_file_link(filename)
			}))
			.appendTo(this.$list)
			.find(".close")
			.data("fileid", fileid)
			.click(function() {
				var remove_btn = this;
				wn.confirm(wn._("Are you sure you want to delete the attachment?"),
					function() {
						var data = $(remove_btn).data("fileid");
						wn.call({
							method: 'webnotes.widgets.form.utils.remove_attach',
							args: {
								fid: data, 
								dt: me.frm.doctype, 
								dn: me.frm.docname 
							},
							callback: function(r,rt) {
								if(r.exc) {
									msgprint("There were errors.");
									return;
								}
								me.remove_fileid(data);
							}
						});
					});
				return false;
			});
	},
	new_attachment: function(fieldname) {
		var me = this;
		if(!this.dialog) {
			this.dialog = new wn.ui.Dialog({
				title: wn._('Upload Attachment'),
				width: 400
			});
			$y(this.dialog.body, {margin:'13px'});
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
			callback: function(fileid, filename, r) {
				me.update_attachment(fileid, filename, fieldname, r);
			}
		});
	},
	update_attachment: function(fileid, filename, fieldname, r) {
		this.dialog && this.dialog.hide();
		if(fileid) {
			this.add_to_file_list(fileid, filename);
			this.refresh();
			if(fieldname) {
				this.frm.set_value(fieldname, "files/"+filename);
				this.frm.cscript[fieldname] && this.frm.cscript[fieldname](this.frm.doc);
			}
		}
	},
	add_to_file_list: function(fileid, filename) {
		var doc = this.frm.doc;
		var file_list = doc.file_list ? this.get_file_list() : {};
		file_list[filename] = fileid;
		doc.file_list = JSON.stringify(file_list);
	},
	remove_fileid: function(fileid) {
		var file_list = this.get_file_list();
		var new_file_list = {};
		$.each(file_list, function(key, value) {
			if(value!=fileid)
				new_file_list[key] = value;
		});
		this.frm.doc.file_list = JSON.stringify(new_file_list);
		this.refresh();
	},
	refresh_attachment_select_fields: function() {
		for(var i=0; i<this.frm.fields.length; i++) {
			if(this.frm.fields[i].attach_files) {
				var fieldname = this.frm.fields[i].df.fieldname;
				refresh_field(fieldname);
				if(this.frm.doc[fieldname]!=undefined && !inList(this.frm.fields[i].df.options.split("\n"), this.frm.doc[fieldname])) {
					this.frm.cscript.on_remove_attachment && this.frm.cscript.on_remove_attachment(this.frm.doc);
					this.frm.set_value(fieldname, "");
				}
			}
		}
	}
});