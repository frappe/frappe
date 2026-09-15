frappe.provide("frappe.attachment_queue_review");

frappe.attachment_queue_review.width_storage_key =
	"frappe.attachment_queue_review.preview_width_px";
frappe.attachment_queue_review.default_preview_width = 480;
frappe.attachment_queue_review.min_preview_width = 320;

frappe.attachment_queue_review.max_preview_width_ratio = 0.6;
frappe.attachment_queue_review.reviewable_statuses = ["Ready for Review", "Failed"];
// The one status a client-held context can be trusted on: a row only ever reaches
// "Completed" by being linked, and nothing moves it out again. The transient statuses are
// deliberately not read this way - the panel's copy lags the worker, so treating a stale
// "Queued" as unlinkable would drop the link on a save taken mid-extraction.
frappe.attachment_queue_review.is_review_completed = function (context) {
	return context?.status === "Completed";
};
// Extraction is in flight in exactly these two states; anything else is terminal for
// the watcher's purposes. Held as one list because four call sites used to inline it.
frappe.attachment_queue_review.extraction_pending_statuses = ["Queued", "Processing"];
// How long extraction may run before the panel says so. Nothing stops at this mark -
// it only reports slowness; the watcher carries on polling at the same interval.
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
// reload. Three call sites carried their own copy of this block - the two below
// and attachment_queue_review_modal.js's _start_review.
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

	if (
		!frm?.is_new?.() ||
		frm.in_dialog ||
		!frm.page ||
		frappe.attachment_queue_review.get_context(frm)
	) {
		return;
	}

	// The loader owns this gate - it ships in form.bundle.js, so it is always
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
	// No freeze: creating the row and opening the form are both quick, and extraction
	// is not waited on at all - the row carries the source file from the moment it
	// exists, so the review page and its preview can come up straight away and
	// mount() picks the extraction up from there.
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
		// frappe.call reports HTTP-level failures itself, but a request that never gets
		// a response (connection dropped mid-upload) matches none of its statusCode
		// handlers - without this nothing would be said at all, and the rejection would
		// escape unhandled through FileUploader's on_success.
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

// `on_slow` fires at most once, when the threshold passes on a still-pending row.
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

	// Single owner of teardown, so the timer, the interval and both listeners are
	// released on every settle path — resolve *and* reject.
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

				// Re-read before flagging. Both the realtime listener and this timer
				// race the worker, and a row that finished while we waited must not
				// be reported as still running.
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
						// No fresh status to go on — "still running" is still the honest
						// read, and the poll below carries on either way.
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
					// `task_update` is Background Task's event and carries Background
					// Task's status vocabulary, not the queue row's. The two overlap
					// only on "Failed", which is why matching the queue's names here
					// left the success path dead. "Cancelled" is terminal too: the
					// worker is gone, so without it the watch would poll a row that is
					// never going to move again.
					["Completed", "Failed", "Cancelled"].includes(data.status)
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

// Keeps one panel in step with one queue row's extraction.
frappe.attachment_queue_review.watch_extraction = function (frm, context) {
	if (!frappe.attachment_queue_review.is_extraction_pending(context.status)) {
		return;
	}

	// mount() runs on every form refresh; one watcher per queue row is enough.
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

	// A settle that lands after the panel was torn down, or after a second watcher
	// took over, must not draw over whatever replaced it.
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
			// null means the watch was aborted, so there is nothing to report.
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

// Single writer, so the two places that update a live review - hydrate_context and
// link_after_save - cannot disagree about where the context lives. Per-document on
// purpose: the loader's has_pending_context reads the same property to decide
// whether to load this module at all.
frappe.attachment_queue_review.set_context = function (frm, context) {
	if (frm.doc) {
		frm.doc.__attachment_queue_review_context = context;
	}
};

// Neither obvious carrier survives a save: frappe.model.sync replaces frm.doc for
// a new document, and rename_notify re-routes to the saved name, which drops
// ?attachment_queue= from the URL. frm itself survives both, so before_save copies
// the context onto it and link_after_save reads it back from there.
frappe.attachment_queue_review.get_pending_link = function (frm) {
	const context = frappe.attachment_queue_review.get_context(frm);

	if (context?.queue_name && context.document_type) {
		// created_document, not the status: a save taken mid-extraction claims the row
		// without ending it, so the row is still Queued or Processing while already having
		// produced its document. link_after_save writes it into the context, and like the
		// status it only ever moves one way - empty to set.
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

			// This fetch races the link: the refresh that follows a save starts it, and
			// link_after_save can finish while it is still in flight. Clearing
			// ?attachment_queue= is how the link ends the review, so a fetch that comes
			// back to find it gone is answering for a review that is already over —
			// re-establishing it here would re-stamp the param and let the submit's
			// before_save arm a second link against a row the server has marked Completed.
			if (from_query_param && !frappe.utils.get_query_params().attachment_queue) {
				return;
			}
		}
	}

	if (!context?.queue_name || context.document_type !== frm.doctype) {
		return;
	}

	// A finished review is not revived from a URL or a stale pending_context, on the
	// document it produced included: that document owns the source file now, and
	// Frappe's own attachment preview is the way back to it.
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

	// The stored handle can outlive its DOM node  a layout rebuilt underneath the
	// panel leaves a detached element behind, and updating a detached node draws
	// nothing at all. Treat that as "never built" and put a fresh panel in.
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

	// Which document this panel belongs to. frm is shared by every document of the
	// doctype, so this is the only way a route change can tell "still the same
	// review" from "a different one" - frm.docname has not been switched over yet
	// at the point clear_switched_panels() below runs.
	frm.attachment_queue_review_panel_docname = frm.docname;

	// Before the render calls, not after: starting the watch is what clears the slow
	// and unreachable flags from a previous one, and update_status reads them. Its
	// callbacks only ever fire a microtask later, by which time the panel is drawn.
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

// FormFactory keeps one form and one .std-form-layout per doctype and reuses them
// for every document of it, so the panel - and the <iframe> that has already
// downloaded a PDF - stay in the page's DOM when the routed document changes.

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

		// The save's reroute from the local name to the saved one counts as a switch
		// like any other: the review ends with the link, so the panel goes with it.
		const panel_docname = frm.attachment_queue_review_panel_docname;
		if (frm.doctype !== route[1] || panel_docname === route[2]) {
			return;
		}

		frappe.attachment_queue_review.teardown(frm);
	});
};

