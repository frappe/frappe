// for link titles
frappe._link_titles = {};

frappe.get_link_title = function(doctype, name) {
	if (!doctype || !name) {
		return;
	}

	return frappe._link_titles[doctype + "::" + name];
};

frappe.add_link_title = function (doctype, name, value) {
	if (!doctype || !name) {
		return;
	}

	frappe._link_titles[doctype + "::" + name] = value;
};

frappe.set_link_title =  function(f) {
	let doctype = f.get_options();
	let docname = f.get_input_value();

	if ((!in_list(frappe.boot.doctypes_with_show_link_field_title, doctype)) || (!doctype || !docname) ||
		(frappe.get_link_title(doctype, docname))) {
		return;
	}

	frappe.xcall("frappe.desk.search.get_link_title", {"doctype": doctype, "docname": docname}).then((r) => {
		if (r && docname !== r) {
			f.set_input_label(r);
		}
	});
};