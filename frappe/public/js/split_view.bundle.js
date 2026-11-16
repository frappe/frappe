// Lazy bundle for the Split list view and the frappe.ui.SplitPane and frappe.ui.DetailLoader it
// is built on. They are kept out of the eager desk bundles and pulled in with
// frappe.require("split_view.bundle.js"): the list factory does so when a split view opens, and
// any other page that uses SplitPane or DetailLoader does so before it builds one.
import "./frappe/ui/components/split_pane.js";
import "./frappe/ui/components/detail_loader.js";
import "./frappe/views/split/split_view.js";
import "./frappe/views/split/split_preview.js";
