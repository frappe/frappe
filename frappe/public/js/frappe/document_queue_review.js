frappe.provide("frappe.document_queue_review");

frappe.document_queue_review.storage_key = "frappe.document_queue_review.pending_context";
frappe.document_queue_review.ttl_ms = 2 * 60 * 1000;
frappe.document_queue_review.width_storage_key = "frappe.document_queue_review.preview_width";
frappe.document_queue_review.default_preview_width = 38;
frappe.document_queue_review.reviewable_statuses = ["Ready for Review", "Failed"];
frappe.document_queue_review.upload_first_enabled = {};

frappe.document_queue_review.start_from_document_queue = async function (frm) {
	if (!frappe.document_queue_review.reviewable_statuses.includes(frm.doc.status)) {
		frappe.msgprint(__("Only documents that are ready for review can be reviewed."));
		return;
	}

	let document_type = frm.doc.document_type;

	if (!document_type) {
		document_type = await frappe.document_queue_review.prompt_document_type();
		if (!document_type) {
			return;
		}

		await frm.call("set_document_type", { document_type });
		await frm.reload_doc();
	}

	const context = await frappe.document_queue_review.fetch_context(frm.doc.name);
	if (!frappe.document_queue_review.reviewable_statuses.includes(context?.status)) {
		frappe.msgprint(__("Only documents that are ready for review can be reviewed."));
		return;
	}

	if (!context?.document_type) {
		frappe.msgprint(__("Select a target DocType before starting review."));
		return;
	}

	frappe.document_queue_review.store_pending_context(context);
	frappe.new_doc(context.document_type);
};

frappe.document_queue_review.prompt_document_type = function () {
	return new Promise((resolve) => {
		let resolved = false;
		const dialog = new frappe.ui.Dialog({
			title: __("Select Document Type"),
			fields: [
				{
					fieldname: "document_type",
					fieldtype: "Link",
					label: __("Document Type"),
					options: "DocType",
					reqd: 1,
					get_query() {
						return {
							filters: {
								enable_upload_first_workflow: 1,
								istable: 0,
							},
						};
					},
				},
			],
			primary_action_label: __("Start Review"),
			primary_action(values) {
				resolved = true;
				dialog.hide();
				resolve(values.document_type);
			},
		});
		dialog.onhide = () => {
			if (!resolved) {
				resolve(null);
			}
		};
		dialog.show();
	});
};

frappe.document_queue_review.fetch_context = function (document_queue) {
	return frappe
		.call({
			method: "frappe.core.doctype.document_queue.document_queue.get_document_review_context",
			args: { document_queue },
		})
		.then((r) => r.message || null);
};

frappe.document_queue_review.store_pending_context = function (context) {
	const wrapped = {
		context,
		created_at: Date.now(),
	};
	frappe._document_queue_pending_review_context = context;
	frappe._document_queue_pending_review_context_created_at = wrapped.created_at;

	try {
		sessionStorage.setItem(frappe.document_queue_review.storage_key, JSON.stringify(wrapped));
	} catch (e) {
		// no-op
	}
};

frappe.document_queue_review.consume_pending_context = function () {
	const globalContext = frappe._document_queue_pending_review_context;
	const globalAge =
		Date.now() - Number(frappe._document_queue_pending_review_context_created_at || 0);

	if (globalContext?.queue_name && globalAge <= frappe.document_queue_review.ttl_ms) {
		delete frappe._document_queue_pending_review_context;
		delete frappe._document_queue_pending_review_context_created_at;
		frappe.document_queue_review.clear_pending_context();
		return globalContext;
	}

	try {
		const raw = sessionStorage.getItem(frappe.document_queue_review.storage_key);
		const parsed = raw ? JSON.parse(raw) : null;
		const age = Date.now() - Number(parsed?.created_at || 0);
		if (parsed?.context?.queue_name && age <= frappe.document_queue_review.ttl_ms) {
			frappe.document_queue_review.clear_pending_context();
			return parsed.context;
		}
	} catch (e) {
		// no-op
	}

	frappe.document_queue_review.clear_pending_context();
	return null;
};

frappe.document_queue_review.clear_pending_context = function () {
	try {
		sessionStorage.removeItem(frappe.document_queue_review.storage_key);
	} catch (e) {
		// no-op
	}
};

