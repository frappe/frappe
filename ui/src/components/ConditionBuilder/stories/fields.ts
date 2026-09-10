import type { ConditionField } from "../types";

/**
 * A sample field list shared by the stories, in the shape the built-in leaf
 * takes, the shape `getFilterableFields` derives from doctype Meta,
 * so `options` is Frappe's newline-joined string rather than an array.
 */
export const sampleFields: ConditionField[] = [
  {
    label: "Subject",
    value: "subject",
    fieldname: "subject",
    fieldtype: "Data",
  },
  {
    label: "Status",
    value: "status",
    fieldname: "status",
    fieldtype: "Select",
    options: "Open\nReplied\nClosed",
  },
  {
    label: "Priority",
    value: "priority",
    fieldname: "priority",
    fieldtype: "Select",
    options: "Low\nMedium\nHigh",
  },
  // Here for the fieldname that overrides its operators.
  {
    label: "Assigned To",
    value: "_assign",
    fieldname: "_assign",
    fieldtype: "Text",
  },
  {
    label: "Created By",
    value: "owner",
    fieldname: "owner",
    fieldtype: "Link",
    options: "User",
  },
  { label: "Rating", value: "rating", fieldname: "rating", fieldtype: "Rating" },
  {
    label: "Resolved",
    value: "resolved",
    fieldname: "resolved",
    fieldtype: "Check",
  },
  {
    label: "Created On",
    value: "creation",
    fieldname: "creation",
    fieldtype: "Datetime",
  },
];
