// Desk's Vue, shared with prebuilt app bundles that mark `vue` as external
// (e.g. frappe-ui's <frappe-mobile-nav>) so they don't ship their own copy.
// Not in the default bundles: mobile_nav.bundle.js loads it on demand.
import * as Vue from "vue";

frappe.Vue = Vue;