frappe.document_queue_review.is_upload_first_enabled = function (doctype) {
	if (!doctype || doctype === "Document Queue") {
		return Promise.resolve(false);
	}

	if (doctype in frappe.document_queue_review.upload_first_enabled) {
		return Promise.resolve(frappe.document_queue_review.upload_first_enabled[doctype]);
	}

	return frappe
		.call({
			method: "frappe.core.doctype.document_queue.document_queue.is_upload_first_workflow_enabled",
			args: { document_type: doctype },
		})
		.then((r) => {
			const enabled = Boolean(r.message);
			frappe.document_queue_review.upload_first_enabled[doctype] = enabled;
			return enabled;
		})
		.catch(() => false);
};

frappe.document_queue_review.setup_upload_first = async function (frm) {
	if (!frm?.is_new?.() || frappe.document_queue_review.get_context(frm)) {
		frappe.document_queue_review.remove_upload_first(frm);
		return;
	}

	const enabled = await frappe.document_queue_review.is_upload_first_enabled(frm.doctype);
	if (!enabled || frappe.document_queue_review.get_context(frm)) {
		frappe.document_queue_review.remove_upload_first(frm);
		return;
	}

	frappe.document_queue_review.add_styles();

	const $page = frm.$wrapper.find(".form-page").first();
	if (!$page.length) {
		return;
	}

	$page.find(".document-queue-upload-first").remove();

	const $banner = $(`
		<div class="document-queue-upload-first">
			<div>
				<div class="document-queue-upload-first-title">${__("Upload Document")}</div>
				<div class="document-queue-upload-first-description">
					${__("Upload one PDF or image before creating a draft.")}
				</div>
			</div>
			<button class="btn btn-default btn-sm document-queue-upload-first-button" type="button">
				${frappe.utils.icon("upload", "sm")}
				<span>${__("Upload")}</span>
			</button>
		</div>
	`);

	$banner.find(".document-queue-upload-first-button").on("click", () => {
		frappe.document_queue_review.open_upload_first_dialog(frm);
	});

	$page.prepend($banner);
	frm.document_queue_upload_first_banner = $banner;
};

frappe.document_queue_review.remove_upload_first = function (frm) {
	frm?.document_queue_upload_first_banner?.remove();
	frm.document_queue_upload_first_banner = null;
	frm?.$wrapper?.find(".document-queue-upload-first").remove();
};

frappe.document_queue_review.open_upload_first_dialog = async function (frm) {
	await frappe.require("file_uploader.bundle.js");

	new frappe.ui.FileUploader({
		allow_multiple: false,
		allow_web_link: false,
		restrictions: {
			allowed_file_types: [".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"],
		},
		dialog_title: __("Upload Source Document"),
		on_success(file_doc) {
			if (!file_doc?.name) {
				frappe.msgprint(__("Could not create a file from the upload."));
				return;
			}

			frappe.document_queue_review.create_upload_first_queue(frm, file_doc.name);
		},
	});
};

frappe.document_queue_review.create_upload_first_queue = async function (frm, file_name) {
	frappe.dom.freeze(__("Extracting document"));
	try {
		const r = await frappe.call({
			method: "frappe.core.doctype.document_queue.document_queue.create_upload_first_queue",
			args: {
				file_name,
				document_type: frm.doctype,
			},
		});

		let context = r.message;
		if (!context?.queue_name) {
			frappe.msgprint(__("Could not create a Document Queue record."));
			return;
		}

		context = await frappe.document_queue_review.wait_for_extraction(context);

		if (context.status === "Failed") {
			frappe.msgprint({
				title: __("Extraction Failed"),
				message: __(
					"The document was queued, but extraction failed. You can still review it from Document Queue."
				),
				indicator: "red",
			});
		}

		frappe.document_queue_review.store_pending_context(context);
		await frappe.new_doc(context.document_type);
	} finally {
		frappe.dom.unfreeze();
	}
};

frappe.document_queue_review.wait_for_extraction = async function (context) {
	if (!["Queued", "Processing"].includes(context.status)) {
		return context;
	}

	let latest_context = context;
	for (let attempt = 0; attempt < 90; attempt++) {
		await new Promise((resolve) => setTimeout(resolve, 1000));

		const response = await frappe.call({
			method: "frappe.core.doctype.document_queue.document_queue.get_document_review_context",
			args: {
				document_queue: context.queue_name,
			},
		});

		latest_context = response.message || latest_context;
		if (!["Queued", "Processing"].includes(latest_context.status)) {
			return latest_context;
		}
	}

	frappe.msgprint({
		title: __("Extraction Still Running"),
		message: __(
			"The document was queued, but extraction is taking longer than expected. You can continue reviewing it from Document Queue when extraction finishes."
		),
		indicator: "orange",
	});

	return latest_context;
};

