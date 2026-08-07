// Embedded split-screen modal for reviewing Document Queue items.
// Left pane: embedded list of queue records. Right pane: file preview.

frappe.ui.DocumentQueueModal = class DocumentQueueModal {
	/** @param {{ doctype: string, title?: string }} options */
	constructor(options = {}) {
		this.doctype = options.doctype;
		this.title =
			options.title ||
			(this.doctype ? __("Documents - {0}", [__(this.doctype)]) : __("Documents"));
		this.sort_by = "creation desc";
		this.active_status = "Pending";
		this.page_size = 20;
		this.list = null;
		this.selected_row = null;
		this._build_dialog();
	}

	_build_dialog() {
		this.dialog = new frappe.ui.Dialog({
			title: this.title,
			size: "extra-large",
			fields: [{ fieldname: "body", fieldtype: "HTML" }],
		});
		this.dialog.footer.hide();
		this.dialog.$wrapper.on("shown.bs.modal", () => {
			this._apply_modal_styles();
			if (!this.list) {
				frappe.require("embedded_list.bundle.js").then(() => {
					this._build_screens();
					this._setup_list();
					this._clear_preview();
				});
			} else {
				this.list.refresh();
			}
		});
	}

	show() {
		this.dialog.show();
	}

	_apply_modal_styles() {
		this.dialog.$wrapper.css({ overflow: "hidden" });
		this.dialog.$wrapper.find(".modal-dialog").css({
			margin: "20px auto",
			width: "92vw",
			"max-width": "1280px",
		});
		this.dialog.$wrapper.find(".modal-content").css({
			display: "flex",
			"flex-direction": "column",
			overflow: "hidden",
		});
		this.dialog.modal_body.css({
			flex: "1 1 auto",
			overflow: "hidden",
			"background-color": "var(--bg-light)",
			padding: "0",
		});
		this.dialog.get_field("body").$wrapper.closest(".form-section").css({ padding: "0", margin: "0", border: "none" });
		this.dialog.get_field("body").$wrapper.closest(".frappe-control").css({ padding: "0", margin: "0" });
		$("#dq-modal-styles").remove();

		const $styles = $(`
			<style id="dq-modal-styles">
			/* ── Modal Header & Split Screen Spacing ── */
			.dq-split-screen {
				padding: 4px 20px 14px 20px !important;
				height: 76vh;
				max-height: 76vh;
				overflow: hidden;
				display: flex;
				flex-direction: row;
				gap: 16px;
				box-sizing: border-box;
			}

			/* ── Left Pane: List View (55%) ── */
			.dq-list-pane {
				flex: 0 0 calc(55% - 8px);
				min-width: 0;
				display: flex;
				flex-direction: column;
				overflow: visible;
				height: 100%;
			}
			.dq-list-wrapper {
				flex: 1;
				display: flex;
				flex-direction: column;
				overflow: visible;
				min-height: 0;
			}

			/* ── Embedded List Framework ── */
			.dq-list-wrapper .embedded-list {
				flex: 1;
				display: flex;
				flex-direction: column;
				overflow: visible;
				min-height: 0;
			}
			.dq-list-wrapper .embedded-list-header {
				flex-shrink: 0;
				display: flex !important;
				justify-content: space-between !important;
				align-items: center !important;
				margin-bottom: 8px !important;
				overflow: visible !important;
				min-height: 30px !important;
				padding: 0 2px !important;
			}
			.dq-list-wrapper .embedded-list-heading {
				display: none !important;
			}
			.dq-list-wrapper .embedded-list-header-left {
				display: flex;
				align-items: center;
			}
			.dq-list-wrapper .embedded-list-header-actions {
				display: flex !important;
				align-items: center !important;
				overflow: visible !important;
			}
			.dq-list-wrapper .filter-section {
				display: inline-flex !important;
				align-items: center !important;
				gap: 8px !important;
				overflow: visible !important;
			}

			.dq-list-wrapper .embedded-list-result {
				flex: 1;
				display: flex;
				flex-direction: column;
				overflow: hidden;
				min-height: 0;
			}

			/* ── List View Table ── */
			.dq-list-wrapper .embedded-list-table-wrap {
				flex: 1;
				overflow-y: auto;
				border: 1px solid var(--border-color);
				border-radius: var(--border-radius-md, 8px);
				background: var(--card-bg, #fff);
				margin-bottom: 0 !important;
				display: block;
			}
			.dq-list-wrapper table.embedded-list-table tbody tr.active-row {
				background-color: var(--control-bg, #ebf1f6) !important;
			}
			.dq-list-wrapper table.embedded-list-table tbody tr.active-row td {
				font-weight: 500;
				color: var(--text-color);
			}

			.dq-list-wrapper .embedded-list > .min-h-48,
			.dq-list-wrapper .embedded-list-loading,
			.dq-list-wrapper .embedded-list-error {
				flex: 1;
				display: flex;
				flex-direction: column;
				justify-content: center;
				align-items: center;
			}

			/* ── Pagination Area (Level Left / Right) ── */
			.dq-list-wrapper .list-paging-area {
				display: flex !important;
				justify-content: space-between !important;
				align-items: center !important;
				padding: 6px 2px 0 2px !important;
				flex-shrink: 0 !important;
				min-height: 28px !important;
				margin-top: auto !important;
			}
			.dq-list-wrapper .list-paging-area .level-left {
				display: flex;
				align-items: center;
			} 
			.dq-list-wrapper .list-paging-area .es-tab-buttons {
				border-radius: 6px !important;
				padding: 1.5px !important;
				gap: 2px !important;
			}
			.dq-list-wrapper .list-paging-area .es-pill {
				font-size: 11px !important;
				padding: 3px 7px !important;
				line-height: 14px !important;
				border-radius: 5px !important;
			}
			.dq-list-wrapper .list-paging-area .level-right {
				display: flex;
				align-items: center;
				gap: 10px;
			}
			.dq-list-wrapper .list-paging-area .list-count {
				font-size: 11px !important;
				color: var(--text-muted) !important;
				white-space: nowrap;
			}
			.dq-list-wrapper .list-paging-area .btn-more {
				height: 24px !important;
				padding: 2px 8px !important;
				font-size: 11px !important;
			}

			/* ── Right Pane: Preview Pane (45%) ── */
			.dq-preview-pane {
				flex: 0 0 calc(45% - 8px);
				min-width: 0;
				display: flex;
				flex-direction: column;
				overflow: hidden;
				height: 100%;
				background: var(--card-bg, #fff);
				border: 1px solid var(--border-color);
				border-radius: var(--border-radius-md, 8px);
				box-sizing: border-box;
				position: relative;
			}
			.dq-preview-empty-container {
				flex: 1;
				display: flex;
				align-items: center;
				justify-content: center;
				padding: 24px;
				height: 100%;
			}
			.dq-preview-header {
				flex-shrink: 0;
				display: flex;
				align-items: center;
				justify-content: space-between;
				padding: 0 10px;
				height: 36px;
				background-color: var(--card-bg, #fff);
				border-bottom: 1px solid var(--border-color);
				box-sizing: border-box;
			}
			.dq-preview-title {
				display: inline-flex;
				align-items: center;
				gap: 6px;
				font-size: var(--text-sm, 12px);
				font-weight: 500;
				color: var(--text-muted, #8d99a6);
			}
			.dq-preview-title-icon {
				display: inline-flex;
				align-items: center;
				color: var(--text-muted, #8d99a6);
			}
			.dq-preview-title-icon svg {
				width: 14px;
				height: 14px;
			}
			.dq-preview-actions {
				display: inline-flex;
				align-items: center;
			}
			.dq-preview-body {
				position: relative;
				flex: 1;
				min-height: 0;
				display: flex;
				align-items: center;
				justify-content: center;
				background-color: var(--subtle-fg, #f8f9fa);
				overflow: hidden;
			}
			.dq-preview-body iframe {
				width: 100%;
				height: 100%;
				border: 0;
				outline: none;
				background-color: #fff;
				border-bottom-left-radius: var(--border-radius-md, 8px);
				border-bottom-right-radius: var(--border-radius-md, 8px);
			}
			.dq-preview-body img {
				max-width: calc(100% - 32px);
				max-height: calc(100% - 32px);
				width: auto;
				height: auto;
				border: 0;
				border-radius: var(--border-radius-md, 8px);
				box-shadow: 0 2px 12px rgba(0, 0, 0, 0.12);
			}
			</style>
		`);
		$("head").append($styles);
	}

	_build_screens() {
		this.$split_screen = $('<div class="dq-split-screen"></div>').appendTo(this.dialog.get_field("body").$wrapper);
		this.$list_pane = $('<div class="dq-list-pane"></div>').appendTo(this.$split_screen);
		this.$preview_pane = $('<div class="dq-preview-pane"></div>').appendTo(this.$split_screen);
	}

	/**
	 * Initializes the EmbeddedList and monkey-patches its lifecycle methods.
	 * Native EmbeddedList doesn't support custom TabButton pagination or 
	 * smooth transitions on refresh, so we override `render_header`, `refresh`,
	 * `after_render`, and `render_load_more` to inject our custom layout.
	 */
	_setup_list() {
		this.$list_wrapper = $('<div class="dq-list-wrapper"></div>').appendTo(this.$list_pane);

		this.list = new frappe.ui.EmbeddedList({
			wrapper: this.$list_wrapper,
			doctype: "Document Queue",
			title: "",
			page_size: this.page_size,
			fields: ["name", "status", "source_file", "document_type", "creation"],
			filters: { document_type: this.doctype, status: "Ready for Review" },
			order_by: this.sort_by,
			on_row_click: (row) => this._toggle_row_selection(row),
			columns: [
				{
					label: __("Source File"),
					fieldname: "source_file",
					render: (row) => {
						const name = frappe.document_queue_review.get_file_name(row.source_file || "");
						return frappe.utils.escape_html(name || "—");
					},
				},
				{
					label: __("Status"),
					fieldname: "status",
					render: (row) => {
						const short = row.status === "Ready for Review" ? "Review" : row.status;
						const theme =
							row.status === "Ready for Review" || row.status === "Queued" ? "blue"
							: row.status === "Completed"  ? "green"
							: row.status === "Processing" ? "orange"
							: row.status === "Failed"     ? "red"
							: "gray";
						return frappe.ui.badge.html({ label: short, theme });
					},
				},
				{
					label: __("Created On"),
					fieldname: "creation",
					render: (row) => frappe.datetime.comment_when(row.creation, true),
				},
			],
		});

		this._patch_list_pagination();
		this.list.render_load_more();
		this.list.render_header = () => {};

		// Smooth fade on refresh
		this.list.refresh = () => {
			this.list.$error.hide();
			this.list.$no_result.hide();
			this.list.$loading.hide();
			const is_initial = !(this.list.data && this.list.data.length > 0);
			this.list.$result
				.show()
				.css({ opacity: is_initial ? "0" : "0.5", transition: "opacity 0.2s ease" });
			return this.list
				.get_data()
				.then((data) => {
					this.list._all_data = data || [];
					this.list.before_render();
					this.list._apply_filter();
				})
				.catch((e) => {
					console.error("EmbeddedList: failed to load data", e);
					this.list.$result.hide();
					this.list.$error.text(this.list.error_message).show();
				})
				.finally(() => {
					requestAnimationFrame(() =>
						requestAnimationFrame(() => this.list.$result.css("opacity", "1"))
					);
				});
		};

		const _orig_after_render = this.list.after_render.bind(this.list);
		this.list.after_render = () => {
			_orig_after_render();
			this.list.render_load_more();
			this._update_filter_button_label();
			this._update_active_row();
		};

		this._setup_native_toolbar();
	}

	_toggle_row_selection(row) {
		if (this.selected_row && this.selected_row.name === row.name) {
			this.selected_row = null;
			this._update_active_row();
			this._clear_preview();
		} else {
			this.selected_row = row;
			this._update_active_row();
			this._render_preview(row);
		}
	}

	_update_active_row() {
		if (!this.$list_wrapper) return;
		this.$list_wrapper.find("table.embedded-list-table tbody tr").removeClass("active-row");
		if (this.selected_row && this.list && this.list.data) {
			const idx = this.list.data.findIndex((r) => r.name === this.selected_row.name);
			if (idx !== -1) {
				this.$list_wrapper
					.find(`table.embedded-list-table tbody tr[data-row-idx="${idx}"]`)
					.addClass("active-row");
			}
		}
	}

	_clear_preview() {
		if (!this.$preview_pane) return;
		this.$preview_pane.empty();

		const $empty_wrap = $('<div class="dq-preview-empty-container"></div>').appendTo(
			this.$preview_pane
		);

		const $empty = frappe.ui.empty_state({
			icon: "file-text",
			title: __("No Document Selected"),
			description: __("Select a document from the list to preview."),
		});
		$empty_wrap.append($empty);
	}

	_render_preview(row) {
		if (!this.$preview_pane) return;
		this.$preview_pane.empty();

		const file_url = this._get_file_url(row.source_file);
		const file_name =
			frappe.document_queue_review.get_file_name(row.source_file || "") || file_url;
		const preview_type = this._get_preview_type(row.source_file);

		// Header (Preview title on left, Start Review button on right)
		const $header = $(`
			<div class="dq-preview-header">
				<div class="dq-preview-title">
					<span class="dq-preview-title-icon">${frappe.utils.icon("file-text", "sm")}</span>
					<span>${__("Preview")}</span>
				</div>
				<div class="dq-preview-actions"></div>
			</div>
		`).appendTo(this.$preview_pane);

		const $start_btn = frappe.ui.button({
			label: __("Start Review"),
			icon_right: "arrow-up-right",
			size: "sm",
			variant: "outline",
			onclick: () => this._start_review(row),
		});
		$header.find(".dq-preview-actions").append($start_btn);

		// Body
		const $body = $('<div class="dq-preview-body"></div>').appendTo(this.$preview_pane);

		const escaped_url = frappe.utils.escape_html(file_url);
		const escaped_name = frappe.utils.escape_html(file_name);

		if (preview_type === "pdf") {
			$body.html(`<iframe src="${escaped_url}" title="${escaped_name}"></iframe>`);
		} else if (preview_type === "image") {
			$body.html(`<img src="${escaped_url}" alt="${escaped_name}" loading="lazy">`);
		} else {
			const $unsupported = frappe.ui.empty_state({
				icon: "file-text",
				title: __("Preview Not Available"),
				description: __("This file format cannot be previewed directly."),
				actions: file_url
					? [
							{
								label: __("Open File"),
								href: file_url,
								icon: "arrow-up-right",
								variant: "subtle",
							},
					  ]
					: [],
			});
			$body.append($unsupported);
		}
	}

	async _start_review(row) {
		this.dialog.hide();
		const queue_name = row.name;

		try {
			const context = await frappe.document_queue_review.fetch_context(queue_name);
			if (context && context.document_type) {
				frappe.model.with_doctype(context.document_type, () => {
					const doc = frappe.model.get_new_doc(context.document_type);
					frappe.document_queue_review.pending_context = context;
					frappe.set_route("Form", context.document_type, doc.name).then(() => {
						let url = new URL(window.location.href);
						url.searchParams.set("document_queue", context.queue_name);
						window.history.replaceState(window.history.state, "", url.toString());
					});
				});
				return;
			}
		} catch (e) {
			console.error("Failed to fetch document review context", e);
		}

		// Fallback to Document Queue form
		frappe.set_route("Form", "Document Queue", queue_name);
	}

	_get_file_url(file_url) {
		if (!file_url) return "";
		if (file_url.indexOf("files/") === 0) {
			file_url = "/" + file_url;
		} else if (!file_url.startsWith("/") && !/^(https?:)?\/\//i.test(file_url)) {
			file_url = "/files/" + file_url;
		}
		const is_web_url = /^(https?:)?\/\//i.test(file_url);
		file_url = encodeURI(file_url);
		if (!is_web_url) {
			file_url = file_url.replace(/#/g, "%23");
		}
		return file_url;
	}

	_get_preview_type(source_url) {
		if (!source_url) return "unsupported";
		const url = String(source_url).split("?")[0].toLowerCase();
		const ext = url.includes(".") ? url.split(".").pop() : "";
		const image_exts = ["jpg", "jpeg", "png", "gif", "webp", "svg", "avif", "bmp", "ico"];
		if (ext === "pdf") return "pdf";
		if (image_exts.includes(ext)) return "image";
		return "unsupported";
	}

	_patch_list_pagination() {
		// Unified render_load_more (Paging Area with TabButtons & Count)
		this.list.render_load_more = () => {
			this.list.$result.find(".embedded-list-more").remove();

			const total_count = (this.list.data || []).length;
			const rendered_count = Math.min(this.list.rendered_count || 0, total_count);

			let $paging_area = this.list.$wrapper.find(".list-paging-area");
			if (!$paging_area.length) {
				$paging_area = $(`
					<div class="list-paging-area level">
						<div class="level-left"></div>
						<div class="level-right">
							<span class="list-count"></span>
						</div>
					</div>
				`).appendTo(this.list.$wrapper);

				const paging_values = [20, 100, 500, 2500];
				if (frappe.ui.TabButtons) {
					const tab_buttons = new frappe.ui.TabButtons({
						label: __("Page Size"),
						options: paging_values.map((val) => ({
							label: String(val),
							value: val,
						})),
						value: this.list.page_size,
						on_change: (val) => {
							this.list.page_size = val;
							this.page_size = val;
							this.list.rendered_count = 0;
							this.list.render();
						},
					});
					$paging_area.find(".level-left").append(tab_buttons.$el);
				}
			}

			// Update count text
			$paging_area.find(".list-count").text(`${rendered_count} of ${total_count}`);

			// Add/remove "Load More" button
			$paging_area.find(".btn-more").remove();
			if (rendered_count < total_count) {
				const $more_btn = $(`
					<button class="btn btn-default btn-sm btn-more" type="button">
						${__("Load More")}
					</button>
				`);
				$more_btn.on("click", (e) => {
					e.preventDefault();
					this.list.render_more();
				});
				$paging_area.find(".level-right").append($more_btn);
			}
		};
	}

	async _setup_native_toolbar() {
		await frappe.model.with_doctype("Document Queue");

		const $header = this.list.$header;
		$header.show().empty().html(`
			<div class="embedded-list-header-left">
				<input type="text" class="form-control form-control-sm embedded-list-search" data-action="search" placeholder="${__("Search")}">
			</div>
			<div class="embedded-list-header-actions">
				<div class="filter-section"></div>
			</div>
		`);

		const $actions_wrap = $header.find(".filter-section");

		// 1. Status Filter (using native frappe.ui.Dropdown from Component Explorer, size sm)
		this.$status_trigger = frappe.ui.button({
			label: __("Review Pending"),
			size: "sm",
			variant: "subtle",
			icon_right: "chevron-down",
		});
		$actions_wrap.append(this.$status_trigger);

		this.status_dropdown = new frappe.ui.Dropdown({
			trigger: this.$status_trigger,
			options: [
				{
					label: __("Review Pending"),
					onclick: () => this._set_status_filter("Pending"),
				},
				{
					label: __("Completed"),
					onclick: () => this._set_status_filter("Completed"),
				},
				{
					label: __("All"),
					onclick: () => this._set_status_filter("All"),
				},
			],
		});

		// 2. Sort Selector (using native frappe.ui.Dropdown from Component Explorer, size sm)
		this.$sort_trigger = frappe.ui.button({
			label: __("Newest First"),
			size: "sm",
			variant: "subtle",
			icon: "arrow-down-wide-narrow",
			icon_right: "chevron-down",
		});
		$actions_wrap.append(this.$sort_trigger);

		this.sort_dropdown = new frappe.ui.Dropdown({
			trigger: this.$sort_trigger,
			options: [
				{
					label: __("Newest First"),
					icon: "arrow-down-wide-narrow",
					onclick: () =>
						this._set_sort("creation desc", __("Newest First"), "arrow-down-wide-narrow"),
				},
				{
					label: __("Oldest First"),
					icon: "arrow-up-narrow-wide",
					onclick: () =>
						this._set_sort("creation asc", __("Oldest First"), "arrow-up-narrow-wide"),
				},
				{
					label: __("File Name (A-Z)"),
					icon: "arrow-down-a-z",
					onclick: () =>
						this._set_sort("source_file asc", __("File Name (A-Z)"), "arrow-down-a-z"),
				},
				{
					label: __("File Name (Z-A)"),
					icon: "arrow-up-z-a",
					onclick: () =>
						this._set_sort("source_file desc", __("File Name (Z-A)"), "arrow-up-z-a"),
				},
			],
		});

		this.list.refresh();
	}

	_set_sort(sort_by, label, icon) {
		this.sort_by = sort_by;
		this.list.order_by = sort_by;
		frappe.ui.button.dress(this.$sort_trigger, { label, icon, icon_right: "chevron-down" });
		this.list.refresh();
	}

	_update_filter_button_label() {
		if (!this.$status_trigger) return;
		const count = this.list.data?.length ?? 0;
		const labels = {
			Pending: __("Review Pending ({0})", [count]),
			Completed: __("Completed ({0})", [count]),
		};
		const text = labels[this.active_status] ?? __("All ({0})", [count]);
		frappe.ui.button.dress(this.$status_trigger, { label: text, icon_right: "chevron-down" });
	}

	_set_status_filter(status) {
		this.active_status = status;
		const filters = { document_type: this.doctype };
		if (status === "Pending") filters.status = "Ready for Review";
		if (status === "Completed") filters.status = "Completed";
		this.list.filters = filters;
		this.list.refresh();
	}
};
