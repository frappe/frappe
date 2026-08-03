import { list_view_virtualization } from "./frappe/list/list_view_virtualization.js";

frappe.provide("frappe.views");
Object.assign(frappe.views.ListView.prototype, list_view_virtualization);
