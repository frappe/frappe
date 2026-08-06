// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Automation Flow", {
	refresh: (frm) => frappe.automation_flow.setup_conditions(frm),
	document_type: (frm) => frappe.automation_flow.setup_conditions(frm),
});

frappe.provide("frappe.automation_flow");

Object.assign(frappe.automation_flow, {
	setup_conditions(frm) {
		const parent = frm.get_field("filters_editor").$wrapper.empty();
		this.render_conditions_intro(parent, frm.doc.document_type);
		if (!frm.doc.document_type) return;
		frappe.model.with_doctype(frm.doc.document_type, () =>
			this.make_filter_group(frm, parent)
		);
	},

	render_conditions_intro(parent, document_type) {
		const guidance = document_type
			? __("Add field rules below, every rule must match before the flow can run")
			: __("Select a Document Type to add field rules.");
		$(`<div class="mb-3">
			<label class="control-label">${__("Match Fields")}</label>
			<p class="text-muted small">${guidance}</p>
		</div>`).appendTo(parent);
	},

	make_filter_group(frm, parent) {
		const filter_group = new frappe.ui.FilterGroup({
			parent,
			doctype: frm.doc.document_type,
			on_change: () => this.store_filters(frm, filter_group),
		});
		frm.automation_filter_group = filter_group;
		filter_group.add_filters_to_filter_group(this.get_filters(frm));
	},

	store_filters(frm, filter_group) {
		frm.set_value("filters", JSON.stringify(filter_group.get_filters()));
	},

	get_filters(frm) {
		if (!frm.doc.filters) return [];
		try {
			return this.normalize_filters(JSON.parse(frm.doc.filters), frm.doc.document_type);
		} catch (error) {
			console.error("Unable to load Automation Flow filters", error);
			frappe.show_alert({
				message: __("Could not load the saved field rules"),
				indicator: "red",
			});
			return [];
		}
	},

	normalize_filters(filters, doctype) {
		if (Array.isArray(filters)) return this.normalize_filter_list(filters, doctype);
		return Object.entries(filters).map(([fieldname, value]) =>
			this.normalize_filter(doctype, fieldname, value)
		);
	},

	normalize_filter_list(filters, doctype) {
		const filter_list = typeof filters[0] === "string" ? [filters] : filters;
		return filter_list.map((filter) => {
			if (filter.length === 2) return [doctype, filter[0], "=", filter[1]];
			if (filter.length === 3) return [doctype, ...filter];
			return filter;
		});
	},

	normalize_filter(doctype, fieldname, value) {
		if (Array.isArray(value) && value.length === 2) {
			return [doctype, fieldname, value[0], value[1]];
		}
		return [doctype, fieldname, "=", value];
	},
});