frappe.document_queue_review.get_context = function (frm) {
	return frm.document_queue_review_context || frm.doc.__document_queue_review_context || null;
};

frappe.document_queue_review.hydrate_context = function (frm) {
	if (frappe.document_queue_review.get_context(frm)) {
		return;
	}

	const routeContext = frappe.route_options?.document_queue_review_context;
	const pendingContext = frm.is_new()
		? frappe.document_queue_review.consume_pending_context()
		: null;
	const context = routeContext?.queue_name ? routeContext : pendingContext;

	if (!context?.queue_name || context.document_type !== frm.doctype) {
		return;
	}

	frm.document_queue_review_context = context;
	frm.doc.__document_queue_review_context = context;
	frm.doc.__document_queue_name = context.queue_name;
};

frappe.document_queue_review.mount = function (frm) {
	const context = frappe.document_queue_review.get_context(frm);
	if (!context?.queue_name) {
		frappe.document_queue_review.teardown(frm);
		return;
	}

	const $layout = frm.$wrapper.find(".form-layout").first();
	if (!$layout.length) {
		return;
	}

	frappe.document_queue_review.add_styles();
	frappe.document_queue_review.remove_upload_first(frm);
	const $std = $layout.closest(".std-form-layout");
	$std.addClass("document-queue-review-layout");
	frappe.document_queue_review.apply_saved_width($std);

	if (!frm.document_queue_review_panel) {
		frm.document_queue_review_panel = $(`<aside class="document-queue-review-panel"></aside>`);
		$std.length
			? $std.prepend(frm.document_queue_review_panel)
			: $layout.before(frm.document_queue_review_panel);
	}

	frappe.document_queue_review.render_panel(frm, context);
};

frappe.document_queue_review.teardown = function (frm) {
	const $layout = frm.$wrapper.find(".form-layout").first();
	$layout.closest(".std-form-layout").removeClass("document-queue-review-layout");
	frm.document_queue_review_panel?.remove();
	frm.document_queue_review_panel = null;
};

frappe.document_queue_review.render_panel = function (frm, context) {
	const active_tab = frm.document_queue_review_active_tab || "preview";
	const source_file_url = context.source_file_url || context.source_file || "";
	const file_name = frappe.document_queue_review.get_file_name(source_file_url);
	const preview_type = frappe.document_queue_review.get_preview_type(source_file_url);
	const open_sections = frm.document_queue_review_open_sections || { text: true };
	const text_icon = frappe.utils.icon(
		open_sections.text ? "es-line-down" : "chevron-right",
		"sm",
		"mb-1"
	);

	frm.document_queue_review_panel.html(`
		<div class="document-queue-review-shell">
			<div class="form-tabs-list document-queue-review-tabs">
				<ul class="nav form-tabs" role="tablist" style="display: flex; justify-content: flex-start; width: 100%;">
					<li class="nav-item" style="flex: 0 0 auto !important; width: auto !important;">
						<button class="nav-link ${
							active_tab === "preview" ? "active" : ""
						}" data-tab="preview" type="button" role="tab" style="display: inline-flex !important; flex: none !important; width: auto !important;">
							${__("Preview")}
						</button>
					</li>
					<li class="nav-item" style="flex: 0 0 auto !important; width: auto !important;">
						<button class="nav-link ${
							active_tab === "extraction" ? "active" : ""
						}" data-tab="extraction" type="button" role="tab" style="display: inline-flex !important; flex: none !important; width: auto !important;">
							${__("Extraction")}
						</button>
					</li>
				</ul>
			</div>
			<div class="document-queue-review-body">
				<section class="document-queue-review-tab-panel ${
					active_tab === "preview" ? "active" : ""
				}" data-panel="preview">
					<div class="document-queue-review-resize-overlay">${__("Resizing preview...")}</div>
					${frappe.document_queue_review.get_preview_markup(source_file_url, file_name)}
				</section>
				<section class="document-queue-review-tab-panel ${
					active_tab === "extraction" ? "active" : ""
				}" data-panel="extraction">
					<div class="document-queue-review-sections">
						<div class="form-section document-queue-review-section">
							<div class="section-head collapsible document-queue-review-section-head ${
								open_sections.text ? "" : "collapsed"
							}" data-section="text" tabindex="0">
								${__("Extracted Text")}
								<span class="collapse-indicator" tabindex="0">${text_icon}</span>
							</div>
							<div class="section-body ${open_sections.text ? "" : "hide"}">
								<pre>${frappe.utils.escape_html(context.extracted_text || "")}</pre>
							</div>
						</div>
					</div>
				</section>
			</div>
		</div>
		<div class="document-queue-review-resizer" title="${__("Resize")}"></div>
	`);
	frm.document_queue_review_preview_type = preview_type;

	frm.document_queue_review_panel.off("click.document-queue-review");
	frm.document_queue_review_panel.on(
		"click.document-queue-review",
		".document-queue-review-tabs .nav-link",
		function () {
			frm.document_queue_review_active_tab = $(this).attr("data-tab") || "preview";
			frappe.document_queue_review.render_panel(frm, context);
		}
	);
	frm.document_queue_review_panel.on(
		"click.document-queue-review",
		".document-queue-review-section-head",
		function () {
			const section = $(this).attr("data-section");
			frm.document_queue_review_open_sections = {
				text: Boolean(open_sections.text),
				[section]: !open_sections[section],
			};
			frappe.document_queue_review.render_panel(frm, context);
		}
	);
	frm.document_queue_review_panel.on(
		"keydown.document-queue-review",
		".document-queue-review-section-head",
		function (event) {
			if (event.key === "Enter" || event.key === " ") {
				event.preventDefault();
				$(this).trigger("click");
			}
		}
	);
	frappe.document_queue_review.bind_resizer(frm);
};

