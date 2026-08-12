frappe.provide("frappe.document_queue");

frappe.document_queue.reviewable_statuses = ["Ready for Review", "Failed"];

frappe.document_queue.start_review = function (frm) {
	// The review module is lazy-loaded only when a review is started.
	// document_queue_review_loader owns that load (via frappe.require), so this
	// shares the framework's asset cache with the feature's other two call sites
	// — the form loader and list_view.js — instead of fetching the script again.
	return frappe.document_queue_review_loader
		.load()
		.then(() => {
			frappe.document_queue_review.start_from_document_queue(frm);
		})
		.catch(() => {
			frappe.msgprint(
				__("Document review script could not be loaded. Please refresh and try again.")
			);
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

		const dev_mode = cint(frappe.boot.developer_mode);
		if (!dev_mode) {
			frm.set_df_property("extracted_text_section", "hidden", 1);
			frm.set_df_property("raw_output_section", "hidden", 1);
			frm.set_df_property("error_section", "hidden", 1);
		} else {
			frm.set_df_property("extracted_text_section", "label", __("Debug: Extracted Text"));
			frm.set_df_property("raw_output_section", "label", __("Debug: Raw Output"));
			frm.set_df_property("error_section", "label", __("Debug: Errors"));
		}
	},
});
