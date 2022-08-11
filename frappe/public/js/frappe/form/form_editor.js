frappe.ui.form.FormEditor = class FormEditor {
	constructor({ frm }) {
		this.frm = frm;
	}

	setup() {
		this.setup_sortable();
		this.setup_switch_tabs_on_hover();
	}

	setup_sortable() {
		// setup sortable in all column
		for (let section of this.frm.layout.sections) {
			for (let column of section.columns) {
				column.make_sortable();
			}
		}
		// sortable for moving tabs
		if (this.frm.layout.tab_link_container) {
			this.tab_sortable = new Sortable(this.frm.layout.tab_link_container.get(0));
		}
	}

	setup_switch_tabs_on_hover() {
		for (let tab of this.frm.layout.tabs) {
			tab.setup_switch_on_hover();
		}
	}

	save() {
		this.field_order = [];
		if (this.frm.layout.is_tabbed_layout()) {
			for (let tab of this.frm.layout.tab_link_container.find(".nav-link")) {
				this.add_field_to_field_order(tab);
				const tab_id = tab.getAttribute("href").slice(1);

				this.add_sections(document.getElementById(tab_id));
			}
		} else {
			this.add_sections(this.frm.layout.page);
		}

		frappe
			.call("frappe.core.doctype.doctype.doctype.set_field_order", {
				doctype: this.frm.doctype,
				field_order: this.field_order,
			})
			.then(() => frappe.toast("Field order updated"));
	}

	add_sections(container) {
		for (let section of $(container).find(".form-section")) {
			this.add_field_to_field_order(section);
			for (let column of $(section).find(".form-column")) {
				this.add_field_to_field_order(column);

				for (let control of $(column).find(".frappe-control")) {
					this.add_field_to_field_order(control);
				}
			}
		}
	}

	rebuid_fields_list() {
		// rebuild the .fields_list and .fields_dict property of sections and columns
		// refresh is based on the these properties

		for (let section of this.frm.layout.sections) {
			section.rebuild_fields_list_from_dom();
		}
	}

	add_field_to_field_order(element) {
		const fieldname = element.getAttribute("data-fieldname");
		const fieldobj = this.frm.fields_dict[fieldname];
		const is_custom_field = fieldobj ? fieldobj.df && fieldobj.df.is_custom_field : false;
		if (fieldname && !is_custom_field && fieldname.substr(0, 2) !== "__") {
			this.field_order.push(fieldname);
		}
	}
};
