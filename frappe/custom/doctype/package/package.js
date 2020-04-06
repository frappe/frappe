// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Package', {
	refresh: function(frm) {
		if (frm.doc.package_details) {
			frm.add_custom_button(__("Go to Release"), function() {
				frappe.set_route("Form", "Release", "Release");
			});
		}

		frm.set_query("document_type", "package_details", function () {
			return {
				filters: {
					"istable": 0,
				}
			};
		});
	},
	import: function(frm) {
		frm.call("import_from_package");
	}
});

frappe.ui.form.on('Package Details', {
	form_render: function (frm, cdt, cdn) {
		function _show_filters(filters, table) {
			table.find('tbody').empty();

			if (filters.length > 0) {
				filters.forEach(filter => {
					const filter_row =
						$(`<tr>
							<td>${filter[1]}</td>
							<td>${filter[2] || ""}</td>
							<td>${filter[3]}</td>
						</tr>`);

					table.find('tbody').append(filter_row);
				});
			} else {
				const filter_row = $(`<tr><td colspan="3" class="text-muted text-center">
					${__("Click to Set Filters")}</td></tr>`);
				table.find('tbody').append(filter_row);
			}
		}

		let row = frappe.get_doc(cdt, cdn);

		let wrapper = $(`[data-fieldname="filters_json"]`).empty();
		let table = $(`<table class="table table-bordered" style="cursor:pointer; margin:0px;">
				<thead>
					<tr>
						<th style="width: 33%">${__('Filter')}</th>
						<th style="width: 33%">${__('Condition')}</th>
						<th>${__('Value')}</th>
					</tr>
				</thead>
				<tbody>
				</tbody>
			</table>`).appendTo(wrapper);
		$(`<p class="text-muted small">${__("Click table to edit")}</p>`).appendTo(wrapper);

		let filters = JSON.parse(row.filters_json || '[]');
		_show_filters(filters, table);

		table.on('click', () => {
			if (!row.document_type) {
				frappe.msgprint(__("Select Document Type."));
				return;
			}

			frappe.model.with_doctype(row.document_type, function() {
				let dialog = new frappe.ui.Dialog({
					title: __('Set Filters'),
					fields: [
						{
							fieldtype: 'HTML',
							label: 'Filters',
							fieldname: 'filter_area',
						}
					],
					primary_action: function() {
						let values = filter_group.get_filters();
						let flt = [];
						if (values) {
							values.forEach(function(value) {
								flt.push([value[0], value[1], value[2], value[3]]);
							});
						}
						row.filters_json = JSON.stringify(flt);
						_show_filters(flt, table);
						dialog.hide();
					},
					primary_action_label: "Set"
				});

				let filter_group = new frappe.ui.FilterGroup({
					parent: dialog.get_field('filter_area').$wrapper,
					doctype: row.document_type,
					on_change: () => {},
				});
				filter_group.add_filters_to_filter_group(filters);
				dialog.show();
			});
		});
	},
});
