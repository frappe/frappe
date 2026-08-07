frappe.provide("frappe.document_queue_review");


frappe.document_queue_review.width_storage_key = "frappe.document_queue_review.preview_width";
frappe.document_queue_review.default_preview_width = 38;
frappe.document_queue_review.reviewable_statuses = ["Ready for Review", "Failed"];
frappe.document_queue_review.image_extensions = [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"];

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

	frappe.model.with_doctype(context.document_type, () => {
		const doc = frappe.model.get_new_doc(context.document_type);
		frappe.document_queue_review.pending_context = context;
		frappe.set_route("Form", context.document_type, doc.name).then(() => {
			let url = new URL(window.location.href);
			url.searchParams.set("document_queue", context.queue_name);
			window.history.replaceState(window.history.state, "", url.toString());
		});
	});
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



frappe.document_queue_review.is_upload_first_enabled = async function (doctype, frm) {
	if (!doctype || doctype === "Document Queue") {
		return false;
	}

	if (cint(frm?.meta?.enable_upload_first_workflow) === 1) {
		return true;
	}

	const meta = frappe.get_meta(doctype);
	if (cint(meta?.enable_upload_first_workflow) === 1) {
		return true;
	}

	if (frappe.boot?.upload_first_doctypes?.includes(doctype)) {
		return true;
	}

	try {
		const res = await frappe.call({
			method: "frappe.core.doctype.document_queue.document_queue.is_upload_first_workflow_doctype",
			args: { document_type: doctype },
		});
		const is_enabled = Boolean(res?.message);
		if (is_enabled) {
			if (frappe.boot) {
				frappe.boot.upload_first_doctypes = frappe.boot.upload_first_doctypes || [];
				if (!frappe.boot.upload_first_doctypes.includes(doctype)) {
					frappe.boot.upload_first_doctypes.push(doctype);
				}
			}
			if (meta) {
				meta.enable_upload_first_workflow = 1;
			}
			if (frm?.meta) {
				frm.meta.enable_upload_first_workflow = 1;
			}
		}
		return is_enabled;
	} catch {
		return false;
	}
};

frappe.document_queue_review.setup_upload_first = async function (frm) {
	frappe.document_queue_review.remove_upload_first(frm);

	if (!frm?.is_new?.() || frm.in_dialog || !frm.page || frappe.document_queue_review.get_context(frm)) {
		return;
	}

	const enabled = await frappe.document_queue_review.is_upload_first_enabled(frm.doctype, frm);
	if (!enabled || frappe.document_queue_review.get_context(frm)) {
		return;
	}

	frappe.document_queue_review.add_styles();

	const $page = frm.page.wrapper.find(".page-body");
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
	frm?.page?.wrapper?.find(".document-queue-upload-first").remove();
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
	frappe.dom.freeze(`<div class="document-queue-freeze-body"><div class="es-spinner"></div><div>${__("Extracting document...")}</div></div>`);
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
		} else if (context.status === "Ready for Review") {
			frappe.show_alert({
				message: __("Extraction Completed"),
				indicator: "green"
			});
		}

		await new Promise(resolve => {
			frappe.model.with_doctype(context.document_type, () => {
				const doc = frappe.model.get_new_doc(context.document_type);
				frappe.document_queue_review.pending_context = context;
				frappe.set_route("Form", context.document_type, doc.name).then(() => {
					let url = new URL(window.location.href);
					url.searchParams.set("document_queue", context.queue_name);
					window.history.replaceState(window.history.state, "", url.toString());
					resolve();
				});
			});
		});
	} finally {
		frappe.dom.unfreeze();
	}
};

