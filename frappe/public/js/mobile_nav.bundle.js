// Loaded only on phone-sized screens (see frappe/ui/mobile_nav.js), so a desktop never
// downloads Vue or the elements. Vue comes first: the prebuilt elements read frappe.Vue
// as they load.
import "./frappe/vue_global.js";
import "./lib/frappe-mobile-nav.js";
import "./lib/frappe-bottom-sheet.js";
