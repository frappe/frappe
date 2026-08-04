frappe.provide("frappe.document_queue_review_loader");

frappe.document_queue_review_loader.script_url =
	"/assets/frappe/js/frappe/document_queue_review.js";

// Snapshot the queue name immediately on script load to survive Frappe's "New Document" redirect
const initial_params = new URLSearchParams(window.location.search);
if (initial_params.get("document_queue")) {
	frappe.document_queue_review_loader.surviving_queue_name = initial_params.get("document_queue");
}

frappe.document_queue_review_loader.load = function () {
	if (frappe.document_queue_review?.refresh_form) {
		return Promise.resolve();
	}

	if (frappe.document_queue_review_loader.loading) {
		return frappe.document_queue_review_loader.loading;
	}

	frappe.document_queue_review_loader.loading = frappe.require(
		frappe.document_queue_review_loader.script_url
	).then(() => {
		if (!frappe.document_queue_review?.refresh_form) {
			throw new Error("Document Queue Review module failed to load.");
		}
	});

	return frappe.document_queue_review_loader.loading;
};

frappe.document_queue_review_loader.has_pending_context = function (frm) {
	if (frm.doc.__document_queue_review_context) {
		return true;
	}

	if (frappe.document_queue_review?.pending_context?.queue_name) {
		return true;
	}

	const query_params = frappe.utils.get_query_params();
	if (query_params.document_queue) {
		frappe.document_queue_review_loader.surviving_queue_name = query_params.document_queue;
		return true;
	}

	if (frappe.document_queue_review_loader.surviving_queue_name) {
		return true;
	}

	return false;
};

frappe.document_queue_review_loader.is_upload_first_enabled = function (doctype) {
	return Promise.resolve(Boolean(frappe.boot.upload_first_doctypes?.includes(doctype)));
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


frappe.ui.form.on("*", {
	refresh(frm) {
		frappe.document_queue_review_loader.setup_form(frm);
	},
	before_save(frm) {
		if (frm.doc.__document_queue_review_context) {
			// Save the queue name so we can link it after the server reloads the document state
			if (frappe.document_queue_review) {
				frappe.document_queue_review.saving_queue_name =
					frm.doc.__document_queue_review_context.queue_name;
			}
		}
	},
	after_save(frm) {
		if (frappe.document_queue_review?.link_after_save) {
			return frappe.document_queue_review.link_after_save(frm);
		}
	},
	on_submit(frm) {
		if (frappe.document_queue_review?.link_after_save) {
			return frappe.document_queue_review.link_after_save(frm);
		}
	},
});


