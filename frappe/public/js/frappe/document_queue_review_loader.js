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

frappe.document_queue_review_loader.is_upload_first_enabled = async function (doctype, frm) {
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
	} catch (e) {
		return false;
	}
};

frappe.document_queue_review_loader.setup_form = async function (frm) {
	if (frappe.document_queue_review_loader.has_pending_context(frm)) {
		await frappe.document_queue_review_loader.load();
		frappe.document_queue_review.refresh_form(frm);
		return;
	}

	if (!frm?.is_new?.() || frm.in_dialog || !frm.page) {
		return;
	}

	const enabled = await frappe.document_queue_review_loader.is_upload_first_enabled(frm.doctype, frm);
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
			// Preserve queue_name across save so link_after_save can read it post-reload
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
