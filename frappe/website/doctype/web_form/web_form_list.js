frappe.listview_settings["Web Form"] = {
	add_fields: ["title", "published"],
	get_indicator: function (doc) {
		if (doc.published) {
			return [__("Published"), "green", "published,=,1"];
		} else {
			return [__("Not Published"), "gray", "published,=,0"];
		}
	},
	primary_action() {
		this.new_web_form_dialog();
	},

	new_web_form_dialog() {
		// a route typed by hand stops following the title
		let route_edited = false;

		let dialog = new frappe.ui.Dialog({
			title: __("New Web Form"),
			fields: [
				{
					label: __("Title"),
					fieldname: "title",
					fieldtype: "Data",
					reqd: 1,
					onchange() {
						if (route_edited) return;
						let title = dialog.get_value("title") || "";
						dialog.set_value("route", title.toLowerCase().replace(/ /g, "-"));
					},
				},
				{
					label: __("Route"),
					fieldname: "route",
					fieldtype: "Data",
					onchange() {
						let title = dialog.get_value("title") || "";
						let route = dialog.get_value("route") || "";
						route_edited = route !== title.toLowerCase().replace(/ /g, "-");
					},
				},
				{
					label: __("Select DocType (optional)"),
					fieldname: "doc_type",
					fieldtype: "Link",
					options: "DocType",
				},
				{
					label: __("Module"),
					fieldname: "module",
					fieldtype: "Link",
					options: "Module Def",
					mandatory_depends_on: "is_standard",
				},
				{
					label: __("Is standard"),
					fieldname: "is_standard",
					fieldtype: "Check",
					description: __(
						frappe.meta.get_docfield("Web Form", "is_standard")?.description || ""
					),
					hidden: !frappe.boot.developer_mode,
				},
				{
					label: __("Banner Image"),
					fieldname: "banner_image",
					fieldtype: "Attach Image",
					make_attachment_public: 1,
				},
				{
					label: __("Description"),
					fieldname: "introduction_text",
					fieldtype: "Text Editor",
					max_height: "150px",
				},
			],
			primary_action_label: __("Save"),
			primary_action(values) {
				return frappe.db.insert({ doctype: "Web Form", ...values }).then((doc) => {
					dialog.hide();
					frappe.set_route("Form", "Web Form", doc.name);
				});
			},
			secondary_action_label: __("Edit Full Form"),
			secondary_action() {
				// route_options would drop title, a no_copy field
				let values = dialog.get_values(true);
				dialog.hide();
				frappe.new_doc("Web Form", null, (doc) => Object.assign(doc, values));
			},
		});
		dialog.show();
	},
};
