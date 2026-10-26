import { safe_href } from "../ui/components/utils.js";
import { queued_file_name } from "../utils/queued_file.js";

frappe.provide("frappe.ui.form.upload_first_review");

const QUEUE_DOCTYPE = "Attachment Queue";

// The unsaved document each entry is being written into, by entry name. Picking an
// entry up again returns to that document instead of starting a new one, so a
// half-filled form is not thrown away. Unsaved documents live in `locals` for the
// session, the same as one started from "Add <DocType>".
const documents_in_progress = {};

/**
 * Write a new document of the entry's DocType beside the file it is written from:
 * the form on the left, the file on the right. Saving the document files the entry
 * against it.
 * @param {Object} entry an Attachment Queue row, with name, document_type and source_file
 */
frappe.ui.form.upload_first_review.start = function (entry) {
	// one-shot hooks that the next form to load, and then to save, picks up
	frappe.route_hooks.after_load = (frm) => frappe.ui.form.upload_first_review.open(frm, entry);
	frappe.route_hooks.after_save = (frm) => file_entry_against(frm);

	frappe.model.with_doctype(entry.document_type, () => {
		// The document has to exist before the entry goes into route_options, since
		// creating it consumes them (see frappe.model.get_new_doc).
		const docname = document_for(entry);

		// The route carries the entry, so the file can be put back beside the form
		// from the URL alone — however the page got there, and whatever clears the
		// pane in between. Read back in Form.show_upload_first_review().
		frappe.route_options = { attachment_queue: entry.name };
		frappe.set_route("Form", entry.document_type, docname);
	});
};

/**
 * The document the entry is written into: the one already being filled in, or a new
 * one. Mandatory child rows are created the same way "Add <DocType>" creates them.
 */
function document_for(entry) {
	const started = documents_in_progress[entry.name];
	const doc = started && frappe.get_doc(entry.document_type, started);
	if (doc && doc.__islocal) return started;

	documents_in_progress[entry.name] = frappe.model.make_new_doc_and_get_name(
		entry.document_type,
		true
	);
	return documents_in_progress[entry.name];
}

/**
 * Open the file beside the form, which is the review: the attachment preview pane
 * narrows the form to make room and takes the sidebar's place.
 * @param {frappe.ui.form.Form} frm the form the document is written in
 * @param {Object} entry the Attachment Queue row being written from
 */
frappe.ui.form.upload_first_review.open = function (frm, entry) {
	// source_file is an Attach field, so it can hold any URL its uploader typed
	const file_url = safe_href(entry.source_file, "upload_first_review");
	if (!frm.attachments || !file_url) return;

	// a review already running for this document keeps the reader's own decisions,
	// such as having closed the file
	const running = frm.upload_first_review;
	if (!running || running.docname !== frm.docname || running.entry.name !== entry.name) {
		frm.upload_first_review = { entry, file_url, docname: frm.docname, closed: false };
	}

	open_pane(frm);
	keep_open_across_refreshes(frm);
};

function open_pane(frm) {
	const review = frm.upload_first_review;
	if (review.closed) return;

	// a no-op while the pane already holds this file, so the file is never reloaded
	frm.attachments.show_attachment_preview(
		{ file_name: queued_file_name(review.entry.source_file) },
		review.file_url
	);

	const $pane = frm.attachments.attachment_preview;
	$pane.addClass("upload-first-review");

	// The reader closing the file ends the review; anything else that drops the pane
	// (a form render, a route change clearing it) does not, so it is put back.
	$pane
		.find(".attachment-preview-close")
		.off("click.upload_first_review")
		.on("click.upload_first_review", () => end_review(frm));

	// the pane's own Escape handler closes it without going through that button
	$(document)
		.off("keydown.upload_first_review")
		.on("keydown.upload_first_review", (event) => {
			if (event.key === "Escape" && !$pane.hasClass("hidden")) end_review(frm);
		});
}

/**
 * The pane is dropped by anything that rebuilds the form's sidebar or clears the
 * preview (a failed save re-renders the form; a route change empties it), so take
 * the file back after every render until the review is over.
 */
function keep_open_across_refreshes(frm) {
	$(document)
		.off("form-refresh.upload_first_review")
		.on("form-refresh.upload_first_review", (event, refreshed) => {
			const review = frm.upload_first_review;
			if (refreshed !== frm || !review) return;

			// the review ends with the document it produced
			if (frm.doc.docstatus !== 0) return end_review(frm);

			// The form object is shared by every document of its DocType, so another
			// document in it is not the one being reviewed.
			if (frm.docname !== review.docname) return;

			open_pane(frm);
		});
}

/** Close the split screen and leave the form as it would be without a review. */
function end_review(frm) {
	const review = frm.upload_first_review;
	if (review) review.closed = true;

	$(document).off("form-refresh.upload_first_review");
	$(document).off("keydown.upload_first_review");
	frm.attachments && frm.attachments.hide_attachment_preview();
}

/** Hand the saved document to the entry, which attaches the file to it. */
function file_entry_against(frm) {
	const review = frm.upload_first_review;
	// after_save is a global hook, taken by whichever form saves first — only the
	// form this review opened carries it
	if (!review || review.entry.created_document) return;

	// The save renamed the document, and the file beside it has not changed. Whether
	// the render after the save ran before this hook or after it, the pane ends up
	// holding the file under the document's saved name.
	review.docname = frm.docname;
	if (frm.attachments) {
		frm.attachments.attachment_preview.attr("data-docname", frm.docname);
		open_pane(frm);
	}

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
			// the document is no longer one being filled in
			delete documents_in_progress[review.entry.name];
			// the file is attached to the document now, so the sidebar can list it
			frm.attachments && frm.attachments.refresh();
			frappe.show_alert({
				message: __("{0} filed against {1}", [
					queued_file_name(review.entry.source_file),
					frm.docname,
				]),
				indicator: "green",
			});
		});
}