frappe.document_queue_review.wait_for_extraction = async function (context) {
	if (!["Queued", "Processing"].includes(context.status)) {
		return context;
	}

	let latest_context = context;
	let listener;
	let timeout;
	let is_resolving = false;

	const fetch_context = async () => {
		const result = await frappe.document_queue_review.fetch_context(context.queue_name);
		latest_context = result || latest_context;
		return latest_context;
	};

	try {
		return await new Promise((resolve, reject) => {
			let fallback_interval;
			const finish = (ctx) => {
				clearTimeout(timeout);
				if (fallback_interval) clearInterval(fallback_interval);
				resolve(ctx);
			};

			timeout = setTimeout(() => {
				if (is_resolving) return;
				is_resolving = true;
				frappe.msgprint({
					title: __("Extraction Still Running"),
					message: __(
						"The document was queued, but extraction is taking longer than expected. You can continue reviewing it from Document Queue when extraction finishes."
					),
					indicator: "orange",
				});
				fetch_context().then(finish).catch(reject);
			}, 90000);

			fallback_interval = setInterval(() => {
				if (is_resolving) return;
				if (frappe.realtime?.socket?.connected) return;
				
				fetch_context()
					.then((ctx) => {
						if (is_resolving) return;
						if (["Ready for Review", "Failed"].includes(ctx.status)) {
							is_resolving = true;
							finish(ctx);
						}
					})
					.catch(() => {});
			}, 3000);

			listener = (data) => {
				if (is_resolving) return;
				if (data.task_id === context.task_id && ["Ready for Review", "Failed"].includes(data.status)) {
					is_resolving = true;
					fetch_context().then(finish).catch(reject);
				}
			};

			frappe.realtime.on("task_update", listener);

			// Immediate state fetch to close the fast-completion race condition
			fetch_context()
				.then((ctx) => {
					if (is_resolving) return;
					if (!["Queued", "Processing"].includes(ctx.status)) {
						is_resolving = true;
						finish(ctx);
					}
				})
				.catch(reject);
		});
	} finally {
		if (listener) {
			frappe.realtime.off("task_update", listener);
		}
	}
};

frappe.document_queue_review.get_context = function (frm) {
	return frm.doc.__document_queue_review_context || null;
};

