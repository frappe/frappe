// Desk's Vue, shared with prebuilt app bundles that mark `vue` as external
// (e.g. frappe-ui's <frappe-mobile-nav>) so they don't ship their own copy.
// Imported near the top of desk.bundle.js so it is set even if a later module
// throws during load.
import * as Vue from "vue";

frappe.Vue = Vue;
