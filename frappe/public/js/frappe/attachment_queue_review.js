frappe.provide("frappe.attachment_queue_review");

frappe.attachment_queue_review.width_storage_key = "frappe.attachment_queue_review.preview_width";
frappe.attachment_queue_review.default_preview_width = 38;
frappe.attachment_queue_review.reviewable_statuses = ["Ready for Review", "Failed"];
frappe.attachment_queue_review.image_extensions = [
	".png",
	".jpg",
	".jpeg",
	".webp",
	".gif",
	".bmp",
];

frappe.attachment_queue_review.start_from_attachment_queue = async function (frm) {
	if (!frappe.attachment_queue_review.reviewable_statuses.includes(frm.doc.status)) {
		frappe.msgprint(__("Only documents that are ready for review can be reviewed."));
		return;
	}

	let document_type = frm.doc.document_type;

	if (!document_type) {
		document_type = await frappe.attachment_queue_review.prompt_document_type();
		if (!document_type) {
			return;
		}

		await frm.call("set_document_type", { document_type });
		await frm.reload_doc();
	}

	const context = await frappe.attachment_queue_review.fetch_context(frm.doc.name);
	if (!frappe.attachment_queue_review.reviewable_statuses.includes(context?.status)) {
		frappe.msgprint(__("Only documents that are ready for review can be reviewed."));
		return;
	}

	if (!context?.document_type) {
		frappe.msgprint(__("Select a target DocType before starting review."));
		return;
	}

	frappe.attachment_queue_review.route_to_new_document(context);
};

