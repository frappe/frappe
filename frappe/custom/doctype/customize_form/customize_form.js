// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.customize_form");

frappe.ui.form.on("Customize Form", {
	setup: function(frm) {
		// save the last setting if refreshing
		window.addEventListener("beforeunload", () => {
			if (frm.doc.doc_type && frm.doc.doc_type != "undefined") {
				localStorage["customize_doctype"] = frm.doc.doc_type;
			}
		});
	},

	onload: function(frm) {
		frm.set_query("doc_type", function() {
			return {
				translate_values: false,
				filters: [
					["DocType", "issingle", "=", 0],
					["DocType", "custom", "=", 0],
					[
						"DocType",
						"name",
						"not in",
						frappe.model.core_doctypes_list
					],
					[
						"DocType",
						"restrict_to_domain",
						"in",
						frappe.boot.active_domains
					]
				]
			};
		});

		frm.set_query("default_print_format", function() {
			return {
				filters: {
					print_format_type: ["!=", "JS"],
					doc_type: ["=", frm.doc.doc_type]
				}
			};
		});

		$(frm.wrapper).on("grid-row-render", function(e, grid_row) {
			if (grid_row.doc && grid_row.doc.fieldtype == "Section Break") {
				$(grid_row.row).css({ "font-weight": "bold" });
			}
		});

		$(frm.wrapper).on("grid-make-sortable", function(e, frm) {
			frm.trigger("setup_sortable");
		});

		$(frm.wrapper).on("grid-move-row", function(e, frm) {
			frm.trigger("setup_sortable");
		});
	},

	doc_type: function(frm) {
		if (frm.doc.doc_type) {
			return frm.call({
				method: "fetch_to_customize",
				doc: frm.doc,
				freeze: true,
				callback: function(r) {
					if (r) {
						if (r._server_messages && r._server_messages.length) {
							frm.set_value("doc_type", "");
						} else {
							frm.refresh();
							frm.trigger("setup_sortable");
						}
					}
					localStorage["customize_doctype"] = frm.doc.doc_type;
				}
			});
		} else {
			frm.refresh();
		}
	},

	setup_sortable: function(frm) {
		frm.page.body.find(".highlight").removeClass("highlight");
		frm.doc.fields.forEach(function(f, i) {
			var data_row = frm.page.body.find(
				'[data-fieldname="fields"] [data-idx="' + f.idx + '"] .data-row'
			);

			if (f.is_custom_field) {
				data_row.addClass("highlight");
			} else {
				f._sortable = false;
			}
			if (f.fieldtype == "Table") {
				frm.add_custom_button(
					f.options,
					function() {
						frm.set_value("doc_type", f.options);
					},
					__("Customize Child Table")
				);
			}
		});
		frm.fields_dict.fields.grid.refresh();
	},

	refresh: function(frm) {
		frm.disable_save(true);
		frm.page.clear_icons();

		if (frm.doc.doc_type) {
			frappe.customize_form.set_primary_action(frm);

			frm.add_custom_button(
				__("Go to {0} List", [__(frm.doc.doc_type)]),
				function() {
					frappe.set_route("List", frm.doc.doc_type);
				},
				__("Actions")
			);

			frm.add_custom_button(
				__("Reload"),
				function() {
					frm.script_manager.trigger("doc_type");
				},
				__("Actions")
			);

			frm.add_custom_button(
				__("Reset to defaults"),
				function() {
					frappe.customize_form.confirm(
						__("Remove all customizations?"),
						frm
					);
				},
				__("Actions")
			);

			frm.add_custom_button(
				__("Set Permissions"),
				function() {
					frappe.set_route("permission-manager", frm.doc.doc_type);
				},
				__("Actions")
			);
		}

		frm.events.setup_export(frm);
		frm.events.setup_sort_order(frm);
		frm.events.set_default_doc_type(frm);
	},

	set_default_doc_type(frm) {
		let doc_type;
		if (frappe.route_options && frappe.route_options.doc_type) {
			doc_type = frappe.route_options.doc_type;
			frappe.route_options = null;
			localStorage.removeItem("customize_doctype");
		}
		if (!doc_type) {
			doc_type = localStorage.getItem("customize_doctype");
		}
		if (doc_type) {
			setTimeout(() => frm.set_value("doc_type", doc_type, false, true), 1000);
		}
	},

	setup_export(frm) {
		if (frappe.boot.developer_mode) {
			frm.add_custom_button(
				__("Export Customizations"),
				function() {
					frappe.prompt(
						[
							{
								fieldtype: "Link",
								fieldname: "module",
								options: "Module Def",
								label: __("Module to Export"),
								reqd: 1,
							},
							{
								fieldtype: "Check",
								fieldname: "sync_on_migrate",
								label: __("Sync on Migrate"),
								default: 1
							},
							{
								fieldtype: "Check",
								fieldname: "with_permissions",
								label: __("Export Custom Permissions"),
								default: 1
							}
						],
						function(data) {
							frappe.call({
								method: "frappe.modules.utils.export_customizations",
								args: {
									doctype: frm.doc.doc_type,
									module: data.module,
									sync_on_migrate: data.sync_on_migrate,
									with_permissions: data.with_permissions
								}
							});
						},
						__("Select Module")
					);
				},
				__("Actions")
			);
		}
	},

	setup_sort_order(frm) {
		// sort order select
		if (frm.doc.doc_type) {
			var fields = $.map(frm.doc.fields, function(df) {
				return frappe.model.is_value_type(df.fieldtype)
					? df.fieldname
					: null;
			});
			fields = ["", "name", "modified"].concat(fields);
			frm.set_df_property("sort_field", "options", fields);
		}
	}
});