frappe.document_queue_review.hydrate_context = async function (frm) {
	if (frappe.document_queue_review.get_context(frm)) {
		return;
	}

	let context = frappe.document_queue_review.pending_context;
	if (context) {
		frappe.document_queue_review.pending_context = null;
	}

	if (!context?.queue_name) {
		const queryParams = frappe.utils.get_query_params();
		let queueName = queryParams.document_queue || frappe.document_queue_review_loader.surviving_queue_name;
		if (queueName) {
			frappe.document_queue_review_loader.surviving_queue_name = null;
			context = await frappe.document_queue_review.fetch_context(queueName);
		}
	}

	if (!context?.queue_name || context.document_type !== frm.doctype) {
		return;
	}

	frm.doc.__document_queue_review_context = context;
	frm.doc.__document_queue_name = context.queue_name;

	const url = new URL(window.location.href);
	if (url.searchParams.get("document_queue") !== context.queue_name) {
		url.searchParams.set("document_queue", context.queue_name);
		window.history.replaceState(window.history.state, "", url.toString());
	}
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
	const dev_mode = cint(frappe.boot.developer_mode);
	let active_tab = frm.document_queue_review_active_tab || "preview";
	if (!dev_mode && active_tab === "extraction") {
		active_tab = "preview";
	}
	const source_file_url = context.source_file_url || context.source_file || "";
	const file_name = frappe.document_queue_review.get_file_name(source_file_url);
	const preview_type = frappe.document_queue_review.get_preview_type(source_file_url);
	const open_sections = frm.document_queue_review_open_sections || { text: true, json: false };
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
		error_alert = `
			<div class="alert alert-danger mb-3">
				<strong>${__("Extraction Failed")}</strong><br>
				${frappe.utils.escape_html(context.error_message)}
			</div>
		`;
	}

	let raw_json_html = "";
	if (context.raw_extraction_json) {
		try {
			let parsed = typeof context.raw_extraction_json === "string" ? JSON.parse(context.raw_extraction_json) : context.raw_extraction_json;
			let formatted = JSON.stringify(parsed, null, 4);
			raw_json_html = `
				<div class="form-section document-queue-review-section">
					<div class="section-head collapsible document-queue-review-section-head ${
						open_sections.json ? "" : "collapsed"
					}" data-section="json" tabindex="0">
						${__("Raw Extraction JSON")}
						<span class="collapse-indicator" tabindex="0">${json_icon}</span>
					</div>
					<div class="section-body ${open_sections.json ? "" : "hide"}">
						<pre class="document-queue-review-json-pre">${frappe.utils.escape_html(formatted)}</pre>
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
				<section class="document-queue-review-tab-panel ${
					active_tab === "extraction" ? "active" : ""
				}" data-panel="extraction">
					<div class="document-queue-review-sections">
						${error_alert}
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
						${raw_json_html}
					</div>
				</section>
		`;
	}

	frm.document_queue_review_panel.html(`
		<div class="document-queue-review-shell">
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
			<div class="document-queue-review-body">
				<section class="document-queue-review-tab-panel ${
					active_tab === "preview" ? "active" : ""
				}" data-panel="preview">
					<div class="document-queue-review-resize-overlay">${__("Resizing preview...")}</div>
					${frappe.document_queue_review.get_preview_markup(source_file_url, file_name)}
				</section>
${debug_tab_panel}
			</div>
		</div>
		<div class="document-queue-review-resizer" title="${__("Resize")}"></div>
	`);
	frm.document_queue_review_preview_type = preview_type;

	frm.document_queue_review_panel.off("click.document-queue-review");
	frm.document_queue_review_panel.on(
		"click.document-queue-review",
		".form-tabs-list .nav-link",
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
				...open_sections,
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

	if (frappe.document_queue_review.image_extensions.some((ext) => lower.endsWith(ext))) {
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

	if (frappe.document_queue_review.image_extensions.some((ext) => lower.endsWith(ext))) {
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
	const context = frappe.document_queue_review.get_context(frm);
	const queue_name =
		frappe.document_queue_review.saving_queue_name ||
		new URLSearchParams(window.location.search).get("document_queue");

	frappe.document_queue_review.saving_queue_name = null;

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
			const updated_context = {
				...(context || {}),
				status: r.message?.status || "Completed",
				created_document: frm.doc.name,
			};
			frm.doc.__document_queue_review_context = updated_context;
			delete frm.doc.__document_queue_name;

			const url = new URL(window.location.href);
			if (url.searchParams.has("document_queue")) {
				url.searchParams.delete("document_queue");
				window.history.replaceState(window.history.state, "", url.toString());
			}

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

	// Inject the primary "Review Pending" button that opens the modal.
	frappe.document_queue_list_action?.setup(listview);
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

frappe.document_queue_review.refresh_form = async function (frm) {
	await frappe.document_queue_review.hydrate_context(frm);
	frappe.document_queue_review.mount(frm);
	frappe.document_queue_review.setup_upload_first(frm);
};

frappe.document_queue_review.add_styles = function () {
	frappe.dom.set_style(
		`
		.document-queue-freeze-body {
			display: flex;
			flex-direction: column;
			align-items: center;
			justify-content: center;
			gap: 8px;
		}
		.document-queue-review-json-pre {
			background-color: var(--control-bg);
			border: 1px solid var(--border-color);
			border-radius: var(--border-radius-sm);
			font-size: var(--text-sm);
		}
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
			cursor: pointer;
			transition: background-color 0.2s;
		}
		.document-queue-ready-banner:hover {
			background-color: var(--control-bg);
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
			background: var(--border-color);
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
		`,
		"document-queue-review-style"
	);
};

$(document).on("form-refresh", async function (event, frm) {
	await frappe.document_queue_review.hydrate_context(frm);
	frappe.document_queue_review.mount(frm);
	frappe.document_queue_review.setup_upload_first(frm);
});