frappe.document_queue_review.apply_saved_width = function ($layout) {
	const saved_width = frappe.document_queue_review.get_stored_preview_width();
	$layout.css("--document-queue-review-width", `${saved_width}%`);
};

frappe.document_queue_review.bind_resizer = function (frm) {
	frm.document_queue_review_panel.off("mousedown.document-queue-review-resizer");
	frm.document_queue_review_panel.on(
		"mousedown.document-queue-review-resizer",
		".document-queue-review-resizer",
		function (event) {
			event.preventDefault();

			const $layout = frm.document_queue_review_panel.closest(
				".document-queue-review-layout"
			);
			if (!$layout.length) {
				return;
			}

			$("body").addClass("document-queue-review-is-resizing");
			if (frm.document_queue_review_preview_type === "pdf") {
				frm.document_queue_review_panel.addClass("document-queue-review-resizing-pdf");
			}

			$(document)
				.on("mousemove.document-queue-review-resizer", function (move_event) {
					frappe.document_queue_review.resize_preview($layout, move_event);
				})
				.on("mouseup.document-queue-review-resizer", function () {
					const width = frappe.document_queue_review.get_current_preview_width($layout);
					frappe.document_queue_review.save_preview_width(width);
					$("body").removeClass("document-queue-review-is-resizing");
					frm.document_queue_review_panel.removeClass(
						"document-queue-review-resizing-pdf"
					);
					$(document).off(".document-queue-review-resizer");
				});
		}
	);
};

frappe.document_queue_review.resize_preview = function ($layout, event) {
	const layout = $layout.get(0);
	if (!layout) {
		return;
	}

	const layout_rect = layout.getBoundingClientRect();
	const width = ((event.clientX - layout_rect.left) / layout_rect.width) * 100;
	frappe.document_queue_review.set_preview_width($layout, width);
};

frappe.document_queue_review.set_preview_width = function ($layout, width) {
	const preview_width = frappe.document_queue_review.clamp_preview_width(width);
	$layout.css("--document-queue-review-width", `${preview_width}%`);
};

frappe.document_queue_review.get_current_preview_width = function ($layout) {
	const value = (
		$layout.get(0)?.style.getPropertyValue("--document-queue-review-width") || ""
	).trim();
	return frappe.document_queue_review.clamp_preview_width(Number(value.replace("%", "")));
};

frappe.document_queue_review.clamp_preview_width = function (width) {
	const min_preview_width = 25;
	const max_preview_width = 60;
	return Math.min(
		Math.max(
			Number(width) || frappe.document_queue_review.default_preview_width,
			min_preview_width
		),
		max_preview_width
	);
};

