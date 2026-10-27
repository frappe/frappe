frappe.provide("frappe.ui.form");

const QUEUE_DOCTYPE = "Attachment Queue";
const SUPPORTED_FILE_TYPES = [".pdf", ".jpg", ".jpeg", ".png"];

/**
 * Upload files for a DocType that allows the upload-first workflow and queue each
 * file to be written into a document of that DocType.
 */
frappe.ui.form.upload_first = function (document_type) {
	new frappe.ui.FileUploader({
		dialog_title: __("Upload files for {0}", [__(document_type)]),
		upload_notes: __("PDFs and images only."),
		folder: "Home/Attachments",
		allow_toggle_private: false,
		disable_file_browser: true,
		restrictions: { allowed_file_types: SUPPORTED_FILE_TYPES },

		on_success: (file_doc) => {
			frappe.db
				.insert({
					doctype: QUEUE_DOCTYPE,
					document_type: document_type,
					source_file: file_doc.file_url,
				})
				.then(({ name }) =>
					frappe.db.set_value("File", file_doc.name, {
						attached_to_doctype: QUEUE_DOCTYPE,
						attached_to_name: name,
					})
				)
				.then(() =>
					frappe.show_alert({
						message: __("{0} queued for {1}", [
							file_doc.file_name,
							__(document_type),
						]),
						indicator: "green",
					})
				)
				.catch((error) => {
					console.error(
						"Failed to queue uploaded file:",
						file_doc.file_name,
						error
					);

					frappe.msgprint({
						title: __("Queueing Failed"),
						message: __(
							"The file {0} was uploaded but could not be added to the queue. Please try again.",
							[file_doc.file_name]
						),
						indicator: "red",
					});
				});
		},
	});
};