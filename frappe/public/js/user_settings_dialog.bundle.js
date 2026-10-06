// Lazy bundle for frappe.ui.show_user_settings — the user Settings dialog is
// only opened on demand (from the sidebar user menu), so it's kept out of the
// eager desk bundle and pulled in with
// frappe.require("user_settings_dialog.bundle.js").
import "./frappe/ui/user_settings_dialog.js";
