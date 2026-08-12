frappe.provide("frappe.document_queue_review_loader");

frappe.document_queue_review_loader.script_url =
	"/assets/frappe/js/frappe/document_queue_review.js";

// Snapshot the queue name immediately on script load to survive Frappe's "New Document" redirect
const _initial_queue = frappe.utils.get_query_params().document_queue;
if (_initial_queue) {
	frappe.document_queue_review_loader.surviving_queue_name = _initial_queue;
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
		return true;
	}

	if (frappe.document_queue_review_loader.surviving_queue_name) {
		return true;
	}

	return false;
};

// `frappe.boot.upload_first_doctypes` is built server-side in boot.py with the
// same predicate as is_upload_first_workflow_doctype (flag set, not a child
// table), so the full answer is already on the client. Async only because this
// gate is awaited/then-ed by its call sites, including list_view.js.
frappe.document_queue_review_loader.is_upload_first_enabled = async function (doctype) {
	if (!doctype || doctype === "Document Queue") {
		return false;
	}

	return !!frappe.boot?.upload_first_doctypes?.includes(doctype);
};

// Single owner of the review lifecycle on a form. Runs on every form refresh
// (via the "*" handler below) and decides whether the review module is needed,
// then always hands off to one refresh_form() call.
frappe.document_queue_review_loader.setup_form = async function (frm) {
	if (frappe.document_queue_review_loader.has_pending_context(frm)) {
		await frappe.document_queue_review_loader.load();
	} else if (
		frm?.is_new?.() &&
		!frm.in_dialog &&
		frm.page &&
		(await frappe.document_queue_review_loader.is_upload_first_enabled(frm.doctype))
	) {
		await frappe.document_queue_review_loader.load();
	} else if (!frappe.document_queue_review?.refresh_form) {
		return;
	}

	frappe.document_queue_review.refresh_form(frm);
};


frappe.ui.form.on("*", {
	refresh(frm) {
		frappe.document_queue_review_loader.setup_form(frm);
	},
	// Written on every save, including to null. That is what bounds its lifetime:
	// a save that fails leaves its value behind, and the next save on this form
	// overwrites it before after_save can read it.
	before_save(frm) {
		frm.__document_queue_pending_link =
			frappe.document_queue_review?.get_pending_link?.(frm) || null;
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
