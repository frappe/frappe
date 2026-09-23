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
		})
		.catch((error) => {
			frappe.attachment_queue_review_loader.loading = null;
			throw error;
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

frappe.attachment_queue_review_loader.is_upload_first_enabled = async function (doctype) {
	if (!doctype || doctype === "Attachment Queue") {
		return false;
	}

	const meta = frappe.get_meta(doctype);

	return !!meta && !!cint(meta.enable_upload_first_workflow) && !cint(meta.istable);
};

// Handles the review flow on form refresh and decides when to load and refresh it.
frappe.attachment_queue_review_loader.setup_form = async function (frm) {
	try {
		if (frappe.attachment_queue_review_loader.has_pending_context(frm)) {
			await frappe.attachment_queue_review_loader.load();
		} else if (
			frm.is_new() &&
			frm.page &&
			(await frappe.attachment_queue_review_loader.is_upload_first_enabled(frm.doctype))
		) {
			await frappe.attachment_queue_review_loader.load();
		} else if (!frappe.attachment_queue_review?.refresh_form) {
			return;
		}
	} catch (error) {
		frappe.msgprint("Attachment Queue Review: failed to load", error);
		frappe.show_alert({
			message: __(
				"Could not load the document review feature. Please refresh the page and try again."
			),
			indicator: "red",
		});
		return;
	}
	frappe.attachment_queue_review.refresh_form(frm);
};

frappe.ui.form.on("*", {
	refresh(frm) {
		frappe.attachment_queue_review_loader.setup_form(frm).catch((error) => {
			console.error("Attachment Queue Review: setup failed", error);
		});
	},
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
