// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.ui.form");

frappe.ui.form.Attachments = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
	},
	make: function() {
		var me = this;
		this.parent.find(".add-attachment").click(function() {
			me.new_attachment();
		});
		this.add_attachment_wrapper = this.parent.find(".add_attachment").parent();
		this.attachments_label = this.parent.find(".attachments-label");
	},
	max_reached: function() {
		// no of attachments
		var n = keys(this.get_attachments()).length;

		// button if the number of attachments is less than max
		if(n < this.frm.meta.max_attachments || !this.frm.meta.max_attachments) {
			return false;
		}
		return true;
	},
	refresh: function() {
		var me = this;

		if(this.frm.doc.__islocal) {
			this.parent.toggle(false);
			return;
		}
		this.parent.toggle(true);
		this.parent.find(".attachment-row").remove();

		var max_reached = this.max_reached();
		this.add_attachment_wrapper.toggleClass("hide", !max_reached);

		// add attachment objects
		var attachments = this.get_attachments();
		if(attachments.length) {
			attachments.forEach(function(attachment) {
				me.add_attachment(attachment)
			});
		} else {
			this.attachments_label.removeClass("has-attachments");
		}

	},
	get_attachments: function() {
		return this.frm.get_docinfo().attachments;
	},
	add_attachment: function(attachment) {
		var file_name = attachment.file_name;
		var file_url = this.get_file_url(attachment);
		var fileid = attachment.name;
		if (!file_name) {
			file_name = file_url;
		}

		var me = this;
		var $attach = $(repl('<li class="attachment-row">\
				<a class="close" data-owner="%(owner)s">&times;</a>\
				<a href="%(file_url)s" target="_blank" title="%(file_name)s" \
					class="text-ellipsis" style="max-width: calc(100% - 43px);">\
					<span>%(file_name)s</span></a>\
			</li>', {
				file_name: file_name,
				file_url: frappe.urllib.get_full_url(file_url)
			}))
			.insertAfter(this.attachments_label.addClass("has-attachments"));

		var $close =
			$attach.find(".close")
			.data("fileid", fileid)
			.click(function() {
				var remove_btn = this;
				frappe.confirm(__("Are you sure you want to delete the attachment?"),
					function() {
						me.remove_attachment($(remove_btn).data("fileid"))
					}
				);
				return false
			});

		if(!frappe.model.can_write(this.frm.doctype, this.frm.name)) {
			$close.remove();
		}
	},
	get_file_url: function(attachment) {
		var file_url = attachment.file_url;
		if (!file_url) {
			if (attachment.file_name.indexOf('files/') === 0) {
				file_url = '/' + attachment.file_name;
			}
			else {
				file_url = '/files/' + attachment.file_name;
			}
		}
		// hash is not escaped, https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/encodeURI
		return encodeURI(file_url).replace(/#/g, '%23');
	},
	get_file_id_from_file_url: function(file_url) {
		var fid;
		$.each(this.get_attachments(), function(i, attachment) {
			if (attachment.file_url === file_url) {
				fid = attachment.name;
				return false;
			}
		});
		return fid;
	},
	remove_attachment_by_filename: function(filename, callback) {
		this.remove_attachment(this.get_file_id_from_file_url(filename), callback);
	},
	remove_attachment: function(fileid, callback) {
		if (!fileid) {
			if (callback) callback();
			return;
		}

		var me = this;
		return frappe.call({
			method: 'frappe.desk.form.utils.remove_attach',
			args: {
				fid: fileid,
				dt: me.frm.doctype,
				dn: me.frm.docname
			},
			callback: function(r,rt) {
				if(r.exc) {
					if(!r._server_messages)
						msgprint(__("There were errors"));
					return;
				}
				me.remove_fileid(fileid);
				me.frm.get_docinfo().comments.push(r.message);
				me.frm.comments.refresh();
				if (callback) callback();
			}
		});
	},
	new_attachment: function(fieldname) {
		var me = this;
		if (this.dialog) {
			// remove upload dialog
			this.dialog.$wrapper.remove();
		}
		
		// make upload dialog
		this.dialog = frappe.ui.get_upload_dialog({
			"args": me.get_args(),
			"callback": function(attachment, r) { me.attachment_uploaded(attachment, r) },
			"max_width": me.frm.cscript ? me.frm.cscript.attachment_max_width : null,
			"max_height": me.frm.cscript ? me.frm.cscript.attachment_max_height : null
		});
	},
	get_args: function() {
		return {
			from_form: 1,
			doctype: this.frm.doctype,
			docname: this.frm.docname,
		}
	},
	attachment_uploaded:  function(attachment, r) {
		this.dialog && this.dialog.hide();
		this.update_attachment(attachment, r.message.comment);

		if(this.fieldname) {
			this.frm.set_value(this.fieldname, attachment.file_url);
		}
	},
	update_attachment: function(attachment, comment) {
		if(attachment.name) {
			this.add_to_attachments(attachment);
			this.refresh();
			if(comment) {
				this.frm.get_docinfo().comments.push(comment);
				this.frm.comments.refresh();
			}
		}
	},
	add_to_attachments: function (attachment) {
		var form_attachments = this.get_attachments();
		for(var i in form_attachments) {
			// prevent duplicate
			if(form_attachments[i]["name"] === attachment.name) return;
		}
		form_attachments.push(attachment);
	},
	remove_fileid: function(fileid) {
		var attachments = this.get_attachments();
		var new_attachments = [];
		$.each(attachments, function(i, attachment) {
			if(attachment.name!=fileid) {
				new_attachments.push(attachment);
			}
		});
		this.frm.get_docinfo().attachments = new_attachments;
		this.refresh();
	}
});

frappe.ui.get_upload_dialog = function(opts){
	dialog = new frappe.ui.Dialog({
		title: __('Upload Attachment'),
	});

	var btn = dialog.set_primary_action(__("Attach"));
	btn.removeClass("btn-primary").addClass("btn-default");

	dialog.show();

	$(dialog.body).empty();

	frappe.upload.make({
		parent: dialog.body,
		args: opts.args,
		callback: function(attachment, r) {
			dialog.hide();
			if(opts.callback){
				opts.callback(attachment, r);
			}
		},
		on_select: function() {
			btn.removeClass("btn-default").addClass("btn-primary");
		},
		onerror: function() {
			dialog.hide();
		},
		btn: btn,
		max_width: opts.max_width,
		max_height: opts.max_height,
	});

	return dialog;
}
