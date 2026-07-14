// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
frappe.ui.form.Attachments = class Attachments {
	constructor(opts) {
		$.extend(this, opts);

		this.attachments_page_length = 10; // show n attachments initially
		this.show_all_attachments = false;
		this.attachment_preview_width_key = "form_attachment_preview_width";
		this.max_csv_preview_size = 5 * 1024 * 1024;
		this.attachment_preview_width = this.get_stored_preview_width();

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
				${frappe.utils.icon(attachment.is_private ? "lock" : "lock-open", "sm ml-0")}
			</a>`;

		let $attachment_row = $(`<div class="attachment-row"></div>`)
			.append(frappe.get_data_pill(file_label, fileid, remove_action, icon))
			.insertAfter(this.add_attachment_wrapper);

		$attachment_row.find(".attachment-file-label").on("click", (event) => {
			if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) {
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
		let file_name = attachment.file_name || file_url;
		let preview_type = this.get_preview_type(attachment, file_url);
		let escaped_file_name = frappe.utils.escape_html(file_name);
		let escaped_file_url = frappe.utils.escape_html(file_url);
		let escaped_absolute_file_url = frappe.utils.escape_html(
			this.get_absolute_file_url(file_url)
		);
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
			preview_html = this.get_unsupported_preview_html(escaped_file_url);
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
					</div>
					<div class="attachment-preview-actions">
						<a class="btn btn-link icon-btn attachment-preview-open-link"
							href="${escaped_file_url}" target="_blank" rel="noopener noreferrer"
							title="${__("Open file in new tab")}"
						>
							${frappe.utils.icon("arrow-up-right", "sm")}
						</a>
						<button class="btn btn-link icon-btn attachment-preview-copy-link"
							type="button"
							data-file-url="${escaped_absolute_file_url}"
							title="${__("Copy file URL to clipboard")}"
							aria-label="${__("Copy file URL to clipboard")}"
						>
							${frappe.utils.icon("copy", "sm")}
						</button>
						<button class="btn btn-link icon-btn attachment-preview-close" type="button" title="${__(
							"Close"
						)}">
							${frappe.utils.icon("x", "sm")}
						</button>
					</div>
				</div>
				<div class="attachment-preview-body">
					${preview_html}
				</div>`
		);

		this.attachment_preview.find(".attachment-preview-close").on("click", () => {
			this.hide_attachment_preview();
		});

		this.attachment_preview.find(".attachment-preview-copy-link").on("click", (event) => {
			frappe.utils.copy_to_clipboard(event.currentTarget.dataset.fileUrl);
		});

		$(document)
			.off("keydown.attachment_preview")
			.on("keydown.attachment_preview", (event) => {
				if (event.key !== "Escape") return;
				if (!document.body.contains(this.attachment_preview?.[0])) {
					$(document).off("keydown.attachment_preview");
					return;
				}
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
			this.render_csv_preview(attachment, file_url, escaped_file_url, preview_request_id);
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

	get_unsupported_preview_html(
		file_url,
		message = __("Preview not available for this file type.")
	) {
		return `<div class="attachment-preview-unavailable">
			<div class="text-muted">${frappe.utils.escape_html(message)}</div>
			<a class="btn btn-default btn-sm" href="${file_url}" target="_blank" rel="noopener noreferrer">
				<span>${__("Open file")}</span>
				${frappe.utils.icon("arrow-up-right", "xs", "", "", "ml-1")}
			</a>
		</div>`;
	}

	async render_csv_preview(attachment, file_url, escaped_file_url, preview_request_id) {
		try {
			let file_size = Number(attachment.file_size);
			if (file_size > this.max_csv_preview_size) {
				throw this.get_csv_size_error();
			}

			let response = await fetch(file_url);
			if (!response.ok) {
				throw new Error("Unable to fetch CSV");
			}

			let content_length = Number(response.headers.get("Content-Length"));
			if (content_length > this.max_csv_preview_size) {
				throw this.get_csv_size_error();
			}

			let csv_text = await response.text();
			if (csv_text.length > this.max_csv_preview_size) {
				throw this.get_csv_size_error();
			}

			let rows = frappe.utils.csv_to_array(csv_text);
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
				.html(
					this.get_unsupported_preview_html(
						escaped_file_url,
						error.code === "CSV_PREVIEW_TOO_LARGE"
							? __("Only files up to {0} MB are supported for preview.", [
									this.max_csv_preview_size / (1024 * 1024),
							  ])
							: __("Preview not available for this file type.")
					)
				);
		}
	}

	get_csv_size_error() {
		let error = new Error("CSV exceeds preview size limit");
		error.code = "CSV_PREVIEW_TOO_LARGE";
		return error;
	}

	get_csv_preview_html(rows) {
		let max_rows = 100;
		let max_columns = 20;
		let header_row = rows[0];
		let data_rows = rows.slice(1);
		let visible_rows = data_rows.slice(0, max_rows);
		let total_rows = data_rows.length;
		let total_columns = rows.reduce((max, row) => Math.max(max, row.length), 0);
		let visible_column_count = Math.min(total_columns, max_columns);
		let visible_row_count = visible_rows.length;
		let is_row_truncated = total_rows > max_rows;
		let is_column_truncated = total_columns > max_columns;

		let get_cell_html = (value = "", tag = "td") => {
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

			return `<${tag}${title}>${frappe.utils.escape_html(display_value)}</${tag}>`;
		};

		let table_headers = [];
		for (let i = 0; i < visible_column_count; i++) {
			table_headers.push(get_cell_html(header_row[i] || "", "th"));
		}

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
					<thead><tr>${table_headers.join("")}</tr></thead>
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
		$(document).off("keydown.attachment_preview");
		if (this.is_resizing_attachment_preview) {
			this.is_resizing_attachment_preview = false;
			this.frm.page.wrapper.removeClass("attachment-preview-resizing");
			$(document).off(".attachment_preview_resize");
		}
	}

	start_preview_resize(event) {
		event.preventDefault();

		this.is_resizing_attachment_preview = true;
		this.frm.page.wrapper.addClass("attachment-preview-resizing");

		if (this.current_attachment_preview_type === "pdf") {
			this.attachment_preview
				.addClass("attachment-preview-resizing-pdf")
				.find(".attachment-preview-body")
				.append(
					`<div class="attachment-preview-resize-overlay">${__(
						"Resizing preview..."
					)}</div>`
				);
		}

		$(document)
			.on("mousemove.attachment_preview_resize", (event) => {
				this.resize_preview(event);
			})
			.on("mouseup.attachment_preview_resize", () => {
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
		this.attachment_preview
			?.removeClass("attachment-preview-resizing-pdf")
			.find(".attachment-preview-resize-overlay")
			.remove();
		$(document).off(".attachment_preview_resize");
		this.save_preview_width();
	}

	set_preview_width(width) {
		let preview_width = this.clamp_preview_width(width);

		this.attachment_preview_width = preview_width;
		this.frm.page.wrapper
			.get(0)
			?.style.setProperty("--attachment-preview-width", `${preview_width}%`);
	}

	clamp_preview_width(width) {
		let min_preview_width = 25;
		let max_preview_width = 60; // Keeps the form at a minimum width of 40%.
		return Math.min(Math.max(width, min_preview_width), max_preview_width);
	}

	get_stored_preview_width() {
		try {
			let stored_width = Number(localStorage.getItem(this.attachment_preview_width_key));
			return this.clamp_preview_width(stored_width || 40);
		} catch {
			return 40;
		}
	}

	save_preview_width() {
		try {
			localStorage.setItem(this.attachment_preview_width_key, this.attachment_preview_width);
		} catch {
			// localStorage can be unavailable in restricted browser contexts.
		}
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

	get_absolute_file_url(file_url) {
		try {
			return new URL(file_url, window.location.origin).href;
		} catch {
			return file_url;
		}
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
