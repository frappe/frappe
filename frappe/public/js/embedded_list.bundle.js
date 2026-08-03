// Lazy bundle for frappe.ui.EmbeddedList — it's a feature component used in
// only a few places (the DocType Settings dialog, the Role form), so it's
// kept out of the eager desk bundle and pulled in on demand with
// frappe.require("embedded_list.bundle.js").
import "./frappe/ui/embedded_list.js";
