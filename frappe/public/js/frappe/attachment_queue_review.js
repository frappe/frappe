frappe.provide("frappe.attachment_queue_review");

frappe.attachment_queue_review.width_storage_key =
	"frappe.attachment_queue_review.preview_width_px";
frappe.attachment_queue_review.default_preview_width = 480;
frappe.attachment_queue_review.min_preview_width = 320;

frappe.attachment_queue_review.max_preview_width_ratio = 0.6;
frappe.attachment_queue_review.reviewable_statuses = ["Ready for Review", "Failed"];

// Completed means the queue row has been linked to a document
frappe.attachment_queue_review.is_review_completed = function (context) {
	return context?.status === "Completed";
};

// Extraction is still running in these states.
frappe.attachment_queue_review.extraction_pending_statuses = ["Queued", "Processing"];

// Time before showing that extraction is taking longer than expected.
frappe.attachment_queue_review.extraction_slow_threshold = 90000;
frappe.attachment_queue_review.extraction_poll_interval = 3000;
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

// Set and clear query parameters without calling replaceState when nothing changes.
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

// Opens a new document and preserves the queue context in memory and the URL.
frappe.attachment_queue_review.route_to_new_document = function (context) {
	if (frappe.attachment_queue_review.is_review_completed(context)) {
		frappe.msgprint(__("This document has already been reviewed."));
		return Promise.resolve();
	}

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

	if (!frm?.is_new?.() || !frm.page || frappe.attachment_queue_review.get_context(frm)) {
		return;
	}

	// Check whether Upload First is enabled for this DocType.
	const enabled = await frappe.attachment_queue_review_loader.is_upload_first_enabled(
		frm.doctype
	);
	if (!enabled || frappe.attachment_queue_review.get_context(frm)) {
		return;
	}

	const $page = frm.page.wrapper.find(".page-body");

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
	frm.attachment_queue_upload_first_banner?.remove();
	frm.attachment_queue_upload_first_banner = null;
	frm.$wrapper?.find(".attachment-queue-upload-first").remove();
	frm.page?.wrapper?.find(".attachment-queue-upload-first").remove();
};

