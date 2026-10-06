// Loaded only on phone-sized screens (see frappe/ui/mobile_nav.js), so a desktop never
// downloads Vue or the element. Vue comes first: the prebuilt element reads frappe.Vue
// as it loads.
import "./frappe/vue_global.js";
import "./lib/frappe-mobile-nav.js";
