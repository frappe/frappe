/**
 * Document Queue Review Modal
 *
 * Screen 1 – EmbeddedList (document queue list view)
 * Screen 2 – Split-screen review: full Frappe Form (left) + sticky PDF/image preview (right)
 *
 * Design contract:
 *  - Uses frappe.ui.Dialog (extra-large).
 *  - Screen 1: frappe.ui.EmbeddedList, frappe.ui.SortSelector, frappe.ui.badge.
 *  - Screen 2: frappe.ui.form.Form (native, full child-table support).
 *              frappe.document_queue_review.get_preview_markup reused for preview.
 *  - Save: frappe.ui.form.save() -> frappe.desk.form.save.savedocs (native Frappe).
 *  - Header: breadcrumb title "Document Queue / DQ-0001", Save / Submit button in modal header.
 *  - No custom HTML grids, no footer buttons.
 */
frappe.provide("frappe.ui");

frappe.ui.DocumentQueueModal = class DocumentQueueModal {
	/** @param {{ doctype: string }} options */
	constructor(options) {
		this.doctype = options.doctype;
		this.sort_by = "creation desc";
		this._screen = "list";
		this._prev_frm = null;
		this.frm = null;
		this.list = null;
		this._current_context = null;
		this._build_dialog();
	}

	// -------------------------------------------------------------------------
	// DIALOG BOOTSTRAP
	// -------------------------------------------------------------------------

	_build_dialog() {
		this.dialog = new frappe.ui.Dialog({
			title: __("Document Queue"),
			size: "extra-large",
			fields: [{ fieldname: "body", fieldtype: "HTML" }],
		});
		this.dialog.footer.hide();
		this.dialog.onhide = () => this._on_dialog_hide();
		this.dialog.$wrapper.on("shown.bs.modal", () => {
			this._apply_modal_styles();
			if (!this.list) {
				frappe.require("embedded_list.bundle.js").then(() => {
					this._build_screens();
					this._setup_list();
				});
			}
		});
	}

	show() {
		this.dialog.show();
	}

	_body() {
		return this.dialog.get_field("body").$wrapper;
	}

	// -------------------------------------------------------------------------
	// MODAL STYLES
	// -------------------------------------------------------------------------

	_apply_modal_styles() {
		this.dialog.$wrapper.css({
			overflow: "hidden",
		});
		this.dialog.$wrapper.find(".modal-dialog").css({
			margin: "24px auto",
			width: "90vw",
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
		this._body().closest(".form-section").css({ padding: "0", margin: "0", border: "none" });
		this._body().closest(".frappe-control").css({ padding: "0", margin: "0" });
		this._body().css({ padding: "0" });

		if (!this.$custom_styles) {
			this.$custom_styles = $(`
				<style>
				/* ── Outer Modal & Window Scroll Management ── */
				html.modal-open,
				body.modal-open {
					overflow: hidden !important;
					height: 100% !important;
				}
				.modal {
					overflow: hidden !important;
				}
				.modal-dialog {
					overflow: hidden !important;
				}
				.modal-content {
					overflow: hidden !important;
				}
				.modal-body {
					overflow: hidden !important;
				}
				.datepicker {
					z-index: 1080 !important;
				}

				/* ── Screen 1 (List View) ─────────────────── */
				.dq-list-screen {
					padding: 16px 20px;
					height: 75vh;
					max-height: 75vh;
					overflow: hidden;
					display: flex;
					flex-direction: column;
					box-sizing: border-box;
				}
				.dq-list-wrapper {
					flex: 1;
					display: flex;
					flex-direction: column;
					overflow: hidden;
					min-height: 0;
					transition: opacity 0.2s ease;
				}
				.dq-list-wrapper .embedded-list {
					flex: 1;
					display: flex;
					flex-direction: column;
					overflow: hidden;
					min-height: 0;
				}
				.dq-list-wrapper .embedded-list-header {
					flex-shrink: 0;
					display: flex !important;
					justify-content: space-between !important;
					align-items: center !important;
					margin-bottom: 12px !important;
					overflow: visible !important;
					min-height: 32px !important;
					padding: 0 !important;
				}
				.dq-list-wrapper .embedded-list-header-actions {
					display: flex !important;
					align-items: center !important;
					gap: 8px !important;
					overflow: visible !important;
				}
				.dq-list-wrapper .embedded-list-search {
					height: 28px !important;
					font-size: var(--text-sm, 12px) !important;
					border-radius: var(--border-radius-sm, 6px) !important;
				}
				.dq-list-wrapper .filter-selector {
					display: inline-flex !important;
					align-items: center !important;
				}
				.dq-list-wrapper .filter-selector .btn {
					height: 28px !important;
					padding: 4px 10px !important;
					font-size: var(--text-sm, 12px) !important;
					display: inline-flex !important;
					align-items: center !important;
					gap: 6px !important;
				}
				.dq-list-wrapper .filter-selector .dropdown-menu {
					min-width: 160px !important;
					padding: 4px 0 !important;
					border-radius: var(--border-radius-md, 8px) !important;
					box-shadow: var(--shadow-md, 0 4px 12px rgba(0,0,0,0.1)) !important;
				}
				.dq-list-wrapper .filter-selector .dropdown-menu .dropdown-item {
					padding: 6px 12px !important;
					font-size: var(--text-sm, 12px) !important;
					cursor: pointer !important;
				}
				.dq-list-wrapper .embedded-list-result {
					flex: 1;
					display: flex;
					flex-direction: column;
					overflow: hidden;
					min-height: 0;
				}
				.dq-list-wrapper .embedded-list-table-wrap {
					flex: 1;
					overflow-y: auto;
					border: 1px solid var(--border-color);
					border-radius: var(--border-radius-md, 8px);
					background: var(--card-bg, #fff);
					margin-bottom: 0 !important;
					display: block;
				}
				.dq-list-wrapper table.embedded-list-table {
					width: 100%;
					margin-bottom: 0;
					border-collapse: separate;
					border-spacing: 0;
				}
				.dq-list-wrapper table.embedded-list-table thead {
					position: sticky;
					top: 0;
					z-index: 2;
				}
				.dq-list-wrapper table.embedded-list-table thead tr {
					background-color: var(--subtle-fg, #f8f9fa);
				}
				.dq-list-wrapper table.embedded-list-table th {
					padding: 8px 12px !important;
					font-size: var(--text-sm, 12px);
					font-weight: 500;
					color: var(--text-muted);
					border-bottom: 1px solid var(--border-color);
					background-color: var(--subtle-fg, #f8f9fa);
					text-align: left;
				}
				.dq-list-wrapper table.embedded-list-table td {
					padding: 8px 12px !important;
					font-size: var(--text-md, 13px);
					border-bottom: 1px solid var(--border-color);
					vertical-align: middle;
					text-align: left;
				}
				.dq-list-wrapper .embedded-list-more {
					display: flex !important;
					justify-content: space-between !important;
					align-items: center !important;
					margin-top: 10px !important;
					margin-bottom: 0 !important;
					padding: 4px 2px 0 2px !important;
					flex-shrink: 0 !important;
				}
				.dq-list-wrapper .embedded-list-more .embedded-list-count {
					font-size: var(--text-sm, 12px) !important;
					color: var(--text-muted) !important;
				}

				/* ── Header Styling ─────────── */
				.modal-header .modal-title {
					display: flex;
					align-items: center;
					gap: 6px;
					font-size: var(--text-lg, 18px) !important;
					font-weight: var(--weight-semibold, 600) !important;
					color: var(--text-color) !important;
					line-height: normal;
				}
				.dq-header-title {
					display: inline-flex;
					align-items: center;
					gap: 4px;
					font-size: inherit;
					font-weight: inherit;
					line-height: normal;
				}
				.dq-breadcrumb-root {
					color: var(--text-muted) !important;
					font-weight: inherit;
					font-size: inherit;
					cursor: pointer;
					text-decoration: none;
					transition: color 0.15s ease;
				}
				.dq-breadcrumb-root:hover {
					color: var(--text-color) !important;
					text-decoration: none;
				}
				.dq-breadcrumb-sep {
					color: var(--text-muted);
					font-weight: normal;
					margin: 0 2px;
				}
				.dq-breadcrumb-current {
					color: var(--text-color);
					font-weight: inherit;
					font-size: inherit;
				}
				.modal-header .modal-actions {
					display: flex !important;
					align-items: center !important;
					gap: 8px !important;
					margin-right: 0 !important;
				}
				.modal-header .modal-actions .dq-submit-badge {
					display: inline-flex;
					align-items: center;
				}

				/* ── Modal Actions Buttons (Save / Submit) ─── */
				.modal-header .modal-actions .dq-save-btn {
					margin: 0 !important;
					display: inline-flex;
					align-items: center;
					font-weight: var(--weight-medium, 500);
					min-width: 60px;
					justify-content: center;
				}
				.modal-header .modal-actions .dq-save-btn.btn-primary,
				.modal-header .modal-actions .dq-save-btn.btn-primary:hover,
				.modal-header .modal-actions .dq-save-btn.btn-primary:focus,
				.modal-header .modal-actions .dq-save-btn.btn-primary:active {
					background-color: var(--btn-primary) !important;
					color: var(--neutral, #ffffff) !important;
					border-color: var(--btn-primary) !important;
				}
				.modal-header .modal-actions .dq-save-btn.btn-primary:disabled,
				.modal-header .modal-actions .dq-save-btn.btn-primary[disabled] {
					background-color: var(--btn-primary) !important;
					color: var(--neutral, #ffffff) !important;
					opacity: 0.6 !important;
					cursor: not-allowed !important;
				}
				.modal-header .modal-actions .dq-submit-btn.btn-primary,
				.modal-header .modal-actions .dq-submit-btn.btn-primary:hover,
				.modal-header .modal-actions .dq-submit-btn.btn-primary:focus,
				.modal-header .modal-actions .dq-submit-btn.btn-primary:active {
					background-color: var(--primary-color, var(--primary, #007bff)) !important;
					color: #ffffff !important;
					border-color: var(--primary-color, var(--primary, #007bff)) !important;
				}

				/* ── Screen 2 split layout ─────────── */
				.dq-review-screen {
					position: relative;
					display: flex;
					height: 75vh;
					max-height: 75vh;
					overflow: hidden;
					background: var(--bg-light);
					box-sizing: border-box;
				}

				/* Left: scrollable form fields */
				.dq-form-side {
					flex: 6;
					height: 100%;
					max-height: 100%;
					overflow-y: auto;
					padding: 16px 20px;
					min-width: 0;
					transition: flex 0.2s ease;
					scrollbar-width: thin;
					box-sizing: border-box;
				}
				/* Strip page chrome irrelevant inside the modal */
				.dq-form-side .page-head,
				.dq-form-side .layout-side-section,
				.dq-form-side .form-footer,
				.dq-form-side .form-message,
				.dq-form-side .form-message-container,
				.dq-form-side .form-dashboard { display: none !important; }

				/* Remove unnecessary top gap above first section in modal */
				.dq-form-side .form-section:first-child {
					padding-top: 0 !important;
					border-top: none !important;
					margin-top: 0 !important;
				}
				.dq-form-side .form-section:first-child > .section-head {
					padding-top: 0 !important;
					margin-top: 0 !important;
				}
				.dq-form-side .form-section:first-child > .section-body:first-child {
					padding-top: 0 !important;
					margin-top: 0 !important;
				}

				/* Phone field country flag & ISD vertical alignment fix inside modal */
				.dq-form-side .frappe-control[data-fieldtype="Phone"] .control-input {
					position: relative !important;
				}
				.dq-form-side .frappe-control[data-fieldtype="Phone"] .selected-phone {
					top: 0 !important;
					bottom: 0 !important;
					margin: auto 0 !important;
					height: 20px !important;
					display: flex !important;
					align-items: center !important;
				}

				/* Prevent document_queue_review.mount from adding the review layout inside modal */
				.dq-form-side .std-form-layout.document-queue-review-layout {
					display: block !important;
				}
				.dq-form-side .document-queue-review-panel { display: none !important; }
				.dq-form-side .std-form-layout {
					box-shadow: none !important;
					border: none !important;
					padding: 0 !important;
					background: transparent !important;
				}
				.dq-form-side .layout-main { overflow-y: visible !important; padding: 0 !important; }
				.dq-form-side .form-page { padding: 0 !important; }
				.dq-form-side .form-layout { padding: 0 !important; }

				/* Right: sticky preview */
				.dq-preview-side {
					flex: 4;
					min-width: 280px;
					max-width: 50%;
					display: flex;
					flex-direction: column;
					height: 100%;
					max-height: 100%;
					border-left: 1px solid var(--border-color);
					background: var(--fg-color);
					transition: flex 0.2s ease, min-width 0.2s ease;
					overflow: hidden;
				}
				.dq-preview-side.collapsed {
					display: none !important;
				}
				.dq-preview-header {
					display: flex;
					align-items: center;
					gap: 6px;
					padding: 8px 12px;
					border-bottom: 1px solid var(--border-color);
					flex-shrink: 0;
					background: var(--fg-color);
				}
				.dq-preview-filename {
					flex: 1;
					font-size: var(--text-sm);
					color: var(--text-muted);
					white-space: nowrap;
					overflow: hidden;
					text-overflow: ellipsis;
				}
				.dq-preview-header .icon-btn {
					padding: 4px;
					color: var(--text-muted);
					border: none;
					background: transparent;
					border-radius: var(--border-radius-sm, 4px);
					display: inline-flex;
					align-items: center;
					justify-content: center;
					cursor: pointer;
					transition: color 0.15s ease, background-color 0.15s ease;
				}
				.dq-preview-header .icon-btn:hover {
					color: var(--text-color);
					background: var(--bg-light-gray);
				}
				.dq-preview-reopen-btn {
					position: absolute;
					top: 8px;
					right: 12px;
					z-index: 20;
					padding: 6px;
					border: 1px solid var(--border-color);
					background: var(--fg-color, #fff);
					color: var(--text-muted);
					border-radius: var(--border-radius-sm, 4px);
					display: none;
					align-items: center;
					justify-content: center;
					cursor: pointer;
					box-shadow: var(--shadow-sm, 0 1px 2px rgba(0,0,0,0.05));
					transition: color 0.15s ease, background-color 0.15s ease;
				}
				.dq-preview-reopen-btn:hover {
					color: var(--text-color);
					background: var(--bg-light-gray, #f4f5f6);
				}
				.dq-preview-header .icon-btn svg,
				.dq-preview-reopen-btn svg {
					width: 16px;
					height: 16px;
					display: block;
				}
				.dq-preview-body {
					flex: 1;
					overflow: hidden;
					min-height: 0;
					display: flex;
					flex-direction: column;
					background: var(--control-bg);
				}
				.dq-preview-body iframe {
					flex: 1;
					width: 100%;
					height: 100%;
					border: none;
					background: #fff;
				}
				</style>
			`);
			$("head").append(this.$custom_styles);
		}
	}

	// -------------------------------------------------------------------------
	// SCREEN SCAFFOLDING
	// -------------------------------------------------------------------------

	_build_screens() {
		const $body = this._body();
		this.$list_screen        = $('<div class="dq-list-screen"></div>').appendTo($body);
		this.$review_screen      = $('<div class="dq-review-screen" style="display:none;"></div>').appendTo($body);
		this.$form_side          = $('<div class="dq-form-side"></div>').appendTo(this.$review_screen);
		this.$preview_side       = $('<div class="dq-preview-side"></div>').appendTo(this.$review_screen);
		this.$preview_header     = $('<div class="dq-preview-header"></div>').appendTo(this.$preview_side);
		this.$preview_body       = $('<div class="dq-preview-body"></div>').appendTo(this.$preview_side);

		this.$preview_reopen_btn = $(`
			<button type="button" class="dq-preview-reopen-btn" title="${__("Show preview")}">
				${frappe.utils.icon("panel-right-open", "sm")}
			</button>
		`).appendTo(this.$review_screen).on("click", () => this._toggle_preview());

		this._build_preview_header();
	}

	_build_preview_header() {
		this.$preview_filename = $(
			`<span class="dq-preview-filename">${__("Preview")}</span>`
		).appendTo(this.$preview_header);

		// "Open in new tab" link -- matches attachments.js pattern
		this.$preview_open_link = $(`
			<a class="btn btn-link icon-btn" target="_blank" rel="noopener noreferrer"
			   title="${__("Open file in new tab")}">
				${frappe.utils.icon("external-link", "sm")}
			</a>
		`).appendTo(this.$preview_header);

		// Toggle close (hide preview)
		this.$preview_toggle = $(`
			<button type="button" class="btn btn-link icon-btn dq-preview-toggle-btn" title="${__("Hide preview")}">
				${frappe.utils.icon("panel-right-close", "sm")}
			</button>
		`).appendTo(this.$preview_header).on("click", () => this._toggle_preview());
	}

	// -------------------------------------------------------------------------
	// SCREEN 1 -- EMBEDDED LIST
	// -------------------------------------------------------------------------

	_setup_list() {
		const $wrapper = $('<div class="dq-list-wrapper"></div>').appendTo(this.$list_screen);

		this.list = new frappe.ui.EmbeddedList({
			wrapper: $wrapper,
			doctype: "Document Queue",
			title: __("Documents"),
			page_size: 20,
			fields: ["name", "status", "source_file", "document_type", "creation"],
			filters: { document_type: this.doctype, status: "Ready for Review" },
			order_by: this.sort_by,
			after_render: () => {
				const count = this.list.data ? this.list.data.length : 0;
				this.list.$header.find(".embedded-list-title").text(__("Documents ({0})", [count]));
			},
			on_row_click: (row) => this._open_review(row),
			columns: [
				{
					label: __("ID"),
					fieldname: "name",
					render: (row) => `<span class="text-muted">${frappe.utils.escape_html(row.name)}</span>`,
				},
				{
					label: __("Status"),
					fieldname: "status",
					render: (row) => {
						const short = row.status === "Ready for Review" ? "Review" : row.status;
						const theme =
							row.status === "Ready for Review" || row.status === "Queued" ? "blue"
							: row.status === "Completed"   ? "green"
							: row.status === "Processing"  ? "orange"
							: row.status === "Failed"      ? "red"
							: "gray";
						return frappe.ui.badge.html({ label: short, theme });
					},
				},
				{
					label: __("Source File"),
					fieldname: "source_file",
					render: (row) => {
						const name = frappe.document_queue_review.get_file_name(row.source_file || "");
						return frappe.utils.escape_html(name || "—");
					},
				},
				{
					label: __("Target Doctype"),
					fieldname: "document_type",
					render: (row) => frappe.utils.escape_html(row.document_type || "—"),
				},
				{
					label: __("Created On"),
					fieldname: "creation",
					render: (row) => frappe.datetime.comment_when(row.creation, true),
				},
			],
		});

		// Standard Frappe load-more placed cleanly below the table
		this.list.render_load_more = () => {
			this.list.$result.find(".embedded-list-more").remove();
			if (this.list.rendered_count >= this.list.data.length) return;

			$(
				`<div class="embedded-list-more">
					<span class="embedded-list-count text-muted">${__(
						"Showing {0} of {1}",
						[this.list.rendered_count, this.list.data.length]
					)}</span>
					${frappe.ui.button.html({
						label: __("Load More"),
						size: "sm",
						attrs: { "data-action": "load-more" },
					})}
				</div>`
			).appendTo(this.list.$result);
		};

		// Smooth fade-in/dim override -- prevents jitter on refresh
		this.list.refresh = () => {
			this.list.$error.hide();
			this.list.$no_result.hide();
			this.list.$loading.hide();
			const is_initial = !(this.list.data && this.list.data.length > 0);
			this.list.$result
				.show()
				.css({ opacity: is_initial ? "0" : "0.5", transition: "opacity 0.3s ease" });
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

		const original_after_render = this.list.after_render.bind(this.list);
		this.list.after_render = () => {
			original_after_render();
			const count = this.list.data ? this.list.data.length : 0;
			this.list.$header.find(".embedded-list-title").text(__("Documents ({0})", [count]));
		};

		this._setup_native_toolbar();
	}

	async _setup_native_toolbar() {
		await frappe.model.with_doctype("Document Queue");

		const $actions    = this.list.$header.find(".embedded-list-header-actions");
		const $filter_wrap = $('<div class="filter-section flex align-items-center"></div>').appendTo($actions);

		this.$filter_pill = $(`
			<div class="filter-selector dropdown mr-2">
				<button type="button" class="btn btn-default btn-sm text-nowrap" data-toggle="dropdown">
					<span class="dropdown-text">${__("Review Pending")}</span>
					<span>${frappe.utils.icon("chevron-down", "xs")}</span>
				</button>
				<ul class="dropdown-menu dropdown-menu-left">
					<li><a class="dropdown-item option" data-value="Pending">${__("Review Pending")}</a></li>
					<li><a class="dropdown-item option" data-value="Completed">${__("Completed")}</a></li>
					<li><a class="dropdown-item option" data-value="All">${__("All")}</a></li>
				</ul>
			</div>
		`).appendTo($filter_wrap);

		this.$filter_pill.find(".dropdown-item").on("click", (e) => {
			e.preventDefault();
			const val = $(e.currentTarget).data("value");
			const text = $(e.currentTarget).text();
			this.$filter_pill.find(".dropdown-text").text(text);
			this._set_status_filter(val);
		});

		this.sort_selector = new frappe.ui.SortSelector({
			parent: $filter_wrap,
			doctype: "Document Queue",
			args: { sort_by: "creation", sort_order: "desc" },
			onchange: (sort_by, sort_order) => {
				this.sort_by       = `${sort_by} ${sort_order}`;
				this.list.order_by = this.sort_by;
				this.list.refresh();
			},
		});

		this.list.refresh();
	}

	_set_status_filter(status) {
		let filters = { document_type: this.doctype };
		if (status === "Pending")   filters.status = "Ready for Review";
		if (status === "Completed") filters.status = "Completed";

		this.list.filters = filters;
		this.list.refresh();
	}

	// -------------------------------------------------------------------------
	// SCREEN 2 -- OPEN REVIEW
	// -------------------------------------------------------------------------

	async _open_review(row) {
		// Dim list slightly during context load without popping a lingering toast
		this.$list_screen.css({ opacity: "0.6", "pointer-events": "none" });

		let context;
		try {
			context = await frappe.document_queue_review.fetch_context(row.name);
		} catch (e) {
			this.$list_screen.css({ opacity: "1", "pointer-events": "auto" });
			frappe.show_alert({ message: __("Failed to load document."), indicator: "red" });
			return;
		} finally {
			this.$list_screen.css({ opacity: "1", "pointer-events": "auto" });
		}

		if (!context?.queue_name) {
			frappe.show_alert({ message: __("Document context not found."), indicator: "red" });
			return;
		}

		this._current_context = context;
		this.$list_screen.hide();
		this.$review_screen.show();
		this.$preview_side.removeClass("collapsed");
		this.$preview_reopen_btn.hide();
		this._set_breadcrumb_title(row.name);
		this._render_preview(context);
		await this._mount_form(context);
		this._screen = "review";
	}

	// Breadcrumb title: "Document Queue / DQ-0001"
	// Clicking "Document Queue" acts as back -- no separate back button needed.
	_set_breadcrumb_title(queue_name) {
		const breadcrumb_html = `
			<div class="dq-header-title">
				<a class="dq-breadcrumb-root">
					${__("Document Queue")}
				</a>
				<span class="dq-breadcrumb-sep">/</span>
				<span class="dq-breadcrumb-current">${frappe.utils.escape_html(queue_name)}</span>
				<span class="dq-indicator-wrap" style="margin-left: 8px;"></span>
			</div>
		`;
		this.dialog.set_title(breadcrumb_html);
		this.dialog.header.find(".dq-breadcrumb-root").on("click", () => this._back_to_list());
	}

	_set_header_indicator(label, color = "orange") {
		const $wrap = this.dialog.header.find(".dq-indicator-wrap");
		if (!$wrap.length) return;
		if (!label) {
			$wrap.empty();
			return;
		}
		const badge = frappe.ui.badge.html({
			label: label,
			theme: color,
			size: "sm",
		});
		$wrap.html(badge);
	}

	// -------------------------------------------------------------------------
	// SCREEN 2 -- PREVIEW (right side)
	// -------------------------------------------------------------------------

	_render_preview(context) {
		const source_url = context.source_file_url || context.source_file || "";
		const file_name  = frappe.document_queue_review.get_file_name(source_url);

		this.$preview_filename.text(file_name || __("Preview")).attr("title", file_name || "");
		this.$preview_open_link.attr("href", source_url || "#").toggle(!!source_url);

		// Reuse existing function from document_queue_review.js -- no reinvention
		const markup = frappe.document_queue_review.get_preview_markup(source_url, file_name);
		this.$preview_body.html(markup);
	}

	_toggle_preview() {
		const collapsed = this.$preview_side.hasClass("collapsed");
		if (collapsed) {
			this.$preview_side.removeClass("collapsed");
			this.$preview_reopen_btn.hide();
		} else {
			// Collapse without clearing iframe src -- keeps PDF loaded for instant re-open
			this.$preview_side.addClass("collapsed");
			this.$preview_reopen_btn.show();
		}
	}

	// -------------------------------------------------------------------------
	// SCREEN 2 -- FORM (left side, native frappe.ui.form.Form)
	// -------------------------------------------------------------------------

	async _mount_form(context) {
		this._destroy_form();

		const doctype   = context.document_type;
		const extracted = context.extracted_data || {};

		// Ensure meta is fetched before instantiating the form
		await new Promise((resolve) => frappe.model.with_doctype(doctype, resolve));

		// Create a new unsaved doc in the client-side model store
		const doc = frappe.model.get_new_doc(doctype);

		// Backup cur_frm so we can restore it when the modal closes
		this._prev_frm = window.cur_frm;

		// Instantiate the native Frappe form engine inside our modal div.
		// in_form=false + in_dialog=true: prevents rename_notify from calling frappe.set_route
		// which would hijack the browser URL away from the list view on save.
		this.frm = new frappe.ui.form.Form(doctype, this.$form_side.get(0), false);
		this.frm.in_dialog = true;
		this.frm.refresh(doc.name);

		// Override cur_frm so client scripts that reference cur_frm work correctly
		window.cur_frm = this.frm;

		// Hide Attach / Attach Image fields -- user sees the file in the preview pane
		frappe.get_meta(doctype).fields.forEach((df) => {
			if (["Attach", "Attach Image"].includes(df.fieldtype)) {
				this.frm.set_df_property(df.fieldname, "hidden", 1);
			}
		});

		// Pre-fill extracted data using native frm.set_value.
		const valid_fieldnames = frappe.get_meta(doctype).fields.map((f) => f.fieldname);
		for (const [fieldname, value] of Object.entries(extracted)) {
			if (valid_fieldnames.includes(fieldname) && this.frm.fields_dict[fieldname]) {
				await this.frm.set_value(fieldname, value);
			}
		}

		// Clear dirty state from initial pre-filling
		if (this.frm.doc) {
			this.frm.doc.__unsaved = 0;
		}
		this._set_header_indicator("", "");

		// Listen to Frappe's native dirty event -- ONLY show "Not Saved" when the
		// user actually edits a field after initial form mount.
		$(this.frm.wrapper).off("dirty.dq-modal").on("dirty.dq-modal", () => {
			if (this.frm && this.frm.is_dirty()) {
				this._set_header_indicator(__("Not Saved"), "orange");
				if (this.$primary_action_btn) {
					this.$primary_action_btn.prop("disabled", false).text(__("Save"));
				}
			}
		});

		this._setup_header_save();
	}

	// Save button placed at the extreme right in the modal header (left of close button).
	// Overrides dialog.get_primary_btn so that Frappe's Ctrl+S shortcut (desk.js)
	// correctly triggers our Save / Submit button instead of looking in the footer.
	_setup_header_save() {
		this.dialog.header.find(".dq-save-btn").remove();
		this.dialog.header.find(".dq-submit-badge").remove();
		this.$primary_action_btn = $(`
			<button type="button" class="btn btn-primary btn-sm dq-save-btn">
				${__("Save")}
			</button>
		`);
		// Place to the left of the close button in .modal-actions (extreme right)
		this.dialog.header.find(".modal-actions").prepend(this.$primary_action_btn);
		this.$primary_action_btn.on("click", () => this._save_form());

		// Override get_primary_btn so Ctrl+S (desk.js:trigger_primary_action) hits our button
		this._orig_get_primary_btn = this.dialog.get_primary_btn.bind(this.dialog);
		this.dialog.get_primary_btn = () => this.$primary_action_btn;
	}

	_save_form() {
		if (!this.frm) return;

		const btn = this.$primary_action_btn ? this.$primary_action_btn.get(0) : null;
		if (this.$primary_action_btn) {
			this.$primary_action_btn.prop("disabled", true).text(__("Saving\u2026"));
		}
		this._set_header_indicator(__("Saving\u2026"), "gray");

		const queue_name = this._current_context?.queue_name;
		const doctype    = this.frm.doctype;

		const on_error = () => {
			// Called by Frappe when validation fails or a mandatory field is empty.
			// Always re-enables the Save button so the user can try again.
			if (this.$primary_action_btn) {
				this.$primary_action_btn.prop("disabled", false).text(__("Save"));
			}
			if (this.frm && this.frm.is_dirty()) {
				this._set_header_indicator(__("Not Saved"), "orange");
			} else {
				this._set_header_indicator("", "");
			}
		};

		// on_save_callback fires inside after_save AFTER frm.refresh() --
		// at this point frm.doc.name is the real server-assigned name (rename done).
		const on_save_callback = (r) => {
			if (r && r.exc) {
				on_error();
				return;
			}
			// Manually link the Document Queue to the newly saved document.
			frappe.call({
				method: "frappe.core.doctype.document_queue.document_queue.link_to_document",
				args: {
					document_queue: queue_name,
					document_type:  doctype,
					document_name:  this.frm.doc.name,  // real name after frm.refresh()
				},
				callback: (link_r) => {
					if (link_r && link_r.exc) {
						on_error();
						return;
					}

					// Refresh outer list view and list action banner
					if (window.cur_list && window.cur_list.doctype === doctype) {
						window.cur_list.refresh();
					}

					if (frappe.model.is_submittable(doctype)) {
						// Submittable doctype: swap Save → Submit button and add header badge
						this._show_submit_btn();
					} else {
						// Non-submittable: done -- go back to list
						this._set_header_indicator(__("Saved"), "green");
						frappe.show_alert({ message: __("Saved successfully"), indicator: "green" });
						this._back_to_list();
					}
				},
				error: on_error,
			});
		};

		// Pass btn element so Frappe's save.js / form.js can reset it on mandatory errors
		this.frm.save("Save", on_save_callback, btn, on_error);

		// Synchronous fallback check: if mandatory check fails synchronously,
		// Frappe immediately re-enables the button without calling on_error.
		setTimeout(() => {
			if (this.$primary_action_btn && !this.$primary_action_btn.prop("disabled")) {
				this.$primary_action_btn.text(__("Save"));
				if (this.frm && this.frm.is_dirty()) {
					this._set_header_indicator(__("Not Saved"), "orange");
				}
			}
		}, 150);
	}

	// Show the Submit button after a successful save for submittable doctypes.
	_show_submit_btn() {
		const indicator = frappe.get_indicator(this.frm.doc) || [__("Draft"), "red"];
		this._set_header_indicator(indicator[0], indicator[1]);

		// Remove any existing badge
		this.dialog.header.find(".dq-submit-badge").remove();

		// Add subtle Espresso badge to the left of Submit button
		const $badge = $(`
			<div class="dq-submit-badge">
				${frappe.ui.badge.html({ label: __("Submit to Confirm"), theme: "blue", size: "sm" })}
			</div>
		`);
		this.dialog.header.find(".modal-actions").prepend($badge);

		this.$primary_action_btn
			.prop("disabled", false)
			.removeClass("btn-primary")
			.addClass("btn-primary dq-submit-btn")
			.text(__("Submit"));

		// Rebind click to submit action
		this.$primary_action_btn.off("click").on("click", () => this._submit_form());
	}

	_submit_form() {
		if (!this.frm) return;

		const btn = this.$primary_action_btn ? this.$primary_action_btn.get(0) : null;
		if (this.$primary_action_btn) {
			this.$primary_action_btn.prop("disabled", true).text(__("Submitting\u2026"));
		}
		this._set_header_indicator(__("Submitting\u2026"), "gray");

		const on_error = () => {
			// Restores button if user cancels confirm dialog or submit validation fails
			if (this.$primary_action_btn) {
				this.$primary_action_btn.prop("disabled", false).text(__("Submit"));
			}
			const indicator = frappe.get_indicator(this.frm.doc) || [__("Draft"), "red"];
			this._set_header_indicator(indicator[0], indicator[1]);
		};

		const on_success = () => {
			this._set_header_indicator(__("Submitted"), "blue");
			frappe.show_alert({ message: __("Submitted successfully"), indicator: "green" });

			// Refresh outer list view and list action banner
			if (window.cur_list && window.cur_list.doctype === this.doctype) {
				window.cur_list.refresh();
			}

			this._back_to_list();
		};

		// frm.savesubmit(btn, callback, on_error)
		this.frm.savesubmit(btn, on_success, on_error);
	}

	// -------------------------------------------------------------------------
	// NAVIGATION -- BACK TO LIST
	// -------------------------------------------------------------------------

	_back_to_list() {
		this._destroy_form();
		this.dialog.set_title(__("Document Queue"));
		this.dialog.header.find(".dq-save-btn").remove();
		this.dialog.header.find(".dq-submit-badge").remove();
		this.dialog.header.find(".dq-indicator-wrap").remove();

		// Restore dialog.get_primary_btn to native implementation
		if (this._orig_get_primary_btn) {
			this.dialog.get_primary_btn = this._orig_get_primary_btn;
			this._orig_get_primary_btn = null;
		}
		this.$primary_action_btn = null;

		// Reset preview toggle for the next document
		this.$preview_side.removeClass("collapsed");
		this.$preview_reopen_btn.hide();

		this.$review_screen.hide();
		this.$list_screen.show();
		this._screen = "list";

		// Refresh modal list so completed/saved items are updated immediately
		if (this.list) {
			this.list.refresh();
		}

		// Also refresh outer list view if open behind the modal
		if (window.cur_list && window.cur_list.doctype === this.doctype) {
			window.cur_list.refresh();
		}
	}

	// -------------------------------------------------------------------------
	// CLEANUP
	// -------------------------------------------------------------------------

	_destroy_form() {
		if (this.frm) {
			// Detach the dirty listener before destroying
			$(this.frm.wrapper).off("dirty.dq-modal");
			// Blank the iframe so the browser releases the PDF from memory
			this.$preview_body.find("iframe").attr("src", "about:blank");
			// Restore the original cur_frm
			window.cur_frm = this._prev_frm;
			this._prev_frm = null;
			this.$form_side.empty();
			this.frm = null;
		}
	}

	_on_dialog_hide() {
		this._destroy_form();
		this._body().find("iframe").attr("src", "about:blank");
		this.$preview_side?.removeClass("collapsed");
		this.$preview_reopen_btn?.hide();
		this.dialog.header.find(".dq-save-btn").remove();
		this.dialog.header.find(".dq-submit-badge").remove();
		this.dialog.header.find(".dq-indicator-wrap").remove();
		// Restore dialog.get_primary_btn if we overrode it
		if (this._orig_get_primary_btn) {
			this.dialog.get_primary_btn = this._orig_get_primary_btn;
			this._orig_get_primary_btn = null;
		}
		this.$primary_action_btn = null;
		this._screen = "list";

		// Refresh outer list view when modal closes
		if (window.cur_list && window.cur_list.doctype === this.doctype) {
			window.cur_list.refresh();
		}
	}
};
