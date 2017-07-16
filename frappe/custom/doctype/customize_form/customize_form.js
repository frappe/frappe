// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.customize_form");

frappe.ui.form.on("Customize Form", {
	onload: function(frm) {
		frappe.customize_form.add_fields_help(frm);

		frm.set_query("doc_type", function() {
			return {
				translate_values: false,
				filters: [
					['DocType', 'issingle', '=', 0],
					['DocType', 'custom', '=', 0],
					['DocType', 'name', 'not in', 'DocType, DocField, DocPerm, User, Role, Has Role, \
						Page, Has Role, Module Def, Print Format, Report, Customize Form, \
						Customize Form Field, Property Setter, Custom Field, Custom Script'],
					['DocType', 'restrict_to_domain', 'in', frappe.boot.active_domains]
				]
			};
		});

		$(frm.wrapper).on("grid-row-render", function(e, grid_row) {
			if(grid_row.doc && grid_row.doc.fieldtype=="Section Break") {
				$(grid_row.row).css({"font-weight": "bold"});
			}
		});

		$(frm.wrapper).on("grid-make-sortable", function(e, frm) {
			frm.trigger("setup_sortable");
		});
	},

	doc_type: function(frm) {
		if(frm.doc.doc_type) {
			return frm.call({
				method: "fetch_to_customize",
				doc: frm.doc,
				freeze: true,
				callback: function(r) {
					frm.refresh();
					frm.trigger("setup_sortable");
				}
			});
		} else {
			frm.refresh();
		}
	},

	setup_sortable: function(frm) {
		frm.page.body.find('.highlight').removeClass('highlight');
		frm.doc.fields.forEach(function(f, i) {
			var data_row = frm.page.body.find('[data-fieldname="fields"] [data-idx="'+ f.idx +'"] .data-row');

			if(!f.is_custom_field) {
				data_row.removeClass('sortable-handle');
			} else {
				data_row.addClass("highlight");
			}
		});
	},

	refresh: function(frm) {
		frm.disable_save();
		frm.page.clear_icons();

		if(frm.doc.doc_type) {
			frappe.customize_form.set_primary_action(frm);

			frm.add_custom_button(__('Refresh Form'), function() {
				frm.script_manager.trigger("doc_type");
			}, "fa fa-refresh", "btn-default");

			frm.add_custom_button(__('Reset to defaults'), function() {
				frappe.customize_form.confirm(__('Remove all customizations?'), frm);
			}, "fa fa-eraser", "btn-default");

			frm.add_custom_button(__('Set Permissions'), function() {
				frappe.set_route('permission-manager', frm.doc.doc_type);
			}, "fa fa-lock", "btn-default");

			if(frappe.boot.developer_mode) {
				frm.add_custom_button(__('Export Customizations'), function() {
					frappe.prompt(
						[
							{fieldtype:'Link', fieldname:'module', options:'Module Def',
								label: __('Module to Export')},
							{fieldtype:'Check', fieldname:'sync_on_migrate',
								label: __('Sync on Migrate'), 'default': 1},
							{fieldtype:'Check', fieldname:'with_permissions',
								label: __('Export Custom Permissions'), 'default': 1},
						],
						function(data) {
							frappe.call({
								method: 'frappe.modules.utils.export_customizations',
								args: {
									doctype: frm.doc.doc_type,
									module: data.module,
									sync_on_migrate: data.sync_on_migrate,
									with_permissions: data.with_permissions
								}
							});
						},
						__("Select Module"));
				});
			}
		}

		// sort order select
		if(frm.doc.doc_type) {
			var fields = $.map(frm.doc.fields,
					function(df) { return frappe.model.is_value_type(df.fieldtype) ? df.fieldname : null; });
			fields = ["", "name", "modified"].concat(fields);
			frm.set_df_property("sort_field", "options", fields);
		}

		if(frappe.route_options) {
			setTimeout(function() {
				frm.set_value("doc_type", frappe.route_options.doc_type);
				frappe.route_options = null;
			}, 1000);
		}

	},

});

frappe.ui.form.on("Customize Form Field", {
	before_fields_remove: function(frm, doctype, name) {
		var row = frappe.get_doc(doctype, name);
		if(!(row.is_custom_field || row.__islocal)) {
			frappe.msgprint(__("Cannot delete standard field. You can hide it if you want"));
			throw "cannot delete custom field";
		}
	},
	fields_add: function(frm, cdt, cdn) {
		var f = frappe.model.get_doc(cdt, cdn);
		f.is_custom_field = 1;
	}
});

