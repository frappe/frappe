// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt



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
		var n = Object.keys(this.get_attachments()).length;

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

		var $attach = $(frappe.render_template("attachment", {
			"file_path": "/desk#Form/File/" + fileid,
			"icon": attachment.is_private ? "fa fa-lock" : "fa fa-unlock-alt",
			"file_name": file_name,
			"file_url": frappe.urllib.get_full_url(file_url)
		})).insertAfter(this.attachments_label.addClass("has-attachments"));

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
						frappe.msgprint(__("There were errors"));
					return;
				}
				me.remove_fileid(fileid);
				me.frm.sidebar.reload_docinfo();
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

		new frappe.ui.FileUploader({
			doctype: this.frm.doctype,
			docname: this.frm.docname,
			folder: 'Home/Attachments',
			on_success: (file_doc) => {
				this.attachment_uploaded(file_doc);
			}
		});
	},
	get_args: function() {
		return {
			from_form: 1,
			doctype: this.frm.doctype,
			docname: this.frm.docname,
		}
	},
	attachment_uploaded:  function(attachment) {
		this.dialog && this.dialog.hide();
		this.update_attachment(attachment);
		this.frm.sidebar.reload_docinfo();

		if(this.fieldname) {
			this.frm.set_value(this.fieldname, attachment.file_url);
		}
	},
	update_attachment: function(attachment) {
		if(attachment.name) {
			this.add_to_attachments(attachment);
			this.refresh();
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
