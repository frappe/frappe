import web_form_source_doctype from "./web_form_source_doctype";

// nothing here survives get_fields_for_doctype: Heading and Button carry no value and a
// Section Break is layout, so the picker has nothing to offer
export default {
	...web_form_source_doctype,
	name: "Web Form Empty Source",
	autoname: "format:WFE-{####}",
	fields: [
		{ fieldname: "details_section", fieldtype: "Section Break", label: "Details" },
		{ fieldname: "details_heading", fieldtype: "Heading", label: "Details" },
		{ fieldname: "run_action", fieldtype: "Button", label: "Run Action" },
	],
};