frappe.customize_form.set_primary_action = function(frm) {
	frm.page.set_primary_action(__("Update"), function() {
		if(frm.doc.doc_type) {
			return frm.call({
				doc: frm.doc,
				freeze: true,
				method: "save_customization",
				callback: function(r) {
					if(!r.exc) {
						frappe.customize_form.clear_locals_and_refresh(frm);
						frm.script_manager.trigger("doc_type");
					}
				}
			});
		}
	});
};

frappe.customize_form.confirm = function(msg, frm) {
	if(!frm.doc.doc_type) return;

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
					if(r.exc) {
						frappe.msgprint(r.exc);
					} else {
						d.hide();
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
	// clear doctype from locals
	frappe.model.clear_doc("DocType", frm.doc.doc_type);
	delete frappe.meta.docfield_copy[frm.doc.doc_type];

	frm.refresh();
}

frappe.customize_form.add_fields_help = function(frm) {
	$(frm.grids[0].parent).before(
		'<div style="padding: 10px">\
			<a id="fields_help" class="link_type">' + __("Help") + '</a>\
		</div>');
	$('#fields_help').click(function() {
		var d = new frappe.ui.Dialog({
			title: __('Help: Field Properties'),
			width: 600
		});

		var help =
			"<table cellspacing='25'>\
				<tr>\
					<td><b>" + __("Label") + "</b></td>\
					<td>" + __("Set the display label for the field") + "</td>\
				</tr>\
				<tr>\
					<td><b>" + __("Type") + "</b></td>\
					<td>" + __("Change type of field. (Currently, Type change is \
						allowed among 'Currency and Float')") + "</td>\
				</tr>\
				<tr>\
					<td width='25%'><b>" + __("Options") + "</b></td>\
					<td width='75%'>" + __("Specify the value of the field") + "</td>\
				</tr>\
				<tr>\
					<td><b>" + __("Perm Level") + "</b></td>\
					<td>\
						" + __("Assign a permission level to the field.") + "<br />\
						(" + __("Permissions can be managed via Setup &gt; Role Permissions Manager") + "\
					</td>\
				</tr>\
				<tr>\
					<td><b>" + __("Width") + "</b></td>\
					<td>\
						" + __("Width of the input box") + "<br />\
						" + __("Example") + ": <i>120px</i>\
					</td>\
				</tr>\
				<tr>\
					<td><b>" + __("Reqd") + "</b></td>\
					<td>" + __("Mark the field as Mandatory") + "</td>\
				</tr>\
				<tr>\
					<td><b>" + __("In Filter") + "</b></td>\
					<td>" + __("Use the field to filter records") + "</td>\
				</tr>\
				<tr>\
					<td><b>" + __("Hidden") + "</b></td>\
					<td>" + __("Hide field in form") + "</td>\
				</tr>\
				<tr>\
					<td><b>" + __("Print Hide") + "</b></td>\
					<td>" + __("Hide field in Standard Print Format") + "</td>\
				</tr>\
				<tr>\
					<td><b>" + __("Report Hide") + "</b></td>\
					<td>" + __("Hide field in Report Builder") + "</td>\
				</tr>\
				<tr>\
					<td><b>" + __("Allow on Submit") + "</b></td>\
					<td>" + __("Allow field to remain editable even after submission") + "</td>\
				</tr>\
				<tr>\
					<td><b>" + __("Depends On") + "</b></td>\
					<td>\
						Show field if a condition is met<br />\
						Example: <code>eval:doc.status=='Cancelled'</code>\
						on a field like \"reason_for_cancellation\" will reveal \
						\"Reason for Cancellation\" only if the record is Cancelled.\
					</td>\
				</tr>\
				<tr>\
					<td><b>" + __("Description") + "</b></td>\
					<td>" + __("Show a description below the field") + "</td>\
				</tr>\
				<tr>\
					<td><b>" + __("Default") + "</b></td>\
					<td>" + __("Specify a default value") + "</td>\
				</tr>\
				<tr>\
					<td></td>\
					<td><a class='link_type' \
							onclick='frappe.customize_form.fields_help_dialog.hide()'\
							style='color:grey'>" + __("Press Esc to close") + "</a>\
					</td>\
				</tr>\
			</table>"

		$y(d.body, {padding: '32px', textAlign: 'center', lineHeight: '200%'});

		$a(d.body, 'div', '', {textAlign: 'left'}, help);

		d.show();

		frappe.customize_form.fields_help_dialog = d;

	});
}