frappe.document_queue_review.get_stored_preview_width = function () {
	try {
		const stored_width = Number(
			localStorage.getItem(frappe.document_queue_review.width_storage_key)
		);
		return frappe.document_queue_review.clamp_preview_width(
			stored_width || frappe.document_queue_review.default_preview_width
		);
	} catch {
		return frappe.document_queue_review.default_preview_width;
	}
};

frappe.document_queue_review.save_preview_width = function (width) {
	try {
		localStorage.setItem(
			frappe.document_queue_review.width_storage_key,
			frappe.document_queue_review.clamp_preview_width(width)
		);
	} catch {
		// localStorage can be unavailable in restricted browser contexts.
	}
};

frappe.document_queue_review.get_preview_markup = function (file_url, file_name) {
	if (!file_url) {
		return `<div class="document-queue-review-empty">${__("No source file available.")}</div>`;
	}

	const preview_url = frappe.document_queue_review.get_preview_url(file_url);
	const escaped_url = frappe.utils.escape_html(preview_url);
	const escaped_name = frappe.utils.escape_html(file_name || "");
	const lower = file_url.toLowerCase().split("?", 1)[0];

	if (lower.endsWith(".pdf")) {
		return `<iframe class="document-queue-review-preview" src="${escaped_url}" title="${escaped_name}"></iframe>`;
	}

	if ([".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"].some((ext) => lower.endsWith(ext))) {
		return `<img class="document-queue-review-preview-image" src="${escaped_url}" alt="${escaped_name}">`;
	}

	return `<a class="btn btn-default btn-sm" href="${escaped_url}" target="_blank" rel="noopener noreferrer">${__(
		"Open Source File"
	)}</a>`;
};

frappe.document_queue_review.get_preview_type = function (file_url) {
	const lower = (file_url || "").toLowerCase().split("?", 1)[0];
	if (lower.endsWith(".pdf")) {
		return "pdf";
	}

	if ([".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"].some((ext) => lower.endsWith(ext))) {
		return "image";
	}

	return "unsupported";
};

frappe.document_queue_review.get_preview_url = function (file_url) {
	if (!file_url || file_url.startsWith("http://") || file_url.startsWith("https://")) {
		return file_url;
	}

	return encodeURI(file_url);
};

frappe.document_queue_review.get_file_name = function (file_url) {
	if (!file_url) {
		return "";
	}
	const clean = file_url.split("?", 1)[0];
	return decodeURIComponent(clean.split("/").pop() || clean);
};

frappe.document_queue_review.link_after_save = function (frm) {
	const queue_name =
		frm.doc.__document_queue_name ||
		frm.document_queue_review_context?.queue_name ||
		frm.doc.__document_queue_review_context?.queue_name;

	if (!queue_name || !frm.doc.name || frm.doc.__document_queue_linked) {
		return Promise.resolve();
	}

	frm.doc.__document_queue_linked = 1;
	return frappe.call({
		method: "frappe.core.doctype.document_queue.document_queue.link_to_document",
		args: {
			document_queue: queue_name,
			document_type: frm.doctype,
			document_name: frm.doc.name,
		},
		callback(r) {
			const context = frappe.document_queue_review.get_context(frm) || {};
			frm.document_queue_review_context = {
				...context,
				status: r.message?.status || "Completed",
				created_document: frm.doc.name,
			};
			frm.doc.__document_queue_review_context = frm.document_queue_review_context;
			delete frm.doc.__document_queue_name;
			delete frm.doc.__document_queue_review_context;
			frm.document_queue_review_context = null;
			frm.sidebar?.reload_docinfo?.();
			frappe.document_queue_review.teardown(frm);
		},
		error() {
			frm.doc.__document_queue_linked = 0;
		},
	});
};

frappe.document_queue_review.setup_list_banner = async function (listview) {
	if (!listview?.doctype || !listview?.$page) {
		return;
	}

	listview.$page.find(".document-queue-ready-banner").remove();

	const enabled = await frappe.document_queue_review.is_upload_first_enabled(listview.doctype);
	if (!enabled) {
		return;
	}

	const count = await frappe.document_queue_review.get_ready_for_review_count(listview.doctype);
	if (!count) {
		return;
	}

	frappe.document_queue_review.add_styles();

	const message = __("{0} Documents ready for review", [count]);
	const $banner = $(`
		<div class="document-queue-ready-banner">
			<span>${frappe.utils.escape_html(message)}</span>
			<button class="btn btn-xs btn-default" type="button">${__("View")}</button>
		</div>
	`);

	$banner.find("button").on("click", () => {
		frappe.set_route("List", "Document Queue", {
			document_type: ["=", listview.doctype],
			status: ["=", "Ready for Review"],
		});
	});

	listview.$page.find(".layout-main-section").first().prepend($banner);
};

