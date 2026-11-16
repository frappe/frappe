// On-demand bundle for the split-screen review of a queued file.
//
// Only reached from "Process" in the pending-documents dialog, so it stays
// out of desk.bundle.js and loads via
// frappe.require("upload_first_review.bundle.js") on the first click
// (see list/attachment_queue_review.js).
import "./frappe/form/upload_first_review.js";
