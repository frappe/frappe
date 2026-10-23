import { safe_href } from "../ui/components/utils.js";
import { queued_file_name } from "../utils/queued_file.js";

frappe.provide("frappe.ui.form");

const QUEUE_DOCTYPE = "Attachment Queue";

/**
 * Write a new document of the entry's DocType beside the file it is written from:
 * the form on the left, the file on the right. Saving the document files the entry
 * against it.
 * @param {Object} entry an Attachment Queue row, with name, document_type and source_file
 */
frappe.ui.form.upload_first_review = function (entry) {
	const review = { entry, file_url: safe_href(entry.source_file, "upload_first_review") };

	// one-shot hooks that the next form to load, and then to save, picks up
	frappe.route_hooks.after_load = (frm) => setup_review(frm, review);
	frappe.route_hooks.after_save = (frm) => file_entry_against(frm, review);

	frappe.model.with_doctype(entry.document_type, () => {
		frappe.set_route(
			"Form",
			entry.document_type,
			frappe.model.make_new_doc_and_get_name(entry.document_type)
		);
	});
};

/** Mark the form as the one this entry is written into, and open the file beside it. */
function setup_review(frm, review) {
	if (!frm.attachments || !review.file_url) return;

	review.docname = frm.docname;
	frm.upload_first_review = review; // It attaches the review object to the JavaScript Form object.
	open_file_pane(frm, review);

	// render_form() builds a new sidebar on every refresh, which empties the section
	// the pane lives in — closing a link field's quick entry dialog is enough to do
	// it. Put the file back once the new sidebar is in place.
	$(document)
		.off("form-refresh.upload_first_review")
		.on("form-refresh.upload_first_review", (event, refreshed) => reopen_pane(refreshed, frm));
}

function reopen_pane(refreshed, frm) {
	const review = frm.upload_first_review;
	if (refreshed !== frm || !review) return;

	// The form object is shared by every document of its DocType, so another
	// document in it is not the one being reviewed — leave that one a plain,
	// full-width form.
	if (frm.docname !== review.docname) {
		frm.attachments && frm.attachments.hide_attachment_preview();
		return;
	}

	// the pane marks the page while it is open, and only the user closing it clears
	// that — so this tells a wiped pane apart from one that was dismissed
	if (!frm.page.wrapper.hasClass("attachment-preview-open")) return;

	open_file_pane(frm, review);
}

/**
 * The form sidebar's preview pane is the split screen: opening it narrows the form
 * to make room and puts the file where the sidebar was.
 */
function open_file_pane(frm, review) {
	frm.attachments.show_attachment_preview(
		{ file_name: queued_file_name(review.entry.source_file) },
		review.file_url
	);
	frm.attachments.attachment_preview.addClass("upload-first-review");
}

/** Close the split screen and leave the form as it would be without a review. */
function end_review(frm) {
	frm.upload_first_review = null;
	$(document).off("form-refresh.upload_first_review");
	if (frm.attachments) {
		frm.attachments.hide_attachment_preview();
		// the file is attached to the document now, so the sidebar can list it
		frm.attachments.refresh();
	}
}

/** Hand the saved document to the entry, which attaches the file to it. */
function file_entry_against(frm, review) {
	// after_save is a global hook, taken by whichever form saves first — only the
	// form this review opened carries it
	if (frm.upload_first_review !== review || review.entry.created_document) return;

	return frappe
		.xcall("run_doc_method", {
			dt: QUEUE_DOCTYPE,
			dn: review.entry.name,
			method: "link_to_document",
			args: { document_name: frm.docname },
		})
		.then(() => {
			// filed, so a later save does not claim it again
			review.entry.created_document = frm.docname;
			review.docname = frm.docname;

			// The review ends with the document it produced: the split screen closes
			// and the form goes back to full width, with the file now listed in the
			// sidebar like any other attachment.
			end_review(frm);
			frappe.show_alert({
				message: __("{0} filed against {1}", [
					queued_file_name(review.entry.source_file),
					frm.docname,
				]),
				indicator: "green",
			});
		});
}