frappe.attachment_queue_review.open_upload_first_dialog = async function (frm) {
	await frappe.require("file_uploader.bundle.js");

	new frappe.ui.FileUploader({
		allow_multiple: false,
		allow_web_link: false,

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
	// Open the review immediately and let mount() track extraction in the background.
	try {
		const r = await frappe.call({
			method: "frappe.core.doctype.attachment_queue.attachment_queue.create_upload_first_queue",
			args: {
				file_name,
				document_type: frm.doctype,
			},
		});

		const context = r.message;
		if (!context?.queue_name) {
			frappe.msgprint(__("Could not create an Attachment Queue record."));
			return;
		}

		await frappe.attachment_queue_review.route_to_new_document(context);
	} catch (error) {
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
	}
};

frappe.attachment_queue_review.is_extraction_pending = function (status) {
	return frappe.attachment_queue_review.extraction_pending_statuses.includes(status);
};

// Reports slow extraction once when the threshold is reached.
frappe.attachment_queue_review.wait_for_extraction = async function (context, options = {}) {
	const { on_slow, signal } = options;

	if (!frappe.attachment_queue_review.is_extraction_pending(context.status)) {
		return context;
	}

	let latest_context = context;
	let listener;
	let abort_listener;
	let timeout;
	let fallback_interval;
	let is_resolving = false;

	const fetch_context = async () => {
		const result = await frappe.attachment_queue_review.fetch_context(context.queue_name);
		latest_context = result || latest_context;
		return latest_context;
	};

	// Clean up all timers and listeners when the wait ends.
	const cleanup = () => {
		clearTimeout(timeout);
		clearInterval(fallback_interval);
		if (listener) {
			frappe.realtime.off("task_update", listener);
		}
		if (abort_listener) {
			signal.removeEventListener("abort", abort_listener);
		}
	};

	try {
		return await new Promise((resolve, reject) => {
			if (signal) {
				if (signal.aborted) {
					resolve(null);
					return;
				}
				abort_listener = () => {
					if (is_resolving) return;
					is_resolving = true;
					resolve(null);
				};
				signal.addEventListener("abort", abort_listener, { once: true });
			}

			timeout = setTimeout(() => {
				if (is_resolving) return;

				// Re-check the status to avoid reporting slow extraction after it has finished.
				fetch_context()
					.then((ctx) => {
						if (is_resolving) return;
						if (frappe.attachment_queue_review.is_extraction_pending(ctx.status)) {
							on_slow?.(ctx);
							return;
						}
						is_resolving = true;
						resolve(ctx);
					})
					.catch(() => {
						// If the status check fails, report the last known state and keep polling.
						on_slow?.(latest_context);
					});
			}, frappe.attachment_queue_review.extraction_slow_threshold);

			fallback_interval = setInterval(() => {
				if (is_resolving) return;

				fetch_context()
					.then((ctx) => {
						if (is_resolving) return;
						if (!frappe.attachment_queue_review.is_extraction_pending(ctx.status)) {
							is_resolving = true;
							resolve(ctx);
						}
					})
					.catch(() => {});
			}, frappe.attachment_queue_review.extraction_poll_interval);

			listener = (data) => {
				if (is_resolving) return;
				if (
					data.task_id === context.task_id &&
					// task_update uses Background Task statuses, so fetch the queue context
					// after a terminal task status instead of using the event status directly.
					["Completed", "Failed", "Cancelled"].includes(data.status)
				) {
					is_resolving = true;
					fetch_context().then(resolve).catch(reject);
				}
			};

			frappe.realtime.on("task_update", listener);

			fetch_context()
				.then((ctx) => {
					if (is_resolving) return;
					if (!frappe.attachment_queue_review.is_extraction_pending(ctx.status)) {
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

// Keeps the panel in sync with the queue row's extraction status.
frappe.attachment_queue_review.watch_extraction = function (frm, context) {
	if (!frappe.attachment_queue_review.is_extraction_pending(context.status)) {
		return;
	}

	// Prevent multiple extraction watchers for the same queue row.
	if (frm.attachment_queue_review_watch?.queue_name === context.queue_name) {
		return;
	}
	frappe.attachment_queue_review.stop_watching(frm);

	const controller = new AbortController();
	frm.attachment_queue_review_watch = { queue_name: context.queue_name, controller };
	frm.attachment_queue_review_extraction_unreachable = false;

	frappe.show_alert({
		message: __("Extraction in progress"),
		indicator: "blue",
	});

	// Ignore results from watchers that are no longer active.
	const is_current = () =>
		frm.attachment_queue_review_watch?.controller === controller &&
		!!frm.attachment_queue_review_panel?.length;

	const apply = (next_context) => {
		frappe.attachment_queue_review.set_context(frm, next_context);
		frappe.attachment_queue_review.update_status(frm, next_context);
		frappe.attachment_queue_review.update_extraction_tab(frm, next_context);
	};

	frappe.attachment_queue_review
		.wait_for_extraction(context, {
			signal: controller.signal,
			on_slow() {
				if (!is_current()) return;
				frappe.show_alert({
					message: __("Extraction is taking longer than expected"),
					indicator: "orange",
				});
			},
		})
		.then((settled_context) => {
			// Ignore the result when the watcher was aborted.
			if (!settled_context || !is_current()) return;

			frm.attachment_queue_review_watch = null;
			apply(settled_context);

			if (settled_context.status === "Ready for Review") {
				frappe.show_alert({
					message: __("Extraction Completed"),
					indicator: "green",
				});
			}
		})
		.catch((error) => {
			if (!is_current()) return;

			// Only a fetch that never got a response lands here.
			frm.attachment_queue_review_watch = null;
			frm.attachment_queue_review_extraction_unreachable = true;
			frappe.attachment_queue_review.update_status(frm, context);
			console.error("Attachment Queue: could not follow extraction", error);
		});
};

frappe.attachment_queue_review.stop_watching = function (frm) {
	frm.attachment_queue_review_watch?.controller.abort();
	frm.attachment_queue_review_watch = null;
};

frappe.attachment_queue_review.get_context = function (frm) {
	return frm.doc?.__attachment_queue_review_context || null;
};

// Store review context on the document so to use the same property.
frappe.attachment_queue_review.set_context = function (frm, context) {
	if (frm.doc) {
		frm.doc.__attachment_queue_review_context = context;
	}
};

frappe.attachment_queue_review.get_pending_link = function (frm) {
	const context = frappe.attachment_queue_review.get_context(frm);

	if (context?.queue_name && context.document_type) {
		// Use created_document because the queue status may still be Queued or Processing after a document is saved.
		if (
			context.created_document ||
			frappe.attachment_queue_review.is_review_completed(context)
		) {
			return null;
		}

		return { queue_name: context.queue_name, document_type: context.document_type };
	}

	const queue_name = frappe.utils.get_query_params().attachment_queue;
	if (!queue_name) {
		return null;
	}

	return { queue_name, document_type: frm.doctype };
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
			const from_query_param = !!queryParams.attachment_queue;
			frappe.attachment_queue_review_loader.surviving_queue_name = null;
			context = await frappe.attachment_queue_review.fetch_context(queueName);

			// Don't restore context if the review ended while the extraction was in progress.
			if (from_query_param && !frappe.utils.get_query_params().attachment_queue) {
				return;
			}
		}
	}

	if (!context?.queue_name || context.document_type !== frm.doctype) {
		return;
	}

	// Don't revive a completed review from stale URL or pending context.
	if (frappe.attachment_queue_review.is_review_completed(context)) {
		frappe.attachment_queue_review.clear_query_param("attachment_queue");
		return;
	}

	frappe.attachment_queue_review.set_context(frm, context);
	frm.doc.__attachment_queue_name = context.queue_name;

	frappe.attachment_queue_review.set_query_param("attachment_queue", context.queue_name);
};

frappe.attachment_queue_review.mount = function (frm) {
	const context = frappe.attachment_queue_review.get_context(frm);
	if (!context?.queue_name) {
		frappe.attachment_queue_review.teardown(frm);
		return;
	}

	if (frappe.attachment_queue_review.is_review_completed(context)) {
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

	// Rebuild the panel if the stored element is no longer attached to the DOM.
	const $panel = frm.attachment_queue_review_panel;
	if (!$panel?.length || !$panel.get(0).isConnected) {
		$panel?.remove();
		frm.attachment_queue_review_panel = $(
			`<aside class="attachment-queue-review-panel"></aside>`
		);
		$std.length
			? $std.prepend(frm.attachment_queue_review_panel)
			: $layout.before(frm.attachment_queue_review_panel);
		frm.attachment_queue_review_built_source = null;
	}

	// Remember which document owns the panel so route changes can detect stale panels.
	frm.attachment_queue_review_panel_docname = frm.docname;

	// Start the watcher first so it resets stale state before the panel is rendered.
	frappe.attachment_queue_review.watch_extraction(frm, context);
	frappe.attachment_queue_review.build_panel(frm, context);
	frappe.attachment_queue_review.update_status(frm, context);
	frappe.attachment_queue_review.update_extraction_tab(frm, context);
};

frappe.attachment_queue_review.teardown = function (frm) {
	frappe.attachment_queue_review.stop_watching(frm);
	const $layout = frm.$wrapper.find(".form-layout").first();
	$layout.closest(".std-form-layout").removeClass("attachment-queue-review-layout");
	frm.attachment_queue_review_resizer_tooltip?.destroy();
	frm.attachment_queue_review_resizer_tooltip = null;
	frm.attachment_queue_review_panel?.remove();
	frm.attachment_queue_review_panel = null;
	frm.attachment_queue_review_built_source = null;
	frm.attachment_queue_review_panel_docname = null;
};

// If switching the panels it should be loaded fresh

frappe.attachment_queue_review.clear_switched_panels = function () {
	const route = frappe.get_route() || [];
	if (route[0] !== "Form") {
		return;
	}

	Object.values(frappe.views.formview || {}).forEach((page) => {
		const frm = page?.frm;
		if (!frm?.attachment_queue_review_panel?.length) {
			return;
		}

		const panel_docname = frm.attachment_queue_review_panel_docname;
		if (frm.doctype !== route[1] || panel_docname === route[2]) {
			return;
		}

		frappe.attachment_queue_review.teardown(frm);
	});
};

// Clear the page when it is changed in browser
$(document)
	.off("page-change.attachment-queue-review")
	.on("page-change.attachment-queue-review", () =>
		frappe.attachment_queue_review.clear_switched_panels()
	);

// Build the panel once per source file and update its contents without rebuilding
// the iframe, so the PDF preview keeps its page and scroll position.
frappe.attachment_queue_review.build_panel = function (frm, context) {
	const source_file_url = context.source_file_url || context.source_file || "";
	if (frm.attachment_queue_review_built_source === source_file_url) {
		return;
	}

	const dev_mode = cint(frappe.boot.developer_mode);
	const file_name = frappe.attachment_queue_review.get_file_name(source_file_url);

	const debug_tab_button = dev_mode
		? `
					<li class="nav-item">
						<button class="nav-link" data-tab="extraction" type="button" role="tab">
							${__("Debug")}
						</button>
					</li>
		`
		: "";
	// Kept empty so update_extraction_tab can refresh its contents without rebuilding the preview.
	const debug_tab_panel = dev_mode
		? `
				<section class="attachment-queue-review-tab-panel" data-panel="extraction">
					<div class="attachment-queue-review-sections"></div>
				</section>
		`
		: "";

	frm.attachment_queue_review_panel.html(`
		<div class="attachment-queue-review-shell">
			<div class="attachment-queue-review-alert"></div>
			<div class="form-tabs-list">
				<ul class="nav form-tabs" role="tablist">
					<li class="nav-item">
						<button class="nav-link active" data-tab="preview" type="button" role="tab">
							${__("Preview")}
						</button>
					</li>
${debug_tab_button}
				</ul>
			</div>
			<div class="attachment-queue-review-body">
				<section class="attachment-queue-review-tab-panel active" data-panel="preview">
					<div class="attachment-queue-review-resize-overlay">${__("Resizing preview...")}</div>
					${frappe.attachment_queue_review.get_preview_markup(source_file_url, file_name)}
				</section>
${debug_tab_panel}
			</div>
		</div>
		<div class="attachment-queue-review-resizer"></div>
	`);

	frm.attachment_queue_review_built_source = source_file_url;
	frm.attachment_queue_review_preview_type =
		frappe.attachment_queue_review.get_preview_type(source_file_url);

	frappe.attachment_queue_review.bind_panel_events(frm);
	frappe.attachment_queue_review.bind_resizer(frm);

	// Restore the previous tab, or fall back if the extraction tab is unavailable.
	frappe.attachment_queue_review.set_active_tab(
		frm,
		frm.attachment_queue_review_active_tab || "preview"
	);
};

// Bound once per panel and delegated so they keep working when inner content is updated.
// They use the current context from frm instead of the context captured at build time.
frappe.attachment_queue_review.bind_panel_events = function (frm) {
	const $panel = frm.attachment_queue_review_panel;

	$panel.off("click.attachment-queue-review").off("keydown.attachment-queue-review");

	$panel.on("click.attachment-queue-review", ".form-tabs-list .nav-link", function () {
		frappe.attachment_queue_review.set_active_tab(frm, $(this).attr("data-tab") || "preview");
	});

	$panel.on(
		"click.attachment-queue-review",
		".attachment-queue-review-section-head",
		function () {
			frappe.attachment_queue_review.toggle_section(frm, $(this).attr("data-section"));
		}
	);

	$panel.on(
		"keydown.attachment-queue-review",
		".attachment-queue-review-section-head",
		function (event) {
			if (event.key === "Enter" || event.key === " ") {
				event.preventDefault();
				$(this).trigger("click");
			}
		}
	);
};

// Only toggle classes to switch tabs without re-rendering, so the PDF preview keeps its state.
frappe.attachment_queue_review.set_active_tab = function (frm, tab) {
	const $panel = frm.attachment_queue_review_panel;
	if (!$panel?.length) {
		return;
	}

	// Fall back to Preview if the requested tab is unavailable.
	const active = $panel.find(`.attachment-queue-review-tab-panel[data-panel="${tab}"]`).length
		? tab
		: "preview";
	frm.attachment_queue_review_active_tab = active;

	$panel.find(".form-tabs-list .nav-link").each(function () {
		$(this).toggleClass("active", $(this).attr("data-tab") === active);
	});
	$panel.find(".attachment-queue-review-tab-panel").each(function () {
		$(this).toggleClass("active", $(this).attr("data-panel") === active);
	});
};

frappe.attachment_queue_review.get_open_sections = function (frm) {
	return frm.attachment_queue_review_open_sections || { text: true, json: false };
};

// Toggle classes only, so collapsing a section (JSON & text) does not rebuild the panel or reload the preview.
frappe.attachment_queue_review.toggle_section = function (frm, section) {
	if (!section) {
		return;
	}

	const open_sections = frappe.attachment_queue_review.get_open_sections(frm);
	const is_open = !open_sections[section];
	frm.attachment_queue_review_open_sections = { ...open_sections, [section]: is_open };

	const $head = frm.attachment_queue_review_panel.find(
		`.attachment-queue-review-section-head[data-section="${section}"]`
	);
	$head.toggleClass("collapsed", !is_open);
	$head.next(".section-body").toggleClass("hide", !is_open);
	$head
		.find(".collapse-indicator")
		.html(frappe.utils.icon(is_open ? "es-line-down" : "chevron-right", "sm", "mb-1"));
};

// Shows only important extraction outcomes.
frappe.attachment_queue_review.update_status = function (frm, context) {
	const $panel = frm.attachment_queue_review_panel;
	if (!$panel?.length) {
		return;
	}

	let alert_html = "";
	if (context.status === "Failed") {
		alert_html = frappe.ui.alert.html({
			title: __("Extraction Failed"),
			description:
				context.error_message ||
				__("No reason was recorded. You can still review the file and key it in."),
			theme: "red",
		});
	} else if (frm.attachment_queue_review_extraction_unreachable) {
		alert_html = frappe.ui.alert.html({
			title: __("Could Not Follow Extraction"),
			description: __(
				"The preview is ready to review. Reload the page to check whether extraction has finished."
			),
			theme: "yellow",
		});
	}
	$panel.find(".attachment-queue-review-alert").html(alert_html);
};

// Rebuild only the debug tab contents, leaving the preview and its iframe untouched.
frappe.attachment_queue_review.update_extraction_tab = function (frm, context) {
	const $sections = frm.attachment_queue_review_panel?.find(".attachment-queue-review-sections");
	if (!$sections?.length) {
		return;
	}

	const open_sections = frappe.attachment_queue_review.get_open_sections(frm);

	let raw_json_html = "";
	if (context.raw_extraction_json) {
		try {
			const parsed =
				typeof context.raw_extraction_json === "string"
					? JSON.parse(context.raw_extraction_json)
					: context.raw_extraction_json;
			raw_json_html = frappe.attachment_queue_review.get_section_markup({
				label: __("Raw Extraction JSON"),
				section: "json",
				is_open: open_sections.json,
				body_html: `<pre class="attachment-queue-review-json-pre">${frappe.utils.escape_html(
					JSON.stringify(parsed, null, 4)
				)}</pre>`,
			});
		} catch {
			// ignore JSON parse errors
		}
	}

	$sections.html(`
		${frappe.attachment_queue_review.get_section_markup({
			label: __("Extracted Text"),
			section: "text",
			is_open: open_sections.text,
			body_html: `<pre>${frappe.utils.escape_html(context.extracted_text || "")}</pre>`,
		})}
		${raw_json_html}
	`);
};

// Build the collapsible section markup with its current open/closed state.
frappe.attachment_queue_review.get_section_markup = function ({
	label,
	section,
	is_open,
	body_html,
}) {
	const icon = frappe.utils.icon(is_open ? "es-line-down" : "chevron-right", "sm", "mb-1");
	return `
		<div class="form-section attachment-queue-review-section">
			<div class="section-head collapsible attachment-queue-review-section-head ${
				is_open ? "" : "collapsed"
			}" data-section="${section}" tabindex="0">
				${label}
				<span class="collapse-indicator" tabindex="0">${icon}</span>
			</div>
			<div class="section-body ${is_open ? "" : "hide"}">${body_html}</div>
		</div>
	`;
};

frappe.attachment_queue_review.apply_saved_width = function ($layout) {
	// Pass shared limits to CSS and keep the max viewport-relative.
	$layout.css({
		"--attachment-queue-review-min-width": `${frappe.attachment_queue_review.min_preview_width}px`,
		"--attachment-queue-review-max-width": `${
			frappe.attachment_queue_review.max_preview_width_ratio * 100
		}vw`,
	});

	// Use set_preview_width so saved widths follow the same limits as drag resizing.
	frappe.attachment_queue_review.set_preview_width(
		$layout,
		frappe.attachment_queue_review.get_stored_preview_width()
	);
};

frappe.attachment_queue_review.bind_resizer = function (frm) {
	// Use a Frappe tooltip for the resize handle and destroy the old one before rebuilding.
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

			let is_resizing = true;
			let has_moved = false;
			const throttled_resize = frappe.utils.throttle(function (move_event) {
				// Ignore trailing throttle calls that run after mouseup has saved the final width.
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
						// Apply the final cursor position directly so the saved width matches where the user released.
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

	// Calculate the preview width from the cursor position, including RTL layouts.
	const layout_rect = layout.getBoundingClientRect();
	const width = frappe.utils.is_rtl()
		? layout_rect.right - event.clientX
		: event.clientX - layout_rect.left;
	frappe.attachment_queue_review.set_preview_width($layout, width);
};

frappe.attachment_queue_review.set_preview_width = function ($layout, width) {
	const preview_width = frappe.attachment_queue_review.clamp_preview_width(width);
	$layout.css("--attachment-queue-review-width", `${preview_width}px`);
};

frappe.attachment_queue_review.get_current_preview_width = function ($layout) {
	const value = (
		$layout.get(0)?.style.getPropertyValue("--attachment-queue-review-width") || ""
	).trim();
	return frappe.attachment_queue_review.clamp_preview_width(Number(value.replace("px", "")));
};

frappe.attachment_queue_review.clamp_preview_width = function (width) {
	const max_preview_width = Math.max(
		frappe.attachment_queue_review.min_preview_width,
		Math.round(window.innerWidth * frappe.attachment_queue_review.max_preview_width_ratio)
	);
	return Math.min(
		Math.max(
			Number(width) || frappe.attachment_queue_review.default_preview_width,
			frappe.attachment_queue_review.min_preview_width
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

// Normalize source_file into a safe preview URL for iframe/img src.
frappe.attachment_queue_review.get_preview_url = function (file_url) {
	if (!file_url) {
		return "";
	}

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
	// Consume the link once, since both after_save and on_submit can call this.
	const pending = frm.__attachment_queue_pending_link;
	frm.__attachment_queue_pending_link = null;

	if (!pending || !frm.doc.name || frm.doc.__attachment_queue_linked) {
		return Promise.resolve();
	}

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
				// Use the row's actual status because linking can happen while extraction is still running.
				status: r.message?.status || context?.status,
				created_document: frm.doc.name,
			};
			frappe.attachment_queue_review.set_context(frm, updated_context);
			delete frm.doc.__attachment_queue_name;

			frappe.attachment_queue_review.clear_query_param("attachment_queue");

			// The source file is linked to this document, so the sidebar can show it immediately.
			frm.sidebar?.reload_docinfo?.();

			if (frappe.attachment_queue_review.is_review_completed(updated_context)) {
				frappe.attachment_queue_review.teardown(frm);
			}
		},
		error() {
			frm.doc.__attachment_queue_linked = 0;
		},
	});
};

frappe.attachment_queue_review.refresh_form = async function (frm) {
	await frappe.attachment_queue_review.hydrate_context(frm);
	frappe.attachment_queue_review.mount(frm);
	frappe.attachment_queue_review.setup_upload_first(frm);
};
