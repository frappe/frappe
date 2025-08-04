// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
frappe.ui.form.Attachments = class Attachments {
	constructor(opts) {
		$.extend(this, opts);

		this.attachments_page_length = 10; // show n attachments initially
		this.show_all_attachments = false;

		this.make();
	}
	make() {
		var me = this;
		this.parent.find(".add-attachment-btn").click(function () {
			me.new_attachment();
		});

		this.parent.find(".explore-link").click(() => {
			if (!this.frm.attachments.get_attachments()?.length) return;
			frappe.open_in_new_tab = true;
			frappe.set_route("List", "File", {
				attached_to_doctype: this.frm.doctype,
				attached_to_name: this.frm.docname,
			});
		});

		this.add_attachment_wrapper = this.parent.find(".attachments-actions");
		this.attachments_label = this.parent.find(".attachments-label");
	}
	max_reached(raise_exception = false) {
		const attachment_count = Object.keys(this.get_attachments()).length;
		const attachment_limit = this.frm.meta.max_attachments;
		if (attachment_limit && attachment_count >= attachment_limit) {
			if (raise_exception) {
				frappe.throw({
					title: __("Attachment Limit Reached"),
					message: __("Maximum attachment limit of {0} has been reached.", [
						cstr(attachment_limit).bold(),
					]),
				});
			}
			return true;
		}
		return false;
	}
	refresh() {
		if (this.frm.doc.__islocal) {
			this.parent.toggle(false);
			return;
		}
		this.parent.toggle(true);
		this.parent.find(".attachment-row").remove();

		var max_reached = this.max_reached();
		this.add_attachment_wrapper.find(".add-attachment-btn").toggle(!max_reached);

		// add attachment objects
		var attachments = this.get_attachments();
		this.render_attachments(attachments);
		this.setup_show_all_button(attachments);
	}

	setup_show_all_button(attachments) {
		// show button if there is more to show and user has not clicked on "Show All"
		let is_slicable = attachments.length > this.attachments_page_length;
		let show = !this.show_all_attachments && is_slicable;

		let show_all_btn = this.parent.find(".show-all-btn");
		if (!show) {
			show_all_btn.addClass("hidden");
			return;
		}

		show_all_btn.removeClass("hidden");
		show_all_btn.click(() => {
			show_all_btn.addClass("hidden");
			this.show_all_attachments = true;
			this.refresh();
		});
	}

	get_attachments() {
		return this.frm.get_docinfo().attachments || [];
	}

	render_attachments(attachments) {
		var me = this;
		let attachments_to_render = attachments;

		let is_slicable = attachments.length > this.attachments_page_length;
		if (!this.show_all_attachments && is_slicable) {
			// render last n attachments as they are at the top
			let start = attachments.length - this.attachments_page_length;
			attachments_to_render = attachments.slice(start, attachments.length);
		}

		if (attachments_to_render.length) {
			let exists = {};
			let unique_attachments = attachments_to_render.filter((attachment) => {
				return Object.prototype.hasOwnProperty.call(exists, attachment.file_name)
					? false
					: (exists[attachment.file_name] = true);
			});
			unique_attachments.forEach((attachment) => {
				me.add_attachment(attachment);
			});
		}

		if (!attachments.length) {
			// If no attachments in totality
			this.attachments_label.removeClass("has-attachments");
		}
	}

	add_attachment(attachment) {
		var file_name = attachment.file_name;
		var file_url = this.get_file_url(attachment);
		var fileid = attachment.name;
		if (!file_name) {
			file_name = file_url;
		}

		var me = this;

		let file_label = `
			<a href="${file_url}" target="_blank" title="${frappe.utils.escape_html(file_name)}"
				class="ellipsis attachment-file-label"
			>
				<span>${file_name}</span>
			</a>`;

		let remove_action = null;
		if (this.can_delete_attachment()) {
			remove_action = function (target_id) {
				frappe.confirm(__("Are you sure you want to delete the attachment?"), function () {
					let target_attachment = me
						.get_attachments()
						.find((attachment) => attachment.name === target_id);
					let to_be_removed = me
						.get_attachments()
						.filter(
							(attachment) => attachment.file_name === target_attachment.file_name
						);
					to_be_removed.forEach((attachment) => me.remove_attachment(attachment.name));
				});
				return false;
			};
		}

		const icon = `<a href="/app/file/${fileid}" class="attachment-icon">
				${frappe.utils.icon(attachment.is_private ? "es-line-lock" : "es-line-unlock", "sm ml-0")}
			</a>`;

		$(`<div class="attachment-row"></div>`)
			.append(frappe.get_data_pill(file_label, fileid, remove_action, icon))
			.insertAfter(this.add_attachment_wrapper);
	}

	can_delete_attachment() {
		if (this.frm.meta.protect_attached_files) {
			switch (this.frm.doc.docstatus) {
				case 0:
					return this.frm.has_perm("write");
				case 2:
					return this.frm.has_perm("write") && this.frm.has_perm("delete");
				default:
					return false;
			}
		}

		return this.frm.has_perm("write");
	}

	get_file_url(attachment) {
		var file_url = attachment.file_url;
		if (!file_url) {
			if (attachment.file_name.indexOf("files/") === 0) {
				file_url = "/" + attachment.file_name;
			} else {
				file_url = "/files/" + attachment.file_name;
			}
		}
		// hash is not escaped, https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/encodeURI
		return encodeURI(file_url).replace(/#/g, "%23");
	}
	get_file_id_from_file_url(file_url) {
		var fid;
		$.each(this.get_attachments(), function (i, attachment) {
			if (attachment.file_url === file_url) {
				fid = attachment.name;
				return false;
			}
		});
		return fid;
	}
	remove_attachment_by_filename(filename, callback) {
		this.remove_attachment(this.get_file_id_from_file_url(filename), callback);
	}
	remove_attachment(fileid, callback) {
		if (!fileid) {
			if (callback) callback();
			return;
		}

		var me = this;
		return frappe.call({
			method: "frappe.desk.form.utils.remove_attach",
			type: "DELETE",
			args: {
				fid: fileid,
				dt: me.frm.doctype,
				dn: me.frm.docname,
			},
			callback: function (r, rt) {
				if (r.exc) {
					if (!r._server_messages) frappe.msgprint(__("There were errors"));
					return;
				}
				me.remove_fileid(fileid);
				me.frm.sidebar.reload_docinfo();
				if (callback) callback();
			},
		});
	}
	new_attachment(fieldname) {
		if (this.dialog) {
			// remove upload dialog
			this.dialog.$wrapper.remove();
		}

		const restrictions = {};
		if (this.frm.meta.max_attachments) {
			restrictions.max_number_of_files =
				this.frm.meta.max_attachments - this.frm.attachments.get_attachments().length;
		}

		new frappe.ui.FileUploader({
			doctype: this.frm.doctype,
			docname: this.frm.docname,
			frm: this.frm,
			folder: "Home/Attachments",
			on_success: (file_doc) => {
				this.attachment_uploaded(file_doc);
			},
			restrictions,
			make_attachments_public: this.frm.meta.make_attachments_public,
		});
	}
	get_args() {
		return {
			from_form: 1,
			doctype: this.frm.doctype,
			docname: this.frm.docname,
		};
	}
	attachment_uploaded(attachment) {
		this.dialog && this.dialog.hide();
		this.update_attachment(attachment);
		this.frm.sidebar.reload_docinfo();

		if (this.fieldname) {
			this.frm.set_value(this.fieldname, attachment.file_url);
		}
	}
	update_attachment(attachment) {
		if (attachment.name) {
			this.add_to_attachments(attachment);
			this.refresh();
		}
	}
	add_to_attachments(attachment) {
		var form_attachments = this.get_attachments();
		for (var i in form_attachments) {
			// prevent duplicate
			if (form_attachments[i]["name"] === attachment.name) return;
		}
		form_attachments.push(attachment);
	}
	remove_fileid(fileid) {
		var attachments = this.get_attachments();
		var new_attachments = [];
		$.each(attachments, function (i, attachment) {
			if (attachment.name != fileid) {
				new_attachments.push(attachment);
			}
		});
		this.frm.get_docinfo().attachments = new_attachments;
		this.refresh();
	}
};
