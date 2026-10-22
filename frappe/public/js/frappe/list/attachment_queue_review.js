import { safe_href } from "../ui/components/utils.js";

frappe.provide("frappe.ui.attachment_queue");

const QUEUE_DOCTYPE = "Attachment Queue";
const PAGE_SIZE = 20;

/**
 * List the files queued for a DocType that no document has been written from yet,
 * newest first, and preview the selected one beside the list. Paged from the
 * server, so a long queue loads one page at a time.
 */
frappe.ui.attachment_queue.show_pending = function (document_type) {
	let selected = null;
	let list = null;

	const dialog = new frappe.ui.Dialog({
		title: __("Documents for Review"),
		size: "extra-large",
		fields: [{ fieldtype: "HTML", fieldname: "pending" }],
		primary_action_label: __("Ready to Review"),
		primary_action: () => frappe.ui.attachment_queue.start_review(selected, dialog),
	});
	// there is nothing to review until a file is picked
	dialog.disable_primary_action();
	dialog.show();

	const $panes = $(`
		<div class="attachment-queue-review flex gap-4 min-h-80">
			<div class="attachment-queue-review-list flex-1 min-w-0 overflow-y-auto"></div>
			<div class="flex-1 min-w-0 flex flex-col overflow-hidden rounded-md border border-outline-gray-1 bg-surface-base">
				<div class="attachment-queue-review-preview-header hidden shrink-0 flex items-center justify-between gap-2 border-b border-outline-gray-1 bg-surface-gray-2 ps-3 pe-1 py-1.5">
					<div class="truncate attachment-queue-review-preview-title"></div>
					<a class="es-button" data-variant="ghost" data-icon-button="true"
						target="_blank" rel="noopener noreferrer"
						title="${__("Open file in new tab")}"
						aria-label="${__("Open file in new tab")}"
					>${frappe.utils.icon("arrow-up-right", "sm", "", "", "", true)}</a>
				</div>
				<div class="attachment-queue-review-preview-body flex-1 min-h-0 flex items-center justify-center overflow-auto"></div>
			</div>
		</div>
	`).appendTo(dialog.fields_dict.pending.$wrapper);

	const $preview_header = $panes.find(".attachment-queue-review-preview-header");
	const $preview_body = $panes.find(".attachment-queue-review-preview-body");

	$preview_body.append(
		frappe.ui.empty_state({
			icon: "file-text",
			title: __("Select a file to preview it"),
		})
	);

	const show_preview = (entry) => {
		const file_name = get_file_name(entry.source_file);
		// source_file is an Attach field, so it can hold any URL its uploader typed
		const file_url = safe_href(entry.source_file, "attachment_queue");

		$preview_header
			.removeClass("hidden")
			.find(".attachment-queue-review-preview-title")
			.text(file_name)
			.attr("title", file_name);
		$preview_header.find("a").attr("href", file_url);

		if (!file_url) {
			$preview_body.empty().append(
				frappe.ui.empty_state({
					icon: "circle-x",
					title: __("This file cannot be previewed"),
				})
			);
			return;
		}

		// the queue only takes PDFs and images, so anything not an image is a PDF
		const $file = frappe.utils.is_image_file(file_url)
			? $("<img loading='lazy'>").attr({ src: file_url, alt: file_name })
			: $("<iframe>").attr({ src: file_url, title: file_name });
		$preview_body.empty().append($file);
	};

	// The selected row keeps its index while Load More appends to the page, so
	// marking it by index holds until the list is rendered from scratch.
	const mark_selected_row = () => {
		list.$result.find("tr[data-row-idx]").removeClass("selected");
		if (!selected) return;

		const index = list.data.findIndex((row) => row.name === selected.name);
		if (index >= 0) {
			list.$result.find(`tr[data-row-idx="${index}"]`).addClass("selected");
		}
	};

	const select = (entry) => {
		selected = entry;
		dialog.enable_primary_action();
		mark_selected_row();
		show_preview(entry);
	};

	frappe
		.require("embedded_list.bundle.js")
		.then(() => {
			list = new frappe.ui.EmbeddedList({
				wrapper: $panes.find(".attachment-queue-review-list"),
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
						fieldname: "source_file",
						render: (row) => frappe.utils.escape_html(get_file_name(row.source_file)),
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
				on_row_click: select,
				after_render: () => mark_selected_row(),
			});
			list.refresh();
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

/**
 * Open the picked entry for review. The split-screen review workflow replaces this.
 * @param {Object} entry the selected Attachment Queue row
 * @param {frappe.ui.Dialog} dialog the dialog it was picked in
 */
frappe.ui.attachment_queue.start_review = function (entry, dialog) {
	dialog.hide();
	frappe.show_alert({
		message: __("Review of {0} is not available yet.", [get_file_name(entry.source_file)]),
		indicator: "orange",
	});
};

function get_file_name(file_url) {
	return decodeURIComponent(file_url.split("?", 1)[0].split("/").pop());
}
