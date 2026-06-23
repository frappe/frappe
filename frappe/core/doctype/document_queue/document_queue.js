frappe.provide("frappe.document_queue");

frappe.document_queue.review_script_url =
	"/assets/frappe/js/frappe/document_queue_review.js?v=document-queue-review-20260623-22";
frappe.document_queue.review_script_fallback_url =
	"/assets/frappe/js/frappe/document_queue_review.js";
frappe.document_queue.reviewable_statuses = ["Ready for Review", "Failed"];

frappe.document_queue.load_review_script = function (url) {
	return new Promise((resolve, reject) => {
		const script = document.createElement("script");
		script.src = url;
		script.onload = resolve;
		script.onerror = reject;
		document.head.appendChild(script);
	});
};

frappe.document_queue.start_review = function (frm) {
	const start_review = () => {
		if (!frappe.document_queue_review?.start_from_document_queue) {
			frappe.msgprint(
				__("Document review script could not be loaded. Please refresh and try again.")
			);
			return;
		}

		frappe.document_queue_review.start_from_document_queue(frm);
	};

	if (frappe.document_queue_review?.start_from_document_queue) {
		start_review();
		return;
	}

	frappe.document_queue
		.load_review_script(frappe.document_queue.review_script_url)
		.then(start_review)
		.catch(() => {
			frappe.document_queue
				.load_review_script(frappe.document_queue.review_script_fallback_url)
				.then(start_review)
				.catch(() => {
					frappe.msgprint(
						__(
							"Document review script could not be loaded. Please refresh and try again."
						)
					);
				});
		});
};

frappe.ui.form.on("Document Queue", {
	setup(frm) {
		frm.set_query("document_type", () => ({
			filters: {
				enable_upload_first_workflow: 1,
				istable: 0,
			},
		}));
	},

	refresh(frm) {
		if (
			!frm.is_new() &&
			frm.doc.source_file &&
			!["Queued", "Processing"].includes(frm.doc.status)
		) {
			frm.add_custom_button(__("Extract"), () => {
				frm.call("extract_in_background").then(() => frm.reload_doc());
			});
		}

		if (
			!frm.is_new() &&
			frm.doc.source_file &&
			frappe.document_queue.reviewable_statuses.includes(frm.doc.status)
		) {
			frm.add_custom_button(__("Start Review"), () => {
				frappe.document_queue.start_review(frm);
			});
		}

		if (frm.doc.task) {
			frm.add_custom_button(__("View Background Task"), () => {
				frappe.set_route("Form", "Background Task", frm.doc.task);
			});
		}
	},
});
