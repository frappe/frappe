// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Kanban Board", {
	onload: function (frm) {
		if (frm.is_new()) frm.set_value("use_kanban_v2", 1);
		frm.trigger("reference_doctype");
	},
	after_save: function (frm) {
		// the board opens with the engine cached for it, so forget it after a change
		if (frappe.views._kanban_engine_cache) {
			delete frappe.views._kanban_engine_cache[frm.doc.name];
		}
	},
	refresh: function (frm) {
		// the grid's docfields may not have been ready in onload
		if (frm.doc.reference_doctype) {
			frappe.model.with_doctype(frm.doc.reference_doctype, () => {
				set_card_field_options(frm);
				set_group_by_field_options(frm);
				set_title_image_field_options(frm);
			});
		}
		if (frm.is_new()) return;
		frm.add_custom_button(__("Show Board"), function () {
			frappe.set_route("List", frm.doc.reference_doctype, "Kanban", frm.doc.name);
		});
	},

	reference_doctype: function (frm) {
		// set field options
		if (!frm.doc.reference_doctype) return;

		frappe.model.with_doctype(frm.doc.reference_doctype, function () {
			var options = $.map(frappe.get_meta(frm.doc.reference_doctype).fields, function (d) {
				if (
					d.fieldname &&
					d.fieldtype === "Select" &&
					!frappe.model.no_value_type.includes(d.fieldtype)
				) {
					return d.fieldname;
				}
				return null;
			});
			frm.set_df_property("field_name", "options", options);
			frm.get_field("field_name").refresh();
			set_card_field_options(frm);
			set_group_by_field_options(frm);
			set_title_image_field_options(frm);
			if (frm.is_new()) {
				seed_title_and_image_fields(frm);
			}
		});
	},
	field_name: function (frm) {
		var field = frappe.meta.get_field(frm.doc.reference_doctype, frm.doc.field_name);
		frm.doc.columns = [];
		field.options &&
			field.options.split("\n").forEach(function (o) {
				o = o.trim();
				if (!o) return;
				var d = frm.add_child("columns");
				d.column_name = o;
			});
		frm.refresh();
	},
});

// autofill the row label from its field; it stays editable
function autofill_field_label(frm, cdt, cdn) {
	var row = locals[cdt][cdn];
	if (!row.fieldname || !frm.doc.reference_doctype) return;
	var df = frappe.meta.get_docfield(frm.doc.reference_doctype, row.fieldname);
	frappe.model.set_value(cdt, cdn, "label", df ? df.label : row.fieldname);
}

frappe.ui.form.on("Kanban Board Field", { fieldname: autofill_field_label });
frappe.ui.form.on("Kanban Board Group Field", { fieldname: autofill_field_label });

/** Card and Preview field pickers: store the fieldname, show the label. */
function set_card_field_options(frm) {
	if (!frm.doc.reference_doctype) return;

	var options = frappe
		.get_meta(frm.doc.reference_doctype)
		.fields.filter(function (df) {
			return (
				df.fieldname &&
				frappe.model.is_value_type(df.fieldtype) &&
				!df.hidden &&
				df.fieldtype !== "Password"
			);
		})
		.map(function (df) {
			return {
				value: df.fieldname,
				label: __(df.label) || df.fieldname,
				description: df.fieldname,
			};
		});

	["card_fields", "preview_fields"].forEach(function (tablefield) {
		var grid = frm.fields_dict[tablefield] && frm.fields_dict[tablefield].grid;
		if (!grid || !grid.docfields) return;
		// update_docfield_property also reaches rows already rendered
		grid.update_docfield_property("fieldname", "options", options);
		grid.refresh();
	});
}

/** Swimlane picker: only Select and Link fields, whose values make sensible groups. */
function set_group_by_field_options(frm) {
	if (!frm.doc.reference_doctype) return;

	var options = frappe
		.get_meta(frm.doc.reference_doctype)
		.fields.filter(function (df) {
			return (
				df.fieldname &&
				(df.fieldtype === "Select" || df.fieldtype === "Link") &&
				!df.hidden
			);
		})
		.map(function (df) {
			return {
				value: df.fieldname,
				label: __(df.label) || df.fieldname,
				description: df.fieldname,
			};
		});

	var grid = frm.fields_dict.group_by_fields && frm.fields_dict.group_by_fields.grid;
	if (!grid || !grid.docfields) return;
	grid.update_docfield_property("fieldname", "options", options);
	grid.refresh();
}

/** Title Field takes ID or a text field; Image Field takes Attach Image fields. */
function set_title_image_field_options(frm) {
	if (!frm.doc.reference_doctype) return;

	var meta = frappe.get_meta(frm.doc.reference_doctype);
	var to_option = function (df) {
		return {
			value: df.fieldname,
			label: __(df.label) || df.fieldname,
			description: df.fieldname,
		};
	};
	var title_options = [
		{
			value: "name",
			label: __("ID"),
			description: "name",
		},
	].concat(
		meta.fields
			.filter(function (df) {
				return (
					df.fieldname &&
					["Data", "Text", "Small Text", "Text Editor"].includes(df.fieldtype) &&
					(!df.hidden || df.fieldname === meta.title_field)
				);
			})
			.map(to_option)
	);

	// image fields are often hidden on the form but meant for display
	var image_options = meta.fields
		.filter(function (df) {
			return df.fieldname && df.fieldtype === "Attach Image";
		})
		.map(to_option);

	frm.set_df_property("title_field", "options", title_options);
	frm.set_df_property("image_field", "options", image_options);
	frm.get_field("title_field") && frm.get_field("title_field").set_data(title_options);
	frm.get_field("image_field") && frm.get_field("image_field").set_data(image_options);
}

/** Same defaults as the server's before_insert, so a new form shows them. */
function seed_title_and_image_fields(frm) {
	var meta = frappe.get_meta(frm.doc.reference_doctype);
	if (!frm.doc.title_field) {
		var title = null;
		if (meta.title_field) {
			var tdf = meta.fields.find(function (df) {
				return df.fieldname === meta.title_field;
			});
			if (tdf && ["Data", "Text", "Small Text", "Text Editor"].includes(tdf.fieldtype))
				title = meta.title_field;
		}
		if (!title) {
			var data = meta.fields.find(function (df) {
				return (
					["Data", "Text", "Small Text", "Text Editor"].includes(df.fieldtype) &&
					df.fieldname &&
					!df.hidden
				);
			});
			title = data ? data.fieldname : "name";
		}
		frm.set_value("title_field", title);
	}
	if (!frm.doc.image_field) {
		var image =
			meta.image_field ||
			(
				meta.fields.find(function (df) {
					return df.fieldtype === "Attach Image" && df.fieldname;
				}) || {}
			).fieldname ||
			"";
		if (image) frm.set_value("image_field", image);
	}
}
