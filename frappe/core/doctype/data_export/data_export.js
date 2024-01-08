// Copyright (c) 2018, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Data Export", {
	refresh: (frm) => {
		frm.disable_save();
		frm.page.set_primary_action("Export", () => {
			can_export(frm) ? export_data(frm) : null;
		});
	},
	onload: (frm) => {
		frm.set_query("reference_doctype", () => {
			return {
				filters: {
					issingle: 0,
					istable: 0,
					name: ["in", frappe.boot.user.can_export],
				},
			};
		});
	},
	reference_doctype: (frm) => {
		const doctype = frm.doc.reference_doctype;
		if (doctype) {
			frappe.model.with_doctype(doctype, () => set_field_options(frm));
		} else {
			reset_filter_and_field(frm);
		}
	},
});

const can_export = (frm) => {
	const doctype = frm.doc.reference_doctype;
	const parent_multicheck_options = frm.fields_multicheck[doctype]
		? frm.fields_multicheck[doctype].get_checked_options()
		: [];
	let is_valid_form = false;
	if (!doctype) {
		frappe.msgprint(__("Please select the Document Type."));
	} else if (!parent_multicheck_options.length) {
		frappe.msgprint(__("Atleast one field of Parent Document Type is mandatory"));
	} else {
		is_valid_form = true;
	}
	return is_valid_form;
};

const export_data = (frm) => {
	let get_template_url = "/api/method/frappe.core.doctype.data_export.exporter.export_data";
	var export_params = () => {
		let columns = {};
		Object.keys(frm.fields_multicheck).forEach((dt) => {
			const options = frm.fields_multicheck[dt].get_checked_options();
			columns[dt] = options;
		});
		return {
			doctype: frm.doc.reference_doctype,
			select_columns: JSON.stringify(columns),
			filters: frm.filter_list.get_filters().map((filter) => filter.slice(1, 4)),
			file_type: frm.doc.file_type,
			template: true,
			with_data: 1,
		};
	};

	open_url_post(get_template_url, export_params());
};

const reset_filter_and_field = (frm) => {
	const parent_wrapper = frm.fields_dict.fields_multicheck.$wrapper;
	const filter_wrapper = frm.fields_dict.filter_list.$wrapper;
	parent_wrapper.empty();
	filter_wrapper.empty();
	frm.filter_list = [];
	frm.fields_multicheck = {};
};

const set_field_options = (frm) => {
	const parent_wrapper = frm.fields_dict.fields_multicheck.$wrapper;
	const filter_wrapper = frm.fields_dict.filter_list.$wrapper;
	const doctype = frm.doc.reference_doctype;
	const related_doctypes = get_doctypes(doctype);

	parent_wrapper.empty();
	filter_wrapper.empty();

	frm.filter_list = new frappe.ui.FilterGroup({
		parent: filter_wrapper,
		doctype: doctype,
		on_change: () => {},
	});

	// Add 'Select All' and 'Unselect All' button
	make_multiselect_buttons(parent_wrapper);

	frm.fields_multicheck = {};
	related_doctypes.forEach((dt) => {
		frm.fields_multicheck[dt] = add_doctype_field_multicheck_control(dt, parent_wrapper);
	});

	frm.refresh();
};

const make_multiselect_buttons = (parent_wrapper) => {
	const button_container = $(parent_wrapper).append('<div class="flex"></div>').find(".flex");

	["Select All", "Unselect All"].map((d) => {
		frappe.ui.form.make_control({
			parent: $(button_container),
			df: {
				label: __(d),
				fieldname: frappe.scrub(d),
				fieldtype: "Button",
				click: () => {
					checkbox_toggle(d !== "Select All");
				},
			},
			render_input: true,
		});
	});

	$(button_container)
		.find(".frappe-control")
		.map((index, button) => {
			$(button).css({ "margin-right": "1em" });
		});

	function checkbox_toggle(checked) {
		$(parent_wrapper)
			.find('[data-fieldtype="MultiCheck"]')
			.map((index, element) => {
				$(element).find(`:checkbox`).prop("checked", checked).trigger("click");
			});
	}
};

const get_doctypes = (parentdt) => {
	return [parentdt].concat(frappe.meta.get_table_fields(parentdt).map((df) => df.options));
};

const add_doctype_field_multicheck_control = (doctype, parent_wrapper) => {
	const fields = get_fields(doctype);

	frappe.model.std_fields
		.filter((df) => ["owner", "creation"].includes(df.fieldname))
		.forEach((df) => {
			fields.push(df);
		});

	const options = fields.map((df) => {
		return {
			label: df.label,
			value: df.fieldname,
			danger: df.reqd,
			checked: 1,
		};
	});

	const multicheck_control = frappe.ui.form.make_control({
		parent: parent_wrapper,
		df: {
			label: doctype,
			fieldname: doctype + "_fields",
			fieldtype: "MultiCheck",
			options: options,
			columns: 3,
		},
		render_input: true,
	});

	multicheck_control.refresh_input();
	return multicheck_control;
};

const filter_fields = (df) => frappe.model.is_value_type(df) && !df.hidden;
const get_fields = (dt) => frappe.meta.get_docfields(dt).filter(filter_fields);
