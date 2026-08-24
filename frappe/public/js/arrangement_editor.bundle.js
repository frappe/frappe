// On-demand bundle for the arrangement editor and the two surfaces built on it.
//
// Nothing here runs until somebody opens a menu and asks to arrange something --
// "Manage Dock" in the user menu, "Edit Sidebar" in the sidebar header -- so the
// editor, the dock's manager and the sidebar's manager stay out of the eager desk
// bundle and are pulled in with frappe.require("arrangement_editor.bundle.js") at
// the click. Together they cost ~19 KB on every desk pageload otherwise.
//
// The base class comes first: both managers extend `frappe.ui.ArrangementEditor` at
// module evaluation, so it has to exist by the time they are read.
import "./frappe/ui/sidebar/arrangement_editor.js";
import "./frappe/ui/sidebar/dock_manager.js";
import "./frappe/ui/sidebar/sidebar_manager.js";