frappe.document_queue_review.get_ready_for_review_count = function (doctype) {
	return frappe
		.call({
			method: "frappe.core.doctype.document_queue.document_queue.get_ready_for_review_count",
			args: { document_type: doctype },
		})
		.then((r) => cint(r.message) || 0)
		.catch(() => 0);
};

frappe.document_queue_review.refresh_form = function (frm) {
	frappe.document_queue_review.hydrate_context(frm);
	frappe.document_queue_review.mount(frm);
	frappe.document_queue_review.setup_upload_first(frm);
};

frappe.document_queue_review.patch_list_view = function () {
	if (
		frappe.document_queue_review.list_view_patched ||
		frappe.document_queue_review_loader?.list_view_patched ||
		!frappe.views?.ListView
	) {
		frappe.document_queue_review.list_view_patched = Boolean(
			frappe.document_queue_review_loader?.list_view_patched
		);
		return;
	}

	const original_after_render = frappe.views.ListView.prototype.after_render;
	frappe.views.ListView.prototype.after_render = function () {
		original_after_render.apply(this, arguments);
		frappe.document_queue_review.setup_list_banner(this);
	};

	frappe.document_queue_review.list_view_patched = true;
	if (frappe.document_queue_review_loader) {
		frappe.document_queue_review_loader.list_view_patched = true;
	}
};

