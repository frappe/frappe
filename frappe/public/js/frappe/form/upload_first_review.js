import { safe_href } from "../ui/components/utils.js";
import { queued_file_name } from "../utils/queued_file.js";

frappe.provide("frappe.ui.form.upload_first_review");

const QUEUE_DOCTYPE = "Attachment Queue";
const EXTRACTION_EVENT = "attachment_queue_extraction";

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
	// a one-shot hook that the next form to load picks up
	frappe.route_hooks.after_load = (frm) => frappe.ui.form.upload_first_review.open(frm, entry);

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
	fill_from_file(frm);
};

/**
 * Put the values Flow read out of the file into the form. Read back from the entry rather
 * than carried on it, since the reading may have finished after the queue was listed.
 */
function fill_from_file(frm) {
	const review = frm.upload_first_review;
	if (!review || review.filled) return;

	frappe.db
		.get_value(QUEUE_DOCTYPE, review.entry.name, [
			"extraction_status",
			"extracted_values",
			"skipped_values",
			"extraction_error",
		])
		.then(({ message }) => {
			if (!message || frm.upload_first_review !== review || review.closed) return;

			if (message.extraction_status === "Started") return wait_for_file(frm);
			if (message.extraction_status === "Completed") {
				apply_values(frm, extracted_values(message.extracted_values));
				return report_skipped(frm, extracted_values(message.skipped_values));
			}

			// never read, or read and failed: either way, read it now
			read_file(frm, message.extraction_error);
		});
}

/**
 * Have Flow read the file, or say why it could not. Opening the review is the moment to
 * read a file that was never offered to Flow, and to try again after a failed read, whose
 * cause usually lies outside the file. Read once per review, so a file Flow cannot read
 * reports that instead of being sent again on every render.
 */
function read_file(frm, error) {
	const review = frm.upload_first_review;
	if (review.requested) return report_failure(frm, error);
	review.requested = true;

	frappe
		.xcall("frappe.core.doctype.attachment_queue.extraction.read_now", {
			entry: review.entry.name,
		})
		.then((status) => {
			if (frm.upload_first_review !== review || review.closed) return;
			if (status === "Started") return wait_for_file(frm);
			// the DocType does not ask for extraction, so the form is filled in by hand
			if (!status) return;
			fill_from_file(frm);
		})
		.catch(() => report_failure(frm, error));
}

/**
 * Say that the file could not be read, and why. The form is filled in by hand from here,
 * so an empty form with no explanation reads as the review being broken.
 */
function report_failure(frm, error) {
	const review = frm.upload_first_review;
	// reported once per document, so a render does not put the message back
	if (review.reported) return;
	review.reported = true;

	frappe.msgprint({
		title: __("Could Not Read This File"),
		message: [
			frappe.utils.escape_html(error || __("Flow did not say why.")),
			__("Fill in {0} from the file yourself.", [__(frm.doctype)]),
		].join("<br><br>"),
		indicator: "orange",
	});
}

function extracted_values(raw) {
	if (!raw) return {};
	if (typeof raw !== "string") return raw;
	try {
		return JSON.parse(raw);
	} catch (e) {
		// the form is still usable by hand, so a bad value is logged and skipped
		console.error("Attachment Queue: could not read the extracted values", e);
		return {};
	}
}

/**
 * The reading is still running, so wait for it instead of leaving the form empty. The
 * values arrive once, for this entry, while the review is open.
 */
function wait_for_file(frm) {
	const review = frm.upload_first_review;
	if (review.waiting) return;
	review.waiting = true;

	frappe.show_alert({
		message: __("Reading {0}. The form fills in once it is read.", [
			queued_file_name(review.entry.source_file),
		]),
		indicator: "blue",
	});

	// the reading is over either way: read the entry back and fill in or explain
	frappe.realtime.on(EXTRACTION_EVENT, ({ entry }) => {
		if (entry !== review.entry.name || review.closed) return;
		stop_waiting(review);
		fill_from_file(frm);
	});
}