frappe.attachment_queue_review.prompt_document_type = function () {
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

frappe.attachment_queue_review.fetch_context = function (attachment_queue) {
	return frappe
		.call({
			method: "frappe.core.doctype.attachment_queue.attachment_queue.get_document_review_context",
			args: { attachment_queue },
		})
		.then((r) => r.message || null);
};

// frappe.utils covers reading query params (get_query_params) but the framework
// has no setter, so these two own the write side for the whole feature. Both
// skip a no-op replaceState, which only some of the former call sites did.
frappe.attachment_queue_review.set_query_param = function (name, value) {
	const url = new URL(window.location.href);
	if (url.searchParams.get(name) === String(value)) {
		return;
	}

	url.searchParams.set(name, value);
	window.history.replaceState(window.history.state, "", url.toString());
};

frappe.attachment_queue_review.clear_query_param = function (name) {
	const url = new URL(window.location.href);
	if (!url.searchParams.has(name)) {
		return;
	}

	url.searchParams.delete(name);
	window.history.replaceState(window.history.state, "", url.toString());
};

// Single owner of "open a new document for this queue context": load the target
// doctype's meta, create the unsaved doc, hand the context over in memory, route
// to it, then stamp ?attachment_queue= so hydrate_context can recover after a
// reload. Three call sites carried their own copy of this block — the two below
// and attachment_queue_review_modal.js's _start_review.
frappe.attachment_queue_review.route_to_new_document = function (context) {
	return new Promise((resolve) => {
		frappe.model.with_doctype(context.document_type, () => {
			const doc = frappe.model.get_new_doc(context.document_type);
			frappe.attachment_queue_review.pending_context = context;
			frappe.set_route("Form", context.document_type, doc.name).then(() => {
				frappe.attachment_queue_review.set_query_param(
					"attachment_queue",
					context.queue_name
				);
				resolve();
			});
		});
	});
};

frappe.attachment_queue_review.setup_upload_first = async function (frm) {
	frappe.attachment_queue_review.remove_upload_first(frm);

	if (
		!frm?.is_new?.() ||
		frm.in_dialog ||
		!frm.page ||
		frappe.attachment_queue_review.get_context(frm)
	) {
		return;
	}

	// The loader owns this gate — it ships in form.bundle.js, so it is always
	// present, and list_view.js already calls the same copy.
	const enabled = await frappe.attachment_queue_review_loader.is_upload_first_enabled(
		frm.doctype
	);
	if (!enabled || frappe.attachment_queue_review.get_context(frm)) {
		return;
	}

	const $page = frm.page.wrapper.find(".page-body");
	$page.find(".attachment-queue-upload-first").remove();

	const $banner = $(`
		<div class="attachment-queue-upload-first">
			<div>
				<div class="attachment-queue-upload-first-title">${__("Upload Document")}</div>
				<div class="attachment-queue-upload-first-description">
					${__("Upload one PDF or image before creating a draft.")}
				</div>
			</div>
			<button class="btn btn-default btn-sm attachment-queue-upload-first-button" type="button">
				${frappe.utils.icon("upload", "sm")}
				<span>${__("Upload")}</span>
			</button>
		</div>
	`);

	$banner.find(".attachment-queue-upload-first-button").on("click", () => {
		frappe.attachment_queue_review.open_upload_first_dialog(frm);
	});

	$page.prepend($banner);
	frm.attachment_queue_upload_first_banner = $banner;
};

frappe.attachment_queue_review.remove_upload_first = function (frm) {
	frm?.attachment_queue_upload_first_banner?.remove();
	frm.attachment_queue_upload_first_banner = null;
	frm?.$wrapper?.find(".attachment-queue-upload-first").remove();
	frm?.page?.wrapper?.find(".attachment-queue-upload-first").remove();
};

frappe.attachment_queue_review.open_upload_first_dialog = async function (frm) {
	await frappe.require("file_uploader.bundle.js");

	new frappe.ui.FileUploader({
		allow_multiple: false,
		allow_web_link: false,
		// Only what the preview pane below can actually render — the reviewer keys the
		// document in from that preview, so accepting a format it cannot show (TIFF,
		// which no browser previews) would strand the upload at review time.
		restrictions: {
			allowed_file_types: [".pdf", ...frappe.attachment_queue_review.image_extensions],
		},
		dialog_title: __("Upload Source Document"),
		on_success(file_doc) {
			if (!file_doc?.name) {
				frappe.msgprint(__("Could not create a file from the upload."));
				return;
			}

			frappe.attachment_queue_review.create_upload_first_queue(frm, file_doc.name);
		},
	});
};

frappe.attachment_queue_review.create_upload_first_queue = async function (frm, file_name) {
	frappe.dom.freeze(
		`<div class="attachment-queue-freeze-body"><div class="es-spinner"></div><div>${__(
			"Extracting document..."
		)}</div></div>`
	);
	try {
		const r = await frappe.call({
			method: "frappe.core.doctype.attachment_queue.attachment_queue.create_upload_first_queue",
			args: {
				file_name,
				document_type: frm.doctype,
			},
		});

		let context = r.message;
		if (!context?.queue_name) {
			frappe.msgprint(__("Could not create an Attachment Queue record."));
			return;
		}

		context = await frappe.attachment_queue_review.wait_for_extraction(context);

		if (context.status === "Failed") {
			frappe.msgprint({
				title: __("Extraction Failed"),
				message: __(
					"The document was queued, but extraction failed. You can still review it from Attachment Queue."
				),
				indicator: "red",
			});
		} else if (context.status === "Ready for Review") {
			frappe.show_alert({
				message: __("Extraction Completed"),
				indicator: "green",
			});
		}

		// Awaited so the freeze in `finally` only lifts once the new form is up.
		await frappe.attachment_queue_review.route_to_new_document(context);
	} catch (error) {
		// frappe.call reports HTTP-level failures itself, but a request that never gets
		// a response (connection dropped mid-upload) matches none of its statusCode
		// handlers — without this the freeze would just lift and say nothing, and the
		// rejection would escape unhandled through FileUploader's on_success.
		if (!error?.status) {
			frappe.msgprint({
				title: __("Upload Failed"),
				message: __(
					"Could not reach the server. Please check your connection and try again."
				),
				indicator: "red",
			});
		}
		console.error("Attachment Queue: upload-first flow failed", error);
	} finally {
		frappe.dom.unfreeze();
	}
};

frappe.attachment_queue_review.wait_for_extraction = async function (context) {
	if (!["Queued", "Processing"].includes(context.status)) {
		return context;
	}

	let latest_context = context;
	let listener;
	let timeout;
	let fallback_interval;
	let is_resolving = false;

	const fetch_context = async () => {
		const result = await frappe.attachment_queue_review.fetch_context(context.queue_name);
		latest_context = result || latest_context;
		return latest_context;
	};

	// Single owner of teardown, so the timer, the interval and the realtime
	// listener are released on every settle path — resolve *and* reject.
	const cleanup = () => {
		clearTimeout(timeout);
		clearInterval(fallback_interval);
		if (listener) {
			frappe.realtime.off("task_update", listener);
		}
	};

	try {
		return await new Promise((resolve, reject) => {
			timeout = setTimeout(() => {
				if (is_resolving) return;
				is_resolving = true;
				frappe.msgprint({
					title: __("Extraction Still Running"),
					message: __(
						"The document was queued, but extraction is taking longer than expected. You can continue reviewing it from Attachment Queue when extraction finishes."
					),
					indicator: "orange",
				});
				fetch_context().then(resolve).catch(reject);
			}, 90000);

			fallback_interval = setInterval(() => {
				if (is_resolving) return;
				if (frappe.realtime?.socket?.connected) return;

				fetch_context()
					.then((ctx) => {
						if (is_resolving) return;
						if (["Ready for Review", "Failed"].includes(ctx.status)) {
							is_resolving = true;
							resolve(ctx);
						}
					})
					.catch(() => {});
			}, 3000);

			listener = (data) => {
				if (is_resolving) return;
				if (
					data.task_id === context.task_id &&
					["Ready for Review", "Failed"].includes(data.status)
				) {
					is_resolving = true;
					fetch_context().then(resolve).catch(reject);
				}
			};

			frappe.realtime.on("task_update", listener);

			// Immediate state fetch to close the fast-completion race condition
			fetch_context()
				.then((ctx) => {
					if (is_resolving) return;
					if (!["Queued", "Processing"].includes(ctx.status)) {
						is_resolving = true;
						resolve(ctx);
					}
				})
				.catch(reject);
		});
	} finally {
		cleanup();
	}
};

frappe.attachment_queue_review.get_context = function (frm) {
	return frm.doc.__attachment_queue_review_context || null;
};

// Neither obvious carrier survives a save: frappe.model.sync replaces frm.doc for
// a new document, and rename_notify re-routes to the saved name, which drops
// ?attachment_queue= from the URL. frm itself survives both, so before_save copies
// the context onto it and link_after_save reads it back from there.
frappe.attachment_queue_review.get_pending_link = function (frm) {
	const context = frappe.attachment_queue_review.get_context(frm);
	if (!context?.queue_name || !context.document_type) {
		return null;
	}

	return { queue_name: context.queue_name, document_type: context.document_type };
};

frappe.attachment_queue_review.hydrate_context = async function (frm) {
	if (frappe.attachment_queue_review.get_context(frm)) {
		return;
	}

	let context = frappe.attachment_queue_review.pending_context;
	if (context) {
		frappe.attachment_queue_review.pending_context = null;
	}

	if (!context?.queue_name) {
		const queryParams = frappe.utils.get_query_params();
		let queueName =
			queryParams.attachment_queue ||
			frappe.attachment_queue_review_loader.surviving_queue_name;
		if (queueName) {
			frappe.attachment_queue_review_loader.surviving_queue_name = null;
			context = await frappe.attachment_queue_review.fetch_context(queueName);
		}
	}

	if (!context?.queue_name || context.document_type !== frm.doctype) {
		return;
	}

	frm.doc.__attachment_queue_review_context = context;
	frm.doc.__attachment_queue_name = context.queue_name;

	frappe.attachment_queue_review.set_query_param("attachment_queue", context.queue_name);
};

frappe.attachment_queue_review.mount = function (frm) {
	const context = frappe.attachment_queue_review.get_context(frm);
	if (!context?.queue_name) {
		frappe.attachment_queue_review.teardown(frm);
		return;
	}

	const $layout = frm.$wrapper.find(".form-layout").first();
	if (!$layout.length) {
		return;
	}

	frappe.attachment_queue_review.remove_upload_first(frm);
	const $std = $layout.closest(".std-form-layout");
	$std.addClass("attachment-queue-review-layout");
	frappe.attachment_queue_review.apply_saved_width($std);

	if (!frm.attachment_queue_review_panel) {
		frm.attachment_queue_review_panel = $(
			`<aside class="attachment-queue-review-panel"></aside>`
		);
		$std.length
			? $std.prepend(frm.attachment_queue_review_panel)
			: $layout.before(frm.attachment_queue_review_panel);
	}

	frappe.attachment_queue_review.render_panel(frm, context);
};

frappe.attachment_queue_review.teardown = function (frm) {
	const $layout = frm.$wrapper.find(".form-layout").first();
	$layout.closest(".std-form-layout").removeClass("attachment-queue-review-layout");
	frm.attachment_queue_review_resizer_tooltip?.destroy();
	frm.attachment_queue_review_resizer_tooltip = null;
	frm.attachment_queue_review_panel?.remove();
	frm.attachment_queue_review_panel = null;
};

frappe.attachment_queue_review.render_panel = function (frm, context) {
	const dev_mode = cint(frappe.boot.developer_mode);
	let active_tab = frm.attachment_queue_review_active_tab || "preview";
	if (!dev_mode && active_tab === "extraction") {
		active_tab = "preview";
	}
	const source_file_url = context.source_file_url || context.source_file || "";
	const file_name = frappe.attachment_queue_review.get_file_name(source_file_url);
	const preview_type = frappe.attachment_queue_review.get_preview_type(source_file_url);
	const open_sections = frm.attachment_queue_review_open_sections || { text: true, json: false };
	const text_icon = frappe.utils.icon(
		open_sections.text ? "es-line-down" : "chevron-right",
		"sm",
		"mb-1"
	);
	const json_icon = frappe.utils.icon(
		open_sections.json ? "es-line-down" : "chevron-right",
		"sm",
		"mb-1"
	);

	let error_alert = "";
	if (context.status === "Failed" && context.error_message) {
		// Rendered in the panel shell, above the tabs, rather than inside a tab: why
		// extraction failed is a state of the whole record, and the only other tab that
		// could host it is the developer-mode one, which most reviewers never see.
		// Markup form (`.html`) because the panel is assembled as one HTML string below.
		// It escapes title and description itself.
		error_alert = frappe.ui.alert.html({
			title: __("Extraction Failed"),
			description: context.error_message,
			theme: "red",
		});
	}

	let raw_json_html = "";
	if (context.raw_extraction_json) {
		try {
			let parsed =
				typeof context.raw_extraction_json === "string"
					? JSON.parse(context.raw_extraction_json)
					: context.raw_extraction_json;
			let formatted = JSON.stringify(parsed, null, 4);
			raw_json_html = `
				<div class="form-section attachment-queue-review-section">
					<div class="section-head collapsible attachment-queue-review-section-head ${
						open_sections.json ? "" : "collapsed"
					}" data-section="json" tabindex="0">
						${__("Raw Extraction JSON")}
						<span class="collapse-indicator" tabindex="0">${json_icon}</span>
					</div>
					<div class="section-body ${open_sections.json ? "" : "hide"}">
						<pre class="attachment-queue-review-json-pre">${frappe.utils.escape_html(formatted)}</pre>
					</div>
				</div>
			`;
		} catch {
			// ignore JSON parse errors
		}
	}

	let debug_tab_button = "";
	let debug_tab_panel = "";

	if (dev_mode) {
		debug_tab_button = `
					<li class="nav-item">
						<button class="nav-link ${
							active_tab === "extraction" ? "active" : ""
						}" data-tab="extraction" type="button" role="tab">
							${__("Debug")}
						</button>
					</li>
		`;
		debug_tab_panel = `
				<section class="attachment-queue-review-tab-panel ${
					active_tab === "extraction" ? "active" : ""
				}" data-panel="extraction">
					<div class="attachment-queue-review-sections">
						<div class="form-section attachment-queue-review-section">
							<div class="section-head collapsible attachment-queue-review-section-head ${
								open_sections.text ? "" : "collapsed"
							}" data-section="text" tabindex="0">
								${__("Extracted Text")}
								<span class="collapse-indicator" tabindex="0">${text_icon}</span>
							</div>
							<div class="section-body ${open_sections.text ? "" : "hide"}">
								<pre>${frappe.utils.escape_html(context.extracted_text || "")}</pre>
							</div>
						</div>
						${raw_json_html}
					</div>
				</section>
		`;
	}

	frm.attachment_queue_review_panel.html(`
		<div class="attachment-queue-review-shell">
			${error_alert ? `<div class="attachment-queue-review-alert">${error_alert}</div>` : ""}
			<div class="form-tabs-list">
				<ul class="nav form-tabs" role="tablist">
					<li class="nav-item">
						<button class="nav-link ${
							active_tab === "preview" ? "active" : ""
						}" data-tab="preview" type="button" role="tab">
							${__("Preview")}
						</button>
					</li>
${debug_tab_button}
				</ul>
			</div>
			<div class="attachment-queue-review-body">
				<section class="attachment-queue-review-tab-panel ${
					active_tab === "preview" ? "active" : ""
				}" data-panel="preview">
					<div class="attachment-queue-review-resize-overlay">${__("Resizing preview...")}</div>
					${frappe.attachment_queue_review.get_preview_markup(source_file_url, file_name)}
				</section>
${debug_tab_panel}
			</div>
		</div>
		<div class="attachment-queue-review-resizer"></div>
	`);
	frm.attachment_queue_review_preview_type = preview_type;

	frm.attachment_queue_review_panel.off("click.attachment-queue-review");
	frm.attachment_queue_review_panel.on(
		"click.attachment-queue-review",
		".form-tabs-list .nav-link",
		function () {
			frm.attachment_queue_review_active_tab = $(this).attr("data-tab") || "preview";
			frappe.attachment_queue_review.render_panel(frm, context);
		}
	);
	frm.attachment_queue_review_panel.on(
		"click.attachment-queue-review",
		".attachment-queue-review-section-head",
		function () {
			const section = $(this).attr("data-section");
			frm.attachment_queue_review_open_sections = {
				...open_sections,
				[section]: !open_sections[section],
			};
			frappe.attachment_queue_review.render_panel(frm, context);
		}
	);
	frm.attachment_queue_review_panel.on(
		"keydown.attachment-queue-review",
		".attachment-queue-review-section-head",
		function (event) {
			if (event.key === "Enter" || event.key === " ") {
				event.preventDefault();
				$(this).trigger("click");
			}
		}
	);
	frappe.attachment_queue_review.bind_resizer(frm);
};

frappe.attachment_queue_review.apply_saved_width = function ($layout) {
	const saved_width = frappe.attachment_queue_review.get_stored_preview_width();
	$layout.css("--attachment-queue-review-width", `${saved_width}%`);
};

frappe.attachment_queue_review.bind_resizer = function (frm) {
	// Espresso tooltip instead of a native `title`, matching the tooltips used
	// elsewhere in desk. render_panel() rebuilds the panel wholesale, so the
	// handle is a new element on every render: destroy the previous instance
	// first, or its bubble (which lives on <body>) can outlive its trigger.
	frm.attachment_queue_review_resizer_tooltip?.destroy();
	frm.attachment_queue_review_resizer_tooltip = new frappe.ui.Tooltip(
		frm.attachment_queue_review_panel.find(".attachment-queue-review-resizer"),
		{ text: __("Resize") }
	);

	frm.attachment_queue_review_panel.off("mousedown.attachment-queue-review-resizer");
	frm.attachment_queue_review_panel.on(
		"mousedown.attachment-queue-review-resizer",
		".attachment-queue-review-resizer",
		function (event) {
			event.preventDefault();

			const $layout = frm.attachment_queue_review_panel.closest(
				".attachment-queue-review-layout"
			);
			if (!$layout.length) {
				return;
			}

			$("body").addClass("attachment-queue-review-is-resizing");
			if (frm.attachment_queue_review_preview_type === "pdf") {
				frm.attachment_queue_review_panel.addClass("attachment-queue-review-resizing-pdf");
			}

			// One width update per animation frame (~16ms at 60Hz) — the display
			// cannot show more than that. Created per drag so the throttle window
			// never carries over from a previous drag.
			let is_resizing = true;
			let has_moved = false;
			const throttled_resize = frappe.utils.throttle(function (move_event) {
				// frappe.utils.throttle has no cancel(), so a trailing call can land
				// after mouseup has already persisted the width; ignore it.
				if (!is_resizing) {
					return;
				}
				frappe.attachment_queue_review.resize_preview($layout, move_event);
			}, 16);

			$(document)
				.on("mousemove.attachment-queue-review-resizer", function (move_event) {
					has_moved = true;
					throttled_resize(move_event);
				})
				.on("mouseup.attachment-queue-review-resizer", function (up_event) {
					is_resizing = false;
					if (has_moved) {
						// Apply the release position un-throttled, so the width that
						// gets persisted is the one actually under the cursor even if
						// the last frame was throttled away.
						frappe.attachment_queue_review.resize_preview($layout, up_event);
					}

					const width =
						frappe.attachment_queue_review.get_current_preview_width($layout);
					frappe.attachment_queue_review.save_preview_width(width);
					$("body").removeClass("attachment-queue-review-is-resizing");
					frm.attachment_queue_review_panel.removeClass(
						"attachment-queue-review-resizing-pdf"
					);
					$(document).off(".attachment-queue-review-resizer");
				});
		}
	);
};

frappe.attachment_queue_review.resize_preview = function ($layout, event) {
	const layout = $layout.get(0);
	if (!layout) {
		return;
	}

	const layout_rect = layout.getBoundingClientRect();
	const width = ((event.clientX - layout_rect.left) / layout_rect.width) * 100;
	frappe.attachment_queue_review.set_preview_width($layout, width);
};

frappe.attachment_queue_review.set_preview_width = function ($layout, width) {
	const preview_width = frappe.attachment_queue_review.clamp_preview_width(width);
	$layout.css("--attachment-queue-review-width", `${preview_width}%`);
};

frappe.attachment_queue_review.get_current_preview_width = function ($layout) {
	const value = (
		$layout.get(0)?.style.getPropertyValue("--attachment-queue-review-width") || ""
	).trim();
	return frappe.attachment_queue_review.clamp_preview_width(Number(value.replace("%", "")));
};

frappe.attachment_queue_review.clamp_preview_width = function (width) {
	const min_preview_width = 25;
	const max_preview_width = 60;
	return Math.min(
		Math.max(
			Number(width) || frappe.attachment_queue_review.default_preview_width,
			min_preview_width
		),
		max_preview_width
	);
};

frappe.attachment_queue_review.get_stored_preview_width = function () {
	try {
		const stored_width = Number(
			localStorage.getItem(frappe.attachment_queue_review.width_storage_key)
		);
		return frappe.attachment_queue_review.clamp_preview_width(
			stored_width || frappe.attachment_queue_review.default_preview_width
		);
	} catch {
		return frappe.attachment_queue_review.default_preview_width;
	}
};

frappe.attachment_queue_review.save_preview_width = function (width) {
	try {
		localStorage.setItem(
			frappe.attachment_queue_review.width_storage_key,
			frappe.attachment_queue_review.clamp_preview_width(width)
		);
	} catch {
		// localStorage can be unavailable in restricted browser contexts.
	}
};

// The two "nothing to preview" branches use frappe.ui.empty_state — the same
// component the review modal already renders for these exact states
// (_clear_preview and the unsupported branch of _render_preview), so both halves
// of the feature show the same thing. `.html` is the markup-string form, which
// is what this function returns; it escapes title/description itself.
frappe.attachment_queue_review.get_preview_markup = function (file_url, file_name) {
	if (!file_url) {
		return frappe.ui.empty_state.html({
			icon: "file-text",
			title: __("No source file available."),
		});
	}

	const preview_url = frappe.attachment_queue_review.get_preview_url(file_url);
	const escaped_url = frappe.utils.escape_html(preview_url);
	const escaped_name = frappe.utils.escape_html(file_name || "");
	const lower = file_url.toLowerCase().split("?", 1)[0];

	if (lower.endsWith(".pdf")) {
		return `<iframe class="attachment-queue-review-preview" src="${escaped_url}" title="${escaped_name}"></iframe>`;
	}

	if (frappe.attachment_queue_review.image_extensions.some((ext) => lower.endsWith(ext))) {
		return `<img class="attachment-queue-review-preview-image" src="${escaped_url}" alt="${escaped_name}">`;
	}

	// `href` actions survive the markup-string form (an onclick could not), and
	// the component applies target/rel and refuses code-running schemes itself.
	return frappe.ui.empty_state.html({
		icon: "file-text",
		title: __("Preview Not Available"),
		description: __("This file format cannot be previewed directly."),
		actions: [
			{
				label: __("Open Source File"),
				href: preview_url,
				icon: "arrow-up-right",
				variant: "subtle",
			},
		],
	});
};

frappe.attachment_queue_review.get_preview_type = function (file_url) {
	const lower = (file_url || "").toLowerCase().split("?", 1)[0];
	if (lower.endsWith(".pdf")) {
		return "pdf";
	}

	if (frappe.attachment_queue_review.image_extensions.some((ext) => lower.endsWith(ext))) {
		return "image";
	}

	return "unsupported";
};

// Single source of truth for turning a stored `source_file` into a URL that is
// safe to use as an iframe/img src. `source_file` is an Attach value, so it is
// normally "/files/x.pdf" or "/private/files/x.pdf?fid=...", but relative values
// are normalized too. Also used by attachment_queue_review_modal.js.
frappe.attachment_queue_review.get_preview_url = function (file_url) {
	if (!file_url) {
		return "";
	}

	// Deliberately broader than frappe.utils.is_url (which is http/https only):
	// this also matches protocol-relative URLs, so a real "#fragment" on a web
	// URL is left alone while a "#" inside a file path is escaped below.
	const is_web_url = /^(https?:)?\/\//i.test(file_url);

	if (!is_web_url && !file_url.startsWith("/")) {
		file_url = file_url.startsWith("files/") ? `/${file_url}` : `/files/${file_url}`;
	}

	file_url = encodeURI(file_url);

	if (!is_web_url) {
		// encodeURI leaves "#" intact, which would truncate the path at a fragment
		file_url = file_url.replace(/#/g, "%23");
	}

	return file_url;
};

frappe.attachment_queue_review.get_file_name = function (file_url) {
	if (!file_url) {
		return "";
	}
	const clean = file_url.split("?", 1)[0];
	return decodeURIComponent(clean.split("/").pop() || clean);
};

frappe.attachment_queue_review.link_after_save = function (frm) {
	const context = frappe.attachment_queue_review.get_context(frm);
	// Consumed, not just read: after_save and on_submit both land here for a
	// submit, and only the first one should link.
	const pending = frm.__attachment_queue_pending_link;
	frm.__attachment_queue_pending_link = null;

	if (!pending || !frm.doc.name || frm.doc.__attachment_queue_linked) {
		return Promise.resolve();
	}

	// A queue row only ever produces its own target doctype, so a mismatch means
	// this form is not the document the review was started for.
	if (pending.document_type !== frm.doctype) {
		return Promise.resolve();
	}

	frm.doc.__attachment_queue_linked = 1;
	return frappe.call({
		method: "frappe.core.doctype.attachment_queue.attachment_queue.link_to_document",
		args: {
			attachment_queue: pending.queue_name,
			document_type: frm.doctype,
			document_name: frm.doc.name,
		},
		callback(r) {
			const updated_context = {
				...(context || {}),
				status: r.message?.status || "Completed",
				created_document: frm.doc.name,
			};
			frm.doc.__attachment_queue_review_context = updated_context;
			delete frm.doc.__attachment_queue_name;

			frappe.attachment_queue_review.clear_query_param("attachment_queue");

			frm.sidebar?.reload_docinfo?.();
			frappe.attachment_queue_review.teardown(frm);
		},
		error() {
			frm.doc.__attachment_queue_linked = 0;
		},
	});
};

frappe.attachment_queue_review.setup_list_banner = async function (listview) {
	if (!listview?.doctype || !listview?.$page) {
		return;
	}

	// list_view.js calls this from after_render(), which fires on every refresh —
	// filter, sort, load-more, realtime update. Without this guard two overlapping
	// refreshes each remove the banner and then each add one back.
	if (listview.attachment_queue_banner_pending) {
		return;
	}
	listview.attachment_queue_banner_pending = true;

	try {
		const enabled = await frappe.attachment_queue_review_loader.is_upload_first_enabled(
			listview.doctype
		);
		if (!enabled) {
			return;
		}

		listview.$page.find(".attachment-queue-ready-banner").remove();

		// Inject the primary "Review Pending" button that opens the modal.
		await frappe.attachment_queue_list_action?.setup(listview);
	} finally {
		listview.attachment_queue_banner_pending = false;
	}
};

frappe.attachment_queue_review.get_ready_for_review_count = function (doctype) {
	return frappe
		.call({
			method: "frappe.core.doctype.attachment_queue.attachment_queue.get_ready_for_review_count",
			args: { document_type: doctype },
		})
		.then((r) => cint(r.message) || 0)
		.catch(() => 0);
};

frappe.attachment_queue_review.refresh_form = async function (frm) {
	await frappe.attachment_queue_review.hydrate_context(frm);
	frappe.attachment_queue_review.mount(frm);
	frappe.attachment_queue_review.setup_upload_first(frm);
};