// can't delete standard fields
frappe.ui.form.on("Customize Form Field", {
	before_fields_remove: function(frm, doctype, name) {
		var row = frappe.get_doc(doctype, name);
		if (!(row.is_custom_field || row.__islocal)) {
			frappe.msgprint(__("Cannot delete standard field. You can hide it if you want"));
			throw "cannot delete standard field";
		}
	},
	fields_add: function(frm, cdt, cdn) {
		var f = frappe.model.get_doc(cdt, cdn);
		f.is_custom_field = 1;
	}
});

// can't delete standard links
frappe.ui.form.on("DocType Link", {
	before_links_remove: function(frm, doctype, name) {
		let row = frappe.get_doc(doctype, name);
		if (!(row.custom || row.__islocal)) {
			frappe.msgprint(__("Cannot delete standard link. You can hide it if you want"));
			throw "cannot delete standard link";
		}
	},
	links_add: function(frm, cdt, cdn) {
		let f = frappe.model.get_doc(cdt, cdn);
		f.custom = 1;
	}
});

// can't delete standard actions
frappe.ui.form.on("DocType Action", {
	before_actions_remove: function(frm, doctype, name) {
		let row = frappe.get_doc(doctype, name);
		if (!(row.custom || row.__islocal)) {
			frappe.msgprint(__("Cannot delete standard action. You can hide it if you want"));
			throw "cannot delete standard action";
		}
	},
	actions_add: function(frm, cdt, cdn) {
		let f = frappe.model.get_doc(cdt, cdn);
		f.custom = 1;
	}
});

frappe.customize_form.set_primary_action = function(frm) {
	frm.page.set_primary_action(__("Update"), function() {
		if (frm.doc.doc_type) {
			return frm.call({
				doc: frm.doc,
				freeze: true,
				btn: frm.page.btn_primary,
				method: "save_customization",
				callback: function(r) {
					if (!r.exc) {
						frappe.customize_form.clear_locals_and_refresh(frm);
						frm.script_manager.trigger("doc_type");
					}
				}
			});
		}
	});
};

frappe.customize_form.confirm = function(msg, frm) {
	if (!frm.doc.doc_type) return;

	var d = new frappe.ui.Dialog({
		title: 'Reset To Defaults',
		fields: [
			{fieldtype:"HTML", options:__("All customizations will be removed. Please confirm.")},
		],
		primary_action: function() {
			return frm.call({
				doc: frm.doc,
				method: "reset_to_defaults",
				callback: function(r) {
					if (r.exc) {
						frappe.msgprint(r.exc);
					} else {
						d.hide();
						frappe.show_alert({message:__('Customizations Reset'), indicator:'green'});
						frappe.customize_form.clear_locals_and_refresh(frm);
					}
				}
			});
		}
	});

	frappe.customize_form.confirm.dialog = d;
	d.show();
}

frappe.customize_form.clear_locals_and_refresh = function(frm) {
	delete frm.doc.__unsaved;
	// clear doctype from locals
	frappe.model.clear_doc("DocType", frm.doc.doc_type);
	delete frappe.meta.docfield_copy[frm.doc.doc_type];

	frm.refresh();
}

