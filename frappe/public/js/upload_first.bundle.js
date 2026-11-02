// On-demand bundle for the upload-first workflow.
//
// Only reached from the list view's "Create from File" menu item, so it stays out
// of desk.bundle.js and loads via `frappe.require("upload_first.bundle.js")` the
// first time that item is clicked (see list/list_view.js).
import "./frappe/form/upload_first.js";