$(document)
	.off("page-change.attachment-queue-review")
	.on("page-change.attachment-queue-review", () =>
		frappe.attachment_queue_review.clear_switched_panels()
	);

// Builds the panel shell exactly once per source file. Everything that changes
// while a review is open - extraction status, extracted data, the active tab, which
// debug sections are expanded - is applied to this DOM by the helpers below, never
// by rebuilding it. That is what keeps the preview stable: re-creating the <iframe>
// restarts the PDF download and throws away the reader's page and scroll position,
// which is what used to happen on every form refresh, tab switch and section toggle.
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
	// Body left empty on purpose - update_extraction_tab owns its contents, so the
	// extracted text and JSON can be refreshed without touching the preview beside it.
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
	// Restores the tab the reviewer was on if this is a rebuild rather than a first
	// build, and corrects a stored "extraction" tab that developer mode no longer offers.
	frappe.attachment_queue_review.set_active_tab(
		frm,
		frm.attachment_queue_review_active_tab || "preview"
	);
};

// Bound once per built panel, and delegated, so they keep working across the
// update_* helpers replacing inner content. They read the live context off frm
// instead of closing over the one that was current at build time - extraction
// finishing replaces it.
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

// Class toggles only. The stylesheet already hides inactive panels
// (.attachment-queue-review-tab-panel, and &.active), so switching tabs needs no
// re-render — and must not do one, or the PDF would reload on every switch.
frappe.attachment_queue_review.set_active_tab = function (frm, tab) {
	const $panel = frm.attachment_queue_review_panel;
	if (!$panel?.length) {
		return;
	}

	// Falls back to the preview when the requested panel does not exist, which is
	// the case for the debug tab outside developer mode.
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

// Same class-only rule as the tabs: collapsing a debug section must not rebuild
// the panel that the preview lives in.
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

// Owns the one piece of extraction state that has to persist in the panel: an
// alert for the outcomes a reviewer must not miss. Extraction merely being in
// progress is not reported here at all — watch_extraction toasts that once and
// lets it fade, so the panel carries no running-state chrome and the preview
// keeps the full pane.
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

// Rebuilds only the debug tab's contents, the one part of the panel that extraction
// actually changes. Unconditional: the preview and its <iframe> live in a different
// tab panel, so redrawing this one costs nothing that matters.
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
	// Through set_preview_width, so the stored value is written in the same unit and
	// through the same clamp as a drag — one writer for the track, not two.
	frappe.attachment_queue_review.set_preview_width(
		$layout,
		frappe.attachment_queue_review.get_stored_preview_width()
	);
};

frappe.attachment_queue_review.bind_resizer = function (frm) {
	// Espresso tooltip instead of a native `title`, matching the tooltips used
	// elsewhere in desk. The handle survives for as long as the panel does, so this
	// runs once per build — but a rebuild does replace it, and the previous instance
	// must be destroyed or its bubble (which lives on <body>) outlives its trigger.
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

	// The panel starts at the layout's left edge, so the cursor's offset from it is the
	// width the reviewer is asking for - in pixels, which is now also the unit the track
	// is expressed in. No division by the layout's width: that is the moving basis this
	// stopped depending on.
	const layout_rect = layout.getBoundingClientRect();
	frappe.attachment_queue_review.set_preview_width($layout, event.clientX - layout_rect.left);
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
				// The row's own status, not an assumed "Completed": a link taken
				// mid-extraction leaves the row Queued or Processing, and claiming
				// otherwise would take the panel down below.
				status: r.message?.status || context?.status,
				created_document: frm.doc.name,
			};
			frappe.attachment_queue_review.set_context(frm, updated_context);
			delete frm.doc.__attachment_queue_name;

			frappe.attachment_queue_review.clear_query_param("attachment_queue");

			// The source file hangs off this document now, so the sidebar can show it
			// whether or not extraction has finished.
			frm.sidebar?.reload_docinfo?.();

			// A link taken mid-extraction is not that row. The extracted text has not
			// arrived yet and this panel is the only place it is ever shown, so the
			// watcher mount() started carries the row to Completed and the refresh
			// after that is what takes the panel down.
			if (frappe.attachment_queue_review.is_review_completed(updated_context)) {
				frappe.attachment_queue_review.teardown(frm);
			}
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
