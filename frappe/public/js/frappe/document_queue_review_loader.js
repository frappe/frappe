frappe.provide("frappe.document_queue_review_loader");

frappe.document_queue_review_loader.script_url =
	"/assets/frappe/js/frappe/document_queue_review.js";
frappe.document_queue_review_loader.storage_key = "frappe.document_queue_review.pending_context";
frappe.document_queue_review_loader.upload_first_enabled = {};

frappe.document_queue_review_loader.load = function () {
	if (frappe.document_queue_review?.refresh_form) {
		return Promise.resolve();
	}

	if (frappe.document_queue_review_loader.loading) {
		return frappe.document_queue_review_loader.loading;
	}

	frappe.document_queue_review_loader.loading = new Promise((resolve, reject) => {
		const script = document.createElement("script");
		script.src = frappe.document_queue_review_loader.script_url;
		script.onload = resolve;
		script.onerror = reject;
		document.head.appendChild(script);
	});

	return frappe.document_queue_review_loader.loading;
};

frappe.document_queue_review_loader.has_pending_context = function (frm) {
	if (frm.document_queue_review_context || frm.doc.__document_queue_review_context) {
		return true;
	}

	if (frappe.route_options?.document_queue_review_context?.queue_name) {
		return true;
	}

	try {
		const pending = JSON.parse(
			sessionStorage.getItem(frappe.document_queue_review_loader.storage_key) || "{}"
		);
		return Boolean(pending?.context?.queue_name);
	} catch {
		return false;
	}
};

frappe.document_queue_review_loader.is_upload_first_enabled = function (doctype) {
	if (doctype in frappe.document_queue_review_loader.upload_first_enabled) {
		return Promise.resolve(frappe.document_queue_review_loader.upload_first_enabled[doctype]);
	}

	return frappe
		.call({
			method: "frappe.core.doctype.document_queue.document_queue.is_upload_first_workflow_enabled",
			args: { document_type: doctype },
		})
		.then((response) => {
			const enabled = Boolean(response.message);
			frappe.document_queue_review_loader.upload_first_enabled[doctype] = enabled;
			return enabled;
		})
		.catch(() => false);
};

frappe.document_queue_review_loader.setup_form = async function (frm) {
	if (frappe.document_queue_review_loader.has_pending_context(frm)) {
		await frappe.document_queue_review_loader.load();
		frappe.document_queue_review.refresh_form(frm);
		return;
	}

	if (!frm?.is_new?.()) {
		return;
	}

	const enabled = await frappe.document_queue_review_loader.is_upload_first_enabled(frm.doctype);
	if (!enabled) {
		return;
	}

	await frappe.document_queue_review_loader.load();
	frappe.document_queue_review.refresh_form(frm);
};

frappe.document_queue_review_loader.setup_list = async function (listview) {
	const enabled = await frappe.document_queue_review_loader.is_upload_first_enabled(
		listview.doctype
	);
	if (!enabled) {
		return;
	}

	await frappe.document_queue_review_loader.load();
	frappe.document_queue_review.setup_list_banner(listview);
};

frappe.document_queue_review_loader.patch_list_view = function () {
	if (frappe.document_queue_review_loader.list_view_patched || !frappe.views?.ListView) {
		return;
	}

	const original_after_render = frappe.views.ListView.prototype.after_render;
	frappe.views.ListView.prototype.after_render = function () {
		original_after_render.apply(this, arguments);
		frappe.document_queue_review_loader.setup_list(this);
	};

	frappe.document_queue_review_loader.list_view_patched = true;
};

frappe.ui.form.on("*", {
	refresh(frm) {
		frappe.document_queue_review_loader.setup_form(frm);
	},
});

frappe.document_queue_review_loader.patch_list_view();
frappe.router.on("change", () => {
	frappe.document_queue_review_loader.patch_list_view();
});
