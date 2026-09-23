// Embedded split-screen modal for reviewing Attachment Queue items.
// Left pane: embedded list of queue records. Right pane: file preview.

frappe.ui.AttachmentQueueModal = class AttachmentQueueModal {
	/** @param {{ doctype: string, title?: string }} options */
	constructor(options = {}) {
		this.doctype = options.doctype;
		this.title =
			options.title ||
			(this.doctype ? __("Documents - {0}", [__(this.doctype)]) : __("Documents"));
		this.sort_by = "creation desc";
		this.page_size = 25;
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

		this.dialog.$wrapper.on("show.bs.modal", () => {
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

		this.dialog.$wrapper.on("hidden.bs.modal", () => this._end_session());
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
			padding: "0",
		});
		this.dialog
			.get_field("body")
			.$wrapper.parentsUntil(".modal-body")
			.css({ padding: "0", margin: "0", border: "none" });
	}

	_build_screens() {
		this.$split_screen = $('<div class="aq-split-screen"></div>').appendTo(
			this.dialog.get_field("body").$wrapper
		);
		this.$list_pane = $('<div class="aq-list-pane"></div>').appendTo(this.$split_screen);
		this.$preview_pane = $('<div class="aq-preview-pane"></div>').appendTo(this.$split_screen);

		this.$preview_content = $('<div class="aq-preview-content"></div>').appendTo(
			this.$preview_pane
		);

		this.$start_review_btn = frappe.ui.button({
			label: __("Start Review"),
			variant: "solid",
			disabled: true,
			onclick: () => this._start_review(this.selected_row),
		});

		// Uses the same layout as the list pane so both panes share one baseline.
		$(`
			<div class="aq-preview-footer level">
				<div class="level-left"></div>
				<div class="level-right"></div>
			</div>
		`)
			.appendTo(this.$preview_pane)
			.find(".level-right")
			.append(this.$start_review_btn);
	}

	// EmbeddedList is available only after the modal opens, so create and cache the subclass on first use.
	_get_list_class() {
		if (frappe.ui.AttachmentQueueEmbeddedList) {
			return frappe.ui.AttachmentQueueEmbeddedList;
		}

		frappe.ui.AttachmentQueueEmbeddedList = class AttachmentQueueEmbeddedList extends (
			frappe.ui.EmbeddedList
		) {
			// EmbeddedList has no pagination, so this replaces the default "Load More" area.
			render_load_more() {
				const total_count = (this.data || []).length;
				const rendered_count = Math.min(this.rendered_count || 0, total_count);

				let $paging_area = this.$wrapper.find(".list-paging-area");
				if (!$paging_area.length) {
					$paging_area = $(`
						<div class="list-paging-area level">
							<div class="level-left"></div>
							<div class="level-right">
								<span class="list-count"></span>
							</div>
						</div>
					`).appendTo(this.$wrapper);

					const paging_values = [10, 25, 50, 100];
					if (frappe.ui.TabButtons) {
						const tab_buttons = new frappe.ui.TabButtons({
							label: __("Page Size"),
							options: paging_values.map((val) => ({
								label: String(val),
								value: val,
							})),
							value: this.page_size,
							on_change: (val) => {
								this.page_size = val;
								this.modal.page_size = val;
								// render() rebuilds the rows, so we call after_render()
								// to restore the selection, count and filter label.
								this.render();
								this.after_render();
							},
						});
						$paging_area.find(".level-left").append(tab_buttons.$el);
					}
				}

				$paging_area.find(".list-count").text(`${rendered_count} of ${total_count}`);

				$paging_area.find(".btn-more").remove();
				if (rendered_count < total_count) {
					const $more_btn = frappe.ui.button({
						label: __("Load More"),
						attrs: { "data-action": "load-more" },
					});
					$more_btn.addClass("btn-more");
					$more_btn.on("click", (e) => {
						e.preventDefault();
						this.render_more();
					});
					$paging_area.find(".level-right").append($more_btn);
				}
			}

			after_render() {
				super.after_render();
				this.render_load_more();
				this.modal._update_active_row();
			}

			// Fade the old rows while loading; refresh() sets up the DOM before fetching new data.
			refresh() {
				const is_initial = !(this.data && this.data.length > 0);
				const refreshed = super.refresh();

				this.$loading.hide();
				this.$result
					.show()
					.css({ opacity: is_initial ? "0" : "0.5", transition: "opacity 0.2s ease" });

				return refreshed.finally(() => {
					requestAnimationFrame(() =>
						requestAnimationFrame(() => this.$result.css("opacity", "1"))
					);
				});
			}
		};

		return frappe.ui.AttachmentQueueEmbeddedList;
	}

	// Sets up the EmbeddedList subclass with custom pagination and refresh behavior.
	_setup_list() {
		this.$list_wrapper = $('<div class="aq-list-wrapper"></div>').appendTo(this.$list_pane);

		const AttachmentQueueEmbeddedList = this._get_list_class();
		const STATUS_THEME = {
			"Ready for Review": "blue",
			Queued: "blue",
			Completed: "green",
			Processing: "amber",
			Failed: "red",
		};

		this.list = new AttachmentQueueEmbeddedList({
			wrapper: this.$list_wrapper,
			modal: this,
			doctype: "Attachment Queue",
			page_size: this.page_size,
			fields: ["name", "status", "source_file", "creation"],
			filters: { document_type: this.doctype, status: "Ready for Review" },
			order_by: this.sort_by,
			on_row_click: (row) => this._toggle_row_selection(row),
			columns: [
				{
					label: __("Source File"),
					fieldname: "source_file",
					render: (row) => {
						const name = frappe.attachment_queue_review.get_file_name(
							row.source_file || ""
						);
						return frappe.utils.escape_html(name || "—");
					},
				},
				{
					label: __("Status"),
					fieldname: "status",
					// Shortened to fit the narrow column and translated from the raw Select values.
					render: (row) => {
						const short =
							row.status === "Ready for Review" ? __("Review") : __(row.status);
						const theme = STATUS_THEME[row.status] || "gray";
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

		this.list.render_load_more();

		this._setup_native_toolbar().catch((error) => {
			console.error("Failed to set up Attachment Queue toolbar", error);
		});
	}

	_toggle_row_selection(row) {
		if (this.selected_row && this.selected_row.name === row.name) {
			this.selected_row = null;
			this._clear_preview();
		} else {
			this.selected_row = row;
			this._render_preview(row);
		}
		this._update_active_row();
	}

	_end_session() {
		this.selected_row = null;
		this._update_active_row();
		this._clear_preview();
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
		if (!this.$preview_content) return;
		this.$preview_content.empty();

		const $empty_wrap = $('<div class="aq-preview-empty-container"></div>').appendTo(
			this.$preview_content
		);

		const $empty = frappe.ui.empty_state({
			icon: "file-text",
			title: __("No Document Selected"),
			description: __("Select a document from the list to preview."),
		});
		$empty_wrap.append($empty);

		this.$start_review_btn.prop("disabled", true);
	}

	_render_preview(row) {
		if (!this.$preview_content) return;
		this.$preview_content.empty();

		const file_url = frappe.attachment_queue_review.get_preview_url(row.source_file);
		const file_name =
			frappe.attachment_queue_review.get_file_name(row.source_file || "") || file_url;
		const preview_type = this._get_preview_type(row.source_file);

		this.$start_review_btn.prop("disabled", false);

		const $body = $('<div class="aq-preview-body"></div>').appendTo(this.$preview_content);

		const escaped_url = frappe.utils.escape_html(file_url);
		const escaped_name = frappe.utils.escape_html(file_name);

		if (preview_type === "pdf") {
			$body.html(`<iframe src="${escaped_url}" title="${escaped_name}"></iframe>`);
		} else if (preview_type === "image") {
			$body.html(`<img src="${escaped_url}" alt="${escaped_name}">`);
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
		if (!row) return;

		const queue_name = row.name;
		let context = null;

		try {
			context = await frappe.attachment_queue_review.fetch_context(queue_name);
		} catch (e) {
			console.error("Failed to fetch document review context", e);
			frappe.show_alert({
				message: __(
					"Could not load review details. Opening the Attachment Queue record instead."
				),
				indicator: "orange",
			});
		}

		// The list row may be outdated, so use the latest context to check if it's still reviewable.
		const statuses = frappe.attachment_queue_review.reviewable_statuses;
		if (context && !statuses.includes(context.status)) {
			frappe.msgprint(__("Only documents that are ready for review can be reviewed."));
			// The row is no longer available for review, so keep the dialog open and show the updated list.
			this._end_session();
			this.list.refresh();
			return;
		}

		this.dialog.hide();

		if (context && context.document_type) {
			frappe.attachment_queue_review.route_to_new_document(context);
			return;
		}

		// Fallback to Attachment Queue form
		frappe.set_route("Form", "Attachment Queue", queue_name);
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

	async _setup_native_toolbar() {
		const $header = this.list.$header;
		$header.show().html(`
			<div class="embedded-list-header-left">
				<input type="text" class="form-control form-control-sm embedded-list-search" data-action="search" placeholder="${__(
					"Search"
				)}">
			</div>
			<div class="embedded-list-header-actions">
				<div class="filter-section"></div>
			</div>
		`);

		const $actions_wrap = $header.find(".filter-section");

		this.$status_trigger = frappe.ui.button({
			label: __("Review Pending"),
			icon_right: "chevron-down",
		});
		$actions_wrap.append(this.$status_trigger);

		new frappe.ui.Dropdown({
			trigger: this.$status_trigger,
			options: [
				{
					label: __("Review Pending"),
					onclick: () => this._set_status_filter("Pending", __("Review Pending")),
				},
				{
					label: __("Completed"),
					onclick: () => this._set_status_filter("Completed", __("Completed")),
				},
				{
					label: __("All"),
					onclick: () => this._set_status_filter("All", __("All")),
				},
			],
		});

		this.$sort_trigger = frappe.ui.button({
			label: __("Newest First"),
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
						this._set_sort(
							"creation desc",
							__("Newest First"),
							"arrow-down-wide-narrow"
						),
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
		this.list.order_by = sort_by;
		frappe.ui.button.dress(this.$sort_trigger, { label, icon, icon_right: "chevron-down" });
		this.list.refresh();
	}

	_set_status_filter(status, label) {
		const filters = { document_type: this.doctype };
		if (status === "Pending") filters.status = "Ready for Review";
		if (status === "Completed") filters.status = "Completed";
		this.list.filters = filters;
		frappe.ui.button.dress(this.$status_trigger, { label, icon_right: "chevron-down" });
		this.list.refresh();
	}
};