frappe.document_queue_review.add_styles = function () {
	$("#document-queue-review-style").remove();

	$(`<style id="document-queue-review-style">
		.document-queue-upload-first {
			display: flex;
			align-items: center;
			justify-content: space-between;
			gap: 16px;
			padding: 12px 16px;
			border-bottom: 1px solid var(--border-color);
			background: var(--fg-color);
		}
		.document-queue-upload-first-title {
			color: var(--text-color);
			font-weight: 600;
			line-height: 1.4;
		}
		.document-queue-upload-first-description {
			color: var(--text-muted);
			font-size: var(--text-sm);
			line-height: 1.4;
		}
		.document-queue-upload-first-button {
			display: inline-flex;
			align-items: center;
			gap: 6px;
			flex: none;
		}
		.document-queue-ready-banner {
			display: flex;
			align-items: center;
			justify-content: space-between;
			gap: 12px;
			min-height: 32px;
			padding: 6px 12px;
			margin-bottom: 8px;
			border: 1px solid var(--border-color);
			border-top: 0;
			background: var(--fg-color);
			color: var(--text-muted);
			font-size: var(--text-sm);
		}
		.std-form-layout.document-queue-review-layout {
			display: grid;
			grid-template-columns:
				minmax(320px, var(--document-queue-review-width, 38%))
				minmax(0, 1fr);
			gap: 0;
			align-items: start;
		}
		.document-queue-review-panel {
			position: sticky;
			top: var(--page-head-height);
			height: calc(100vh - var(--page-head-height));
			margin-top: 0;
			overflow: visible;
			border: 1px solid var(--border-color);
			border-width: 0 1px 1px 0;
			border-radius: 0;
			background: var(--fg-color);
		}
		.document-queue-review-shell {
			display: flex;
			height: 100%;
			min-height: 0;
			overflow: hidden;
			border-radius: 0;
			flex-direction: column;
		}
		.document-queue-review-tabs {
			position: relative;
			padding: 0;
			background-color: var(--card-bg);
			border-bottom: 1px solid var(--border-color);
			border-radius: 0;
			margin-bottom: 0;
			margin-top: 0;
		}
		.document-queue-review-tabs .form-tabs {
			display: flex;
			flex-wrap: nowrap;
			align-items: center;
			justify-content: flex-start;
			overflow: overlay;
			padding: 0;
			margin: 0;
			list-style: none;
			width: 100%;
		}
		.document-queue-review-tabs .nav-item {
			flex: none !important;
			white-space: nowrap;
			width: auto !important;
			max-width: max-content;
		}
		.document-queue-review-tabs .nav-link {
			display: inline-flex !important;
			align-items: center;
			gap: 6px;
			flex: none !important;
			width: auto !important;
			min-width: 0;
			padding: 10px 0;
			margin: 0 var(--margin-md);
			border: 0;
			border-bottom: 1px solid transparent;
			border-radius: 0;
			background-color: var(--card-bg);
			color: var(--text-light);
			font-size: var(--text-base);
			font-weight: 400;
			line-height: 1.4;
			text-align: left;
		}
		.document-queue-review-tabs .nav-link.active {
			padding-bottom: 9px;
			border-bottom-color: var(--text-color);
			color: var(--text-neutral);
			font-weight: 400;
		}
		.document-queue-review-tabs .nav-link:focus-visible {
			outline: none;
			font-weight: 600;
		}
		.document-queue-review-body {
			min-height: 0;
			flex: 1;
			overflow: auto;
			padding: 12px;
			margin-top: 0;
			border-bottom: 1px solid var(--border-color);
		}
		.document-queue-review-tab-panel {
			display: none;
			height: 100%;
		}
		.document-queue-review-tab-panel.active {
			display: block;
		}
		.document-queue-review-tab-panel[data-panel="preview"] {
			position: relative;
		}
		.document-queue-review-resize-overlay {
			position: absolute;
			display: none;
			top: 50%;
			left: 50%;
			transform: translate(-50%, -50%);
			color: var(--text-muted);
			font-size: var(--text-base);
			font-weight: 400;
			pointer-events: none;
			z-index: 1;
		}
		.document-queue-review-preview {
			width: 100%;
			height: 100%;
			border: 0;
			border-radius: 0;
			background: #fff;
		}
		.document-queue-review-preview-image {
			width: 100%;
			height: auto;
			border-radius: 0;
		}
		.document-queue-review-panel.document-queue-review-resizing-pdf .document-queue-review-preview {
			visibility: hidden;
		}
		.document-queue-review-panel.document-queue-review-resizing-pdf .document-queue-review-resize-overlay {
			display: block;
		}
		.document-queue-review-sections {
			display: flex;
			flex-direction: column;
		}
		.document-queue-review-section {
			padding: 0;
			border: 0;
			background: var(--fg-color);
		}
		.document-queue-review-section .section-head,
		.document-queue-review-section .section-body {
			max-width: none !important;
			margin: auto !important;
		}
		.document-queue-review-section .section-head {
			display: flex;
			align-items: center;
			justify-content: space-between;
			padding: var(--padding-md);
			border-bottom: 0;
			color: var(--text-color);
			font-size: var(--text-md);
			font-weight: var(--weight-medium);
		}
		.document-queue-review-section .collapse-indicator {
			margin-left: auto;
		}
		.document-queue-review-section .section-body {
			display: block;
			padding: var(--padding-sm) var(--padding-md) 0;
		}
		.document-queue-review-section .section-body.hide {
			display: none;
		}
		.document-queue-review-panel pre {
			margin: 0;
			white-space: pre-wrap;
			word-break: break-word;
			padding: var(--padding-md);
			border-radius: 0;
			border: 0;
			background: var(--control-bg);
			font-size: var(--text-sm);
		}
		.document-queue-review-resizer {
			position: absolute;
			top: 0;
			right: -2px;
			bottom: 0;
			width: 5px;
			cursor: col-resize;
			z-index: 2;
			background: transparent;
			transition: background-color 120ms ease;
		}
		.document-queue-review-resizer:hover {
			background: color-mix(in srgb, var(--gray-400) 55%, transparent);
		}
		body.document-queue-review-is-resizing {
			cursor: col-resize;
			user-select: none;
		}
		@media (max-width: 991px) {
			.std-form-layout.document-queue-review-layout {
				display: block;
			}
			.document-queue-review-panel {
				position: static;
				height: calc(100vh - 96px);
				margin-bottom: 16px;
			}
			.document-queue-review-resizer {
				display: none;
			}
		}
	</style>`).appendTo(document.head);
};

$(document).on("form-refresh", function (event, frm) {
	frappe.document_queue_review.hydrate_context(frm);
	frappe.document_queue_review.mount(frm);
	frappe.document_queue_review.setup_upload_first(frm);
});

frappe.document_queue_review.patch_list_view();

frappe.router?.on("change", () => {
	frappe.document_queue_review.patch_list_view();
});

frappe.ui.form.on("*", {
	after_save(frm) {
		return frappe.document_queue_review.link_after_save(frm);
	},

	on_submit(frm) {
		return frappe.document_queue_review.link_after_save(frm);
	},
});
