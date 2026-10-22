frappe.provide("frappe.ui.attachment_queue");

const QUEUE_DOCTYPE = "Attachment Queue";
const PAGE_SIZE = 20;

/**
 * List the files queued for a DocType that no document has been written from yet,
 * newest first. Paged from the server, so a long queue loads one page at a time.
 */
frappe.ui.attachment_queue.show_pending = function (document_type) {
	const dialog = new frappe.ui.Dialog({
		title: __("Documents for Review"),
		size: "large",
		fields: [{ fieldtype: "HTML", fieldname: "pending" }],
	});
	dialog.show();

	const $list = $('<div class="attachment-queue-pending"></div>').appendTo(
		dialog.fields_dict.pending.$wrapper
	);

	frappe
		.require("embedded_list.bundle.js")
		.then(() => {
			new frappe.ui.EmbeddedList({
				wrapper: $list,
				show_search: false,
				page_size: PAGE_SIZE,
				empty_icon: "file-text",
				empty_message: __("No files are waiting for review."),
				get_page: ({ start, page_length }) =>
					frappe.db.get_list(QUEUE_DOCTYPE, {
						fields: ["name", "source_file", "owner", "creation"],
						filters: { document_type, created_document: ["is", "not set"] },
						order_by: "creation desc",
						start,
						limit: page_length,
					}),
				columns: [
					{
						label: __("File"),
						type: "link",
						fieldname: "source_file",
						text: (row) => get_file_name(row.source_file),
						url: (row) => row.source_file,
					},
					{
						label: __("Uploaded By"),
						render: (row) =>
							frappe.utils.escape_html(frappe.user.full_name(row.owner)),
					},
					{
						label: __("Uploaded"),
						render: (row) => comment_when(row.creation),
					},
				],
			}).refresh();
		})
		.catch((e) => {
			// a failed lazy load must not leave the dialog silently blank
			console.error("Attachment Queue: failed to load embedded_list.bundle.js", e);
			dialog.hide();
			frappe.ui.toast({
				message: __("Could not load this list. Please refresh the page."),
				type: "error",
			});
		});
};

function get_file_name(file_url) {
	return decodeURIComponent(file_url.split("?", 1)[0].split("/").pop());
}
