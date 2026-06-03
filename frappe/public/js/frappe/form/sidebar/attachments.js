// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
frappe.ui.form.Attachments = class Attachments {
	constructor(opts) {
		$.extend(this, opts);

		this.attachments_page_length = 10; // show n attachments initially
		this.show_all_attachments = false;
		this.attachment_preview_width = 40;

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
		this.setup_preview_area();
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
		return this.frm.get_docinfo()?.attachments || [];
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
				class="ellipsis attachment-file-label ellipsis-width"
			>
				<span>${frappe.utils.xss_sanitise(file_name)}</span>
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

		const icon = `<a href="/desk/file/${fileid}" class="attachment-icon">
				${frappe.utils.icon(attachment.is_private ? "es-line-lock" : "es-line-unlock", "sm ml-0")}
			</a>`;

		let $attachment_row = $(`<div class="attachment-row"></div>`)
			.append(frappe.get_data_pill(file_label, fileid, remove_action, icon))
			.insertAfter(this.add_attachment_wrapper);

		$attachment_row.find(".attachment-file-label").on("click", (event) => {
			if (event.metaKey || event.ctrlKey || event.shiftKey || event.which !== 1) {
				return;
			}

			event.preventDefault();
			this.show_attachment_preview(attachment, file_url);
		});
	}

	setup_preview_area() {
		if (this.attachment_preview) {
			return;
		}

		this.attachment_preview = $(`<div class="attachment-preview hidden"></div>`).appendTo(
			this.frm.page.sidebar
		);
	}

	show_attachment_preview(attachment, file_url) {
		this.setup_preview_area();

		let file_name = attachment.file_name || file_url;
		let preview_type = this.get_preview_type(attachment, file_url);
		let escaped_file_name = frappe.utils.escape_html(file_name);
		let escaped_file_url = frappe.utils.escape_html(file_url);
		let preview_html = "";

		if (preview_type === "pdf") {
			preview_html = `<iframe src="${escaped_file_url}" title="${escaped_file_name}"></iframe>`;
		} else if (preview_type === "image") {
			preview_html = `<img src="${escaped_file_url}" alt="${escaped_file_name}" loading="lazy">`;
		} else if (preview_type === "csv") {
			preview_html = `<div class="text-muted attachment-preview-loading">${__(
				"Loading preview..."
			)}</div>`;
		} else {
			preview_html = `<div class="attachment-preview-unavailable">
				<div class="text-muted">${__("Preview not available for this file type.")}</div>
				<a class="btn btn-default btn-sm" href="${escaped_file_url}" target="_blank" rel="noopener noreferrer">
					<span>${__("Open file")}</span>
					${frappe.utils.icon("es-line-arrow-up-right", "xs", "", "", "ml-1")}
				</a>
			</div>`;
		}

		this.current_attachment_preview_type = preview_type;
		this.attachment_preview_request_id = (this.attachment_preview_request_id || 0) + 1;
		let preview_request_id = this.attachment_preview_request_id;
		this.set_preview_width(this.attachment_preview_width);
		this.frm.page.wrapper.addClass("attachment-preview-open");

		this.attachment_preview.removeClass("hidden").html(
			`<div class="attachment-preview-resize-handle"></div>
				<div class="attachment-preview-header">
					<div class="attachment-preview-title">
						<div class="ellipsis" title="${escaped_file_name}">${escaped_file_name}</div>
						<a class="btn btn-link icon-btn attachment-preview-open"
							href="${escaped_file_url}" target="_blank" rel="noopener noreferrer"
							title="${__("Open in new tab")}"
						>
							${frappe.utils.icon("es-line-arrow-up-right", "sm")}
						</a>
					</div>
					<button class="btn btn-link icon-btn attachment-preview-close" type="button" title="${__(
						"Close"
					)}">
						${frappe.utils.icon("close", "sm")}
					</button>
				</div>
				<div class="attachment-preview-body">
					${preview_html}
				</div>`
		);

		this.attachment_preview.find(".attachment-preview-close").on("click", () => {
			this.hide_attachment_preview();
		});

		this.attachment_preview
			.find(".attachment-preview-resize-handle")
			.on("mousedown", (event) => {
				if (event.target !== event.currentTarget) {
					return;
				}

				this.start_preview_resize(event);
			});

		if (preview_type === "csv") {
			this.render_csv_preview(file_url, escaped_file_url, preview_request_id);
		}
	}

	get_preview_type(attachment, file_url) {
		let file_type = (attachment.file_type || "").toLowerCase();
		let file_name = (attachment.file_name || file_url || "").split("?")[0].toLowerCase();
		let image_extensions = ["jpg", "jpeg", "png", "gif", "webp", "svg", "avif", "bmp", "ico"];
		let extension = file_name.includes(".") ? file_name.split(".").pop() : "";

		if (file_type.includes("pdf") || extension === "pdf") {
			return "pdf";
		}

		if (extension === "csv") {
			return "csv";
		}

		if (
			file_type.includes("image") ||
			image_extensions.includes(file_type) ||
			image_extensions.includes(extension)
		) {
			return "image";
		}

		return "unsupported";
	}

	get_unsupported_preview_html(file_url) {
		return `<div class="attachment-preview-unavailable">
			<div class="text-muted">${__("Preview not available for this file type.")}</div>
			<a class="btn btn-default btn-sm" href="${file_url}" target="_blank" rel="noopener noreferrer">
				<span>${__("Open file")}</span>
				${frappe.utils.icon("es-line-arrow-up-right", "xs", "", "", "ml-1")}
			</a>
		</div>`;
	}

	async render_csv_preview(file_url, escaped_file_url, preview_request_id) {
		try {
			let response = await fetch(file_url);
			if (!response.ok) {
				throw new Error("Unable to fetch CSV");
			}

			let csv_text = await response.text();
			let rows = this.parse_csv(csv_text);
			if (!rows.length) {
				throw new Error("Empty CSV");
			}

			if (
				preview_request_id !== this.attachment_preview_request_id ||
				this.current_attachment_preview_type !== "csv"
			) {
				return;
			}

			this.attachment_preview
				.find(".attachment-preview-body")
				.html(this.get_csv_preview_html(rows));
		} catch (error) {
			if (
				preview_request_id !== this.attachment_preview_request_id ||
				this.current_attachment_preview_type !== "csv"
			) {
				return;
			}

			this.attachment_preview
				.find(".attachment-preview-body")
				.html(this.get_unsupported_preview_html(escaped_file_url));
		}
	}

	parse_csv(csv_text) {
		let rows = [];
		let row = [];
		let value = "";
		let in_quotes = false;

		let push_value = () => {
			row.push(value);
			value = "";
		};

		let push_row = () => {
			push_value();
			rows.push(row);
			row = [];
		};

		for (let i = 0; i < csv_text.length; i++) {
			let character = csv_text[i];

			if (in_quotes) {
				if (character === '"') {
					if (csv_text[i + 1] === '"') {
						value += '"';
						i++;
					} else {
						in_quotes = false;
					}
				} else {
					value += character;
				}
				continue;
			}

			if (character === '"') {
				in_quotes = true;
			} else if (character === ",") {
				push_value();
			} else if (character === "\n") {
				push_row();
			} else if (character === "\r") {
				if (csv_text[i + 1] === "\n") {
					i++;
				}
				push_row();
			} else {
				value += character;
			}
		}

		if (in_quotes) {
			throw new Error("Unclosed quoted field");
		}

		if (value.length || row.length) {
			push_row();
		}

		return rows;
	}

	get_csv_preview_html(rows) {
		let max_rows = 100;
		let max_columns = 20;
		let visible_rows = rows.slice(0, max_rows);
		let total_rows = rows.length;
		let total_columns = rows.reduce((max, row) => Math.max(max, row.length), 0);
		let visible_column_count = Math.min(total_columns, max_columns);
		let visible_row_count = visible_rows.length;
		let is_row_truncated = total_rows > max_rows;
		let is_column_truncated = total_columns > max_columns;

		let get_cell_html = (value = "") => {
			let cell_value = String(value);
			let max_cell_length = 200;
			let max_title_length = 1000;
			let is_cell_truncated = cell_value.length > max_cell_length;
			let display_value = is_cell_truncated
				? cell_value.slice(0, max_cell_length) + "…"
				: cell_value;
			let title =
				cell_value.length && cell_value.length <= max_title_length
					? ` title="${frappe.utils.escape_html(cell_value)}"`
					: "";

			return `<td${title}>${frappe.utils.escape_html(display_value)}</td>`;
		};

		let table_rows = visible_rows
			.map((row) => {
				let cells = [];
				for (let i = 0; i < visible_column_count; i++) {
					cells.push(get_cell_html(row[i] || ""));
				}
				return `<tr>${cells.join("")}</tr>`;
			})
			.join("");

		let format_count = (count) => format_number(count, null, 0);
		let note = "";
		if (is_row_truncated && is_column_truncated) {
			note = __("Showing {0} of {1} rows and {2} of {3} columns.", [
				format_count(visible_row_count),
				format_count(total_rows),
				format_count(visible_column_count),
				format_count(total_columns),
			]);
		} else if (is_row_truncated) {
			note = __("Showing {0} of {1} rows.", [
				format_count(visible_row_count),
				format_count(total_rows),
			]);
		} else if (is_column_truncated) {
			note = __("Showing {0} of {1} columns.", [
				format_count(visible_column_count),
				format_count(total_columns),
			]);
		}

		return `<div class="attachment-preview-csv">
			<div class="attachment-preview-csv-table">
				<table class="table table-bordered">
					<tbody>${table_rows}</tbody>
				</table>
			</div>
			${note ? `<div class="text-muted attachment-preview-note">${note}</div>` : ""}
		</div>`;
	}

	hide_attachment_preview() {
		this.attachment_preview?.addClass("hidden").empty();
		this.frm.page.wrapper.removeClass("attachment-preview-open");
		this.attachment_preview_request_id = (this.attachment_preview_request_id || 0) + 1;
	}

	start_preview_resize(event) {
		event.preventDefault();

		this.is_resizing_attachment_preview = true;
		this.frm.page.wrapper.addClass("attachment-preview-resizing");

		if (this.current_attachment_preview_type === "pdf") {
			this.attachment_preview.addClass("attachment-preview-resizing-pdf");
		}

		$(document)
			.on("mousemove.attachment_preview", (event) => {
				this.resize_preview(event);
			})
			.on("mouseup.attachment_preview", () => {
				this.stop_preview_resize();
			});
	}

	resize_preview(event) {
		if (!this.is_resizing_attachment_preview) {
			return;
		}

		let layout = this.frm.page.wrapper.find(".layout-main").get(0);
		if (!layout) {
			return;
		}

		let layout_rect = layout.getBoundingClientRect();
		let preview_width = ((layout_rect.right - event.clientX) / layout_rect.width) * 100;

		this.set_preview_width(preview_width);
	}

	stop_preview_resize() {
		if (!this.is_resizing_attachment_preview) {
			return;
		}

		this.is_resizing_attachment_preview = false;
		this.frm.page.wrapper.removeClass("attachment-preview-resizing");
		this.attachment_preview?.removeClass("attachment-preview-resizing-pdf");
		$(document).off(".attachment_preview");
	}

	set_preview_width(width) {
		let min_preview_width = 25;
		let max_preview_width = 60; // Keeps the form at a minimum width of 40%.
		let preview_width = Math.min(Math.max(width, min_preview_width), max_preview_width);

		this.attachment_preview_width = preview_width;
		this.frm.page.wrapper
			.get(0)
			?.style.setProperty("--attachment-preview-width", `${preview_width}%`);
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

		const is_web_url = /^(https?:)?\/\//i.test(file_url);

		file_url = encodeURI(file_url);

		// hash is not escaped, https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/encodeURI
		// only encode hash if it's a local file path, not a web URL
		if (!is_web_url) {
			file_url = file_url.replace(/#/g, "%23");
		}

		return file_url;
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
