// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.customize_form");

frappe.ui.form.on("Customize Form", {
	onload: function(frm) {
		frappe.customize_form.add_fields_help(frm);

		frm.set_query("doc_type", function() {
			return {
				filters: [
					['DocType', 'issingle', '=', 0],
					['DocType', 'custom', '=', 0],
					['DocType', 'in_create', '=', 0],
					['DocType', 'name', 'not in', 'DocType, DocField, DocPerm, User, Role, UserRole, \
						 Page, Page Role, Module Def, Print Format, Report, Customize Form, \
						 Customize Form Field']
				]
			};
		});

		$(frm.wrapper).on("grid-row-render", function(e, grid_row) {
			if(grid_row.doc && grid_row.doc.fieldtype=="Section Break") {
				$(grid_row.row).css({"font-weight": "bold"});
			}
		});
	},

	doc_type: function(frm) {
		if(frm.doc.doc_type) {
			return frm.call({
				method: "fetch_to_customize",
				doc: frm.doc,
				callback: function(r) {
					frm.refresh();
				}
			});
		}
	},

	refresh: function(frm) {
		frm.disable_save();
		frm.page.clear_icons();

		if(frm.doc.doc_type) {
			frappe.customize_form.set_primary_action(frm);

			frm.add_custom_button(__('Refresh Form'), function() {
				frm.script_manager.trigger("doc_type");
			}, "icon-refresh", "btn-default");

			frm.add_custom_button(__('Reset to defaults'), function() {
				frappe.customize_form.confirm(__('Remove all customizations?'), frm);
			}, "icon-eraser", "btn-default");
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
				frm.set_value("doc_type", frappe.route_options.doctype);
				frappe.route_options = null;
			}, 1000);
		}

	},

});

frappe.ui.form.on("Customize Form Field", {
	before_fields_remove: function(frm, doctype, name) {
		var row = frappe.get_doc(doctype, name);
		if(!(row.is_custom_field || row.__islocal)) {
			msgprint(__("Cannot delete standard field. You can hide it if you want"));
			throw "cannot delete custom field";
		}
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
						msgprint(r.exc);
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
