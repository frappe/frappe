frappe.provide("frappe.attachment_queue_review_loader");

frappe.attachment_queue_review_loader.script_url =
	"/assets/frappe/js/frappe/attachment_queue_review.js";

// Snapshot the queue name immediately on script load to survive Frappe's "New Document" redirect
const _initial_queue = frappe.utils.get_query_params().attachment_queue;
if (_initial_queue) {
	frappe.attachment_queue_review_loader.surviving_queue_name = _initial_queue;
}

frappe.attachment_queue_review_loader.load = function () {
	if (frappe.attachment_queue_review?.refresh_form) {
		return Promise.resolve();
	}

	if (frappe.attachment_queue_review_loader.loading) {
		return frappe.attachment_queue_review_loader.loading;
	}

	frappe.attachment_queue_review_loader.loading = frappe
		.require(frappe.attachment_queue_review_loader.script_url)
		.then(() => {
			if (!frappe.attachment_queue_review?.refresh_form) {
				throw new Error("Attachment Queue Review module failed to load.");
			}
		});

	return frappe.attachment_queue_review_loader.loading;
};

frappe.attachment_queue_review_loader.has_pending_context = function (frm) {
	if (frm.doc.__attachment_queue_review_context) {
		return true;
	}

	if (frappe.attachment_queue_review?.pending_context?.queue_name) {
		return true;
	}

	const query_params = frappe.utils.get_query_params();
	if (query_params.attachment_queue) {
		return true;
	}

	if (frappe.attachment_queue_review_loader.surviving_queue_name) {
		return true;
	}

	return false;
};

// Answered from the DocType meta the form/list view has already loaded, so this
// costs no request. Mirrors the server predicate is_upload_first_workflow_doctype
// (flag set, not a child table), which stays the authority for every write.
// Async only because this gate is awaited/then-ed by its call sites, including
// list_view.js.
frappe.attachment_queue_review_loader.is_upload_first_enabled = async function (doctype) {
	if (!doctype || doctype === "Attachment Queue") {
		return false;
	}

	const meta = frappe.get_meta(doctype);

	return !!meta && !!cint(meta.enable_upload_first_workflow) && !cint(meta.istable);
};

// Single owner of the review lifecycle on a form. Runs on every form refresh
// (via the "*" handler below) and decides whether the review module is needed,
// then always hands off to one refresh_form() call.
frappe.attachment_queue_review_loader.setup_form = async function (frm) {
	if (frappe.attachment_queue_review_loader.has_pending_context(frm)) {
		await frappe.attachment_queue_review_loader.load();
	} else if (
		frm?.is_new?.() &&
		!frm.in_dialog &&
		frm.page &&
		(await frappe.attachment_queue_review_loader.is_upload_first_enabled(frm.doctype))
	) {
		await frappe.attachment_queue_review_loader.load();
	} else if (!frappe.attachment_queue_review?.refresh_form) {
		return;
	}

	frappe.attachment_queue_review.refresh_form(frm);
};

frappe.ui.form.on("*", {
	refresh(frm) {
		frappe.attachment_queue_review_loader.setup_form(frm);
	},
	// Written on every save, including to null. That is what bounds its lifetime:
	// a save that fails leaves its value behind, and the next save on this form
	// overwrites it before after_save can read it.
	before_save(frm) {
		frm.__attachment_queue_pending_link =
			frappe.attachment_queue_review?.get_pending_link?.(frm) || null;
	},
	after_save(frm) {
		if (frappe.attachment_queue_review?.link_after_save) {
			return frappe.attachment_queue_review.link_after_save(frm);
		}
	},
	on_submit(frm) {
		if (frappe.attachment_queue_review?.link_after_save) {
			return frappe.attachment_queue_review.link_after_save(frm);
		}
	},
});
