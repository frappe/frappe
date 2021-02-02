// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt



frappe.ui.form.Attachments = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
	},
	make: function() {
		var me = this;
		this.parent.find(".add-attachment-btn").click(function() {
			me.new_attachment();
		});
		this.add_attachment_wrapper = this.parent.find(".add_attachment").parent();
		this.attachments_label = this.parent.find(".attachments-label");
	},
	max_reached: function(raise_exception=false) {
		const attachment_count = Object.keys(this.get_attachments()).length;
		const attachment_limit = this.frm.meta.max_attachments;
		if (attachment_limit && attachment_count >= attachment_limit) {
			if (raise_exception) {
				frappe.throw({
					title: __("Attachment Limit Reached"),
					message: __("Maximum attachment limit of {0} has been reached.", [cstr(attachment_limit).bold()]),
				});
			}
			return true;
		}
		return false;
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

		let file_label = `
			<a href="${file_url}" target="_blank" title="${file_name}" class="ellipsis" style="max-width: calc(100% - 43px);">
				<span>${file_name}</span>
			</a>`;

		let remove_action = null;
		if (frappe.model.can_write(this.frm.doctype, this.frm.name)) {
			remove_action = function(target_id) {
				frappe.confirm(__("Are you sure you want to delete the attachment?"),
					function() {
						me.remove_attachment(target_id);
					}
				);
				return false;
			};
		}

		let icon;
		// REDESIGN-TODO: set icon using frappe.utils.icon
		if (attachment.is_private) {
			icon = `<div><svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
				<path fill-rule="evenodd" clip-rule="evenodd" d="M8.07685 1.45015H8.02155C7.13255 1.44199 6.2766 1.78689 5.64159 2.40919C5.00596 3.0321 4.64377 3.88196 4.63464 4.77188L4.63462 4.77188V4.77701V5.12157H3.75C2.64543 5.12157 1.75 6.017 1.75 7.12157V12.5132C1.75 13.6177 2.64543 14.5132 3.75 14.5132H12.2885C13.393 14.5132 14.2885 13.6177 14.2885 12.5132V7.12157C14.2885 6.017 13.393 5.12157 12.2885 5.12157H11.4037V4.83708C11.4119 3.94809 11.067 3.09213 10.4447 2.45713C9.82175 1.8215 8.97189 1.4593 8.08198 1.45018L8.08198 1.45015H8.07685ZM10.4037 5.12157V4.8347V4.82972L10.4037 4.82972C10.4099 4.20495 10.1678 3.60329 9.73045 3.15705C9.29371 2.7114 8.69805 2.4572 8.07417 2.45015H8.01916H8.01418L8.01419 2.45013C7.38942 2.44391 6.78776 2.68609 6.34152 3.12341C5.89586 3.56015 5.64166 4.15581 5.63462 4.77969V5.12157H10.4037ZM3.75 6.12157C3.19772 6.12157 2.75 6.56929 2.75 7.12157V12.5132C2.75 13.0655 3.19772 13.5132 3.75 13.5132H12.2885C12.8407 13.5132 13.2885 13.0655 13.2885 12.5132V7.12157C13.2885 6.56929 12.8407 6.12157 12.2885 6.12157H3.75ZM8.01936 10.3908C8.33605 10.3908 8.59279 10.134 8.59279 9.81734C8.59279 9.50064 8.33605 9.24391 8.01936 9.24391C7.70266 9.24391 7.44593 9.50064 7.44593 9.81734C7.44593 10.134 7.70266 10.3908 8.01936 10.3908ZM9.59279 9.81734C9.59279 10.6863 8.88834 11.3908 8.01936 11.3908C7.15038 11.3908 6.44593 10.6863 6.44593 9.81734C6.44593 8.94836 7.15038 8.24391 8.01936 8.24391C8.88834 8.24391 9.59279 8.94836 9.59279 9.81734Z" fill="currentColor"/>
			</svg></div>`;
		} else {
			icon = `<div><svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
				<path fill-rule="evenodd" clip-rule="evenodd" d="M8.07685 1.45014H8.02155C7.13255 1.44198 6.2766 1.78687 5.64159 2.40918C5.00596 3.03209 4.64377 3.88195 4.63464 4.77187L4.63462 4.77187V4.777V5.12156H3.75C2.64543 5.12156 1.75 6.01699 1.75 7.12156V12.5132C1.75 13.6177 2.64543 14.5132 3.75 14.5132H12.2885C13.393 14.5132 14.2885 13.6177 14.2885 12.5132V7.12156C14.2885 6.01699 13.393 5.12156 12.2885 5.12156H5.63462V4.77968C5.64166 4.1558 5.89586 3.56014 6.34152 3.12339C6.78776 2.68608 7.38942 2.4439 8.01419 2.45012L8.01418 2.45014H8.01916H8.07417C8.69805 2.45718 9.29371 2.71138 9.73045 3.15704C9.92373 3.35427 10.2403 3.35746 10.4375 3.16418C10.6347 2.9709 10.6379 2.65434 10.4447 2.45711C9.82175 1.82149 8.97189 1.45929 8.08198 1.45017L8.08198 1.45014H8.07685ZM3.75 6.12156C3.19772 6.12156 2.75 6.56927 2.75 7.12156V12.5132C2.75 13.0655 3.19772 13.5132 3.75 13.5132H12.2885C12.8407 13.5132 13.2885 13.0655 13.2885 12.5132V7.12156C13.2885 6.56927 12.8407 6.12156 12.2885 6.12156H3.75ZM8.01936 10.3908C8.33605 10.3908 8.59279 10.134 8.59279 9.81732C8.59279 9.50063 8.33605 9.2439 8.01936 9.2439C7.70266 9.2439 7.44593 9.50063 7.44593 9.81732C7.44593 10.134 7.70266 10.3908 8.01936 10.3908ZM9.59279 9.81732C9.59279 10.6863 8.88834 11.3908 8.01936 11.3908C7.15038 11.3908 6.44593 10.6863 6.44593 9.81732C6.44593 8.94835 7.15038 8.2439 8.01936 8.2439C8.88834 8.2439 9.59279 8.94835 9.59279 9.81732Z" fill="currentColor"/>
			</svg></div>`;
		}

		$(`<li class="attachment-row">`)
			.append(frappe.get_data_pill(
				file_label,
				fileid,
				remove_action,
				icon
			))
			.insertAfter(this.attachments_label.addClass("has-attachments"));

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
		if (this.dialog) {
			// remove upload dialog
			this.dialog.$wrapper.remove();
		}

		new frappe.ui.FileUploader({
			doctype: this.frm.doctype,
			docname: this.frm.docname,
			frm: this.frm,
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