function stop_waiting(review) {
	if (!review.waiting) return;
	review.waiting = false;
	frappe.realtime.off(EXTRACTION_EVENT);
}

/**
 * Fill in the fields the file states, leaving alone any the reader has already answered.
 * Only an unsaved document is filled: once saved, its values are the reader's.
 */
function apply_values(frm, values) {
	if (!frm.doc.__islocal) return;

	const filled = {};
	for (const [fieldname, value] of Object.entries(values)) {
		if (frm.get_field(fieldname) && !frm.doc[fieldname]) filled[fieldname] = value;
	}

	const fieldnames = Object.keys(filled);
	if (!fieldnames.length) return;

	// filled once, so a later render cannot put a value back over an edit
	frm.upload_first_review.filled = true;

	frm.set_value(filled).then(() => {
		fieldnames.forEach((fieldname) => mark_filled(frm, fieldname));
		frappe.show_alert({
			message: __("{0} fields filled in from the file. Check them before saving.", [
				fieldnames.length,
			]),
			indicator: "blue",
		});
	});
}

/**
 * List what the file stated that the document could not hold. Only the reader can act on
 * these — a supplier the file names but the site has no record of is theirs to create —
 * so dropping them silently leaves the form looking half read for no visible reason.
 */
function report_skipped(frm, skipped) {
	const review = frm.upload_first_review;
	const fieldnames = Object.keys(skipped || {});
	// its own flag: a read that failed and then succeeded still has these to report
	if (!fieldnames.length || review.listed) return;
	review.listed = true;

	const rows = fieldnames
		.map((fieldname) => {
			const { label, value, reason } = skipped[fieldname];
			return `<tr>
				<td>${frappe.utils.escape_html(label || fieldname)}</td>
				<td>${frappe.utils.escape_html(value)}</td>
				<td class="text-muted">${frappe.utils.escape_html(reason)}</td>
			</tr>`;
		})
		.join("");

	frappe.msgprint({
		title: __("Left Out of the Form"),
		message: `<p>${__("The file states these, but {0} cannot hold them as written.", [
			__(frm.doctype),
		])}</p>
			<table class="table table-bordered">
				<thead><tr>
					<th>${__("Field")}</th><th>${__("In the file")}</th><th>${__("Why")}</th>
				</tr></thead>
				<tbody>${rows}</tbody>
			</table>`,
		indicator: "orange",
	});
}

/** Show which fields came from the file, until the reader edits them. */
function mark_filled(frm, fieldname) {
	const field = frm.get_field(fieldname);
	if (!field || !field.$wrapper) return;

	field.$wrapper.addClass("filled-from-file");
	field.$wrapper.one("change input", () => field.$wrapper.removeClass("filled-from-file"));
}

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
	if (review) {
		review.closed = true;
		stop_waiting(review);
	}

	$(document).off("form-refresh.upload_first_review");
	$(document).off("keydown.upload_first_review");
	frm.attachments && frm.attachments.hide_attachment_preview();
	remove_entry_from_url();
}

/** Drop the entry from the route, so a reload does not open the file again. */
function remove_entry_from_url() {
	const url = new URL(window.location.href);
	url.searchParams.delete("attachment_queue");
	history.replaceState(history.state, "", url.toString());
}

/** Hand the saved document to the entry, which attaches the file to it. */
frappe.ui.form.upload_first_review.file = function (frm) {
	const review = frm.upload_first_review;
	if (review.entry.created_document) return;
	// the form is shared by every document of its DocType, so only the reviewed one files
	if (frm.docname !== (frappe.model.new_names[review.docname] || review.docname)) return;

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
			// the server attached the file, so fetch the attachments again for the sidebar
			frm.sidebar?.reload_docinfo();
			frappe.show_alert({
				message: __("{0} linked to {1}", [
					queued_file_name(review.entry.source_file),
					frm.docname,
				]),
				indicator: "green",
			});
		});
};
