// On-demand bundle for the pending Attachment Queue dialog.
//
// Only reached from the "View All" button on the list view's review notice, so it
// stays out of desk.bundle.js and loads via
// frappe.require("attachment_queue_review.bundle.js") on the first click
// (see list/list_view.js).
import "./frappe/list/attachment_queue_review.js";
