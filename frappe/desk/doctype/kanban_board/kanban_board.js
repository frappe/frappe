// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Kanban Board", {
	onload: function (frm) {
		frm.trigger("reference_doctype");
	},
	after_save: function (frm) {
		// The engine (classic vs v2) is chosen from use_kanban_v2; drop the cached
		// value so reopening the board reflects a just-changed toggle (no reload).
		if (frappe.views._kanban_engine_cache) {
			delete frappe.views._kanban_engine_cache[frm.doc.name];
		}
	},
	refresh: function (frm) {
		set_standard_toggle_access(frm);
		set_private_toggle_access(frm);
		// The grid may not have had its docfields ready during onload.
		if (frm.doc.reference_doctype) {
			frappe.model.with_doctype(frm.doc.reference_doctype, () => {
				set_card_field_options(frm);
				set_group_by_field_options(frm);
				set_title_image_field_options(frm);
			});
		}
		if (frm.is_new()) return;
		frm.add_custom_button(__("Show Board"), function () {
			// Same route for both UIs; this board's "Use Kanban v2" flag picks the engine.
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

/** Standard boards are fixture-backed: only Administrator in dev mode can mark/unmark. */
function set_standard_toggle_access(frm) {
	const can_toggle =
		frappe.session.user === "Administrator" && Boolean(frappe.boot?.developer_mode);
	frm.set_df_property("is_standard", "read_only", can_toggle ? 0 : 1);
}

/** Existing boards: only owner/Admin can toggle Private. Backend also enforces. */
function set_private_toggle_access(frm) {
	if (frm.is_new()) {
		frm.set_df_property("private", "read_only", 0);
		return;
	}
	const can_toggle =
		frappe.session.user === "Administrator" || frappe.session.user === frm.doc.owner;
	frm.set_df_property("private", "read_only", can_toggle ? 0 : 1);
}

// Autofill the label from the selected field; the user can still edit it. Shared
// by the Card/Preview field rows and the Group By field rows.
function autofill_field_label(frm, cdt, cdn) {
	var row = locals[cdt][cdn];
	if (!row.fieldname || !frm.doc.reference_doctype) return;
	var df = frappe.meta.get_docfield(frm.doc.reference_doctype, row.fieldname);
	frappe.model.set_value(cdt, cdn, "label", df ? __(df.label) : row.fieldname);
}

frappe.ui.form.on("Kanban Board Field", { fieldname: autofill_field_label });
frappe.ui.form.on("Kanban Board Group Field", { fieldname: autofill_field_label });

/**
 * Fill the Card Fields and Preview Fields grids' autocomplete with the reference
 * doctype's fields. Value = fieldname (what is stored), label = field label,
 * description = fieldname, so the dropdown reads like the field picker elsewhere
 * in desk.
 */
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
		// update_docfield_property also patches already-rendered rows, so the
		// options land on existing rows and on rows added afterwards.
		grid.update_docfield_property("fieldname", "options", options);
		grid.refresh();
	});
}

/**
 * Fill the Group By Fields grid's autocomplete. Only Select and Link fields
 * make sense as swimlane groupings — bounded, categorical values — so the
 * picker is narrower than the Card/Preview field pickers.
 */
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
	// update_docfield_property patches both existing and later-added rows.
	grid.update_docfield_property("fieldname", "options", options);
	grid.refresh();
}

/**
 * Title Field: name (ID) + Data fields only.
 * Image Field: Attach Image fields only.
 */
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
				return df.fieldname && df.fieldtype === "Data" && !df.hidden;
			})
			.map(to_option)
	);

	// Include the doctype's configured image_field even if hidden, since
	// image fields are often hidden in forms but used in sidebars/cards.
	var image_options = meta.fields
		.filter(function (df) {
			return (
				df.fieldname &&
				df.fieldtype === "Attach Image" &&
				(!df.hidden || df.fieldname === meta.image_field)
			);
		})
		.map(to_option);

	frm.set_df_property("title_field", "options", title_options);
	frm.set_df_property("image_field", "options", image_options);
	frm.get_field("title_field") && frm.get_field("title_field").set_data(title_options);
	frm.get_field("image_field") && frm.get_field("image_field").set_data(image_options);
}

/** Mirror server before_insert defaults so a new form shows title/image already picked. */
function seed_title_and_image_fields(frm) {
	var meta = frappe.get_meta(frm.doc.reference_doctype);
	if (!frm.doc.title_field) {
		var title = null;
		if (meta.title_field) {
			var tdf = meta.fields.find(function (df) {
				return df.fieldname === meta.title_field;
			});
			if (tdf && tdf.fieldtype === "Data" && !tdf.hidden) title = meta.title_field;
		}
		if (!title) {
			var data = meta.fields.find(function (df) {
				return df.fieldtype === "Data" && df.fieldname && !df.hidden;
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
					return df.fieldtype === "Attach Image" && df.fieldname && !df.hidden;
				}) || {}
			).fieldname ||
			"";
		if (image) frm.set_value("image_field", image);
	}
}
