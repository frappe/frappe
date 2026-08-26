// On-demand bundle for the DocType Settings dialog.
//
// Kept out of the always-loaded default bundles (desk/form/…) because the whole
// feature — every tab plus its registry/list panel — is only reached from the
// form toolbar's "Settings" menu item and would otherwise cost ~40 KB on every
// desk pageload. Loaded lazily via `frappe.require("doctype_settings.bundle.js")`
// the first time that menu item is clicked (see form/toolbar.js).
//
// Note: the generic `frappe.ui.SettingsDialog` primitive stays in desk.bundle.js
// (it's reused elsewhere); doctype_settings.js references it as a global, which is
// safe because desk.bundle.js always loads before this on-demand bundle runs.
// permission_dialog.js likewise stays in desk.bundle.js — role.js relies on
// `frappe.perm_editor` being globally available; the permissions tab uses that global.
import "./frappe/form/doctype_settings/doctype_settings.js";
