import web_form_source_doctype from "./web_form_source_doctype";

// middle_note is one Tab Break from first_note and one Section Break from last_note;
// spare_note stays unticked, as ticking everything rebuilds the layout instead
export default {
	...web_form_source_doctype,
	name: "Web Form Tabbed Source",
	autoname: "format:WFT-{####}",
	fields: [
		{ fieldname: "first_note", fieldtype: "Data", label: "First Note" },
		{ fieldname: "second_tab", fieldtype: "Tab Break", label: "Second" },
		{ fieldname: "middle_note", fieldtype: "Data", label: "Middle Note" },
		{ fieldname: "last_section", fieldtype: "Section Break", label: "Last" },
		{ fieldname: "last_note", fieldtype: "Data", label: "Last Note" },
		{ fieldname: "spare_note", fieldtype: "Data", label: "Spare Note" },
	],
};
