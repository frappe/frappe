// Loaded only on phone-sized screens (see frappe/ui/mobile_nav_loader.js), so a desktop
// never downloads Vue, the element or the tab bar. Vue comes first: the prebuilt element
// reads frappe.Vue as it loads.
import "./frappe/vue_global.js";
import "./lib/frappe-mobile-nav.js";
import "./frappe/ui/mobile_nav.js";
