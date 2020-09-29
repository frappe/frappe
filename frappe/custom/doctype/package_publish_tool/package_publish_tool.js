// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Package Publish Tool', {
	refresh: function(frm) {
		frm.set_query("document_type", "package_details", function () {
			return {
				filters: {
					"istable": 0,
				}
			};
		});

		frappe.realtime.on("package", (data) => {
			frm.dashboard.show_progress(data.prefix, data.progress / data.total * 100, __("{0}", [data.message]));
			if ((data.progress+1) != data.total) {
				frm.dashboard.show_progress(data.prefix, data.progress / data.total * 100, __("{0}", [data.message]));
			} else {
				frm.dashboard.hide_progress();
			}
		});

		frm.trigger("show_instructions");
		frm.trigger("last_deployed_on");
		frm.trigger("set_dirty_trigger");
		frm.trigger("set_deploy_primary_action");
	},
	last_deployed_on: function(frm) {
		if (frm.doc.last_deployed_on) {
			frm.trigger("show_indicator");
		}
	},
	show_indicator: function(frm) {
		let pretty_date = frappe.datetime.prettyDate(frm.doc.last_deployed_on);
		frm.page.set_indicator(__("Last published {0}", [pretty_date]), "blue");
	},
	set_dirty_trigger: function(frm) {
		$(frm.wrapper).on("dirty", function() {
			frm.page.set_primary_action(__('Save'), () => frm.save());
		});
	},
	set_deploy_primary_action: function(frm) {
		if (frm.doc.package_details.length && frm.doc.instances.length) {
			frm.page.set_primary_action(__("Publish"), function () {
				frappe.show_alert({
					message: __("Publishing documents..."),
					indicator: "green"
				});

				frappe.call({
					method: "frappe.custom.doctype.package_publish_tool.package_publish_tool.deploy_package",
					callback: function() {
						frm.reload_doc();
						frappe.msgprint(__("Documents have been published."));
					}
				});
			});
		}
	},
	show_instructions: function(frm) {
		let field = frm.get_field("html_info");
		field.html(`
			<p class="text-muted text-medium">
				Package Publish Tool let's you copy documents from your site to any other remote site.
				Follow the steps below to publish.
			</p>
			<ol class="text-muted small">
				<li>Add Document Types that you want to copy from the table below. You can also add filters by expanding the row.</li>
				<li>Add the Sites URL where you want to copy these documents, and enter the Username and Password.</li>
				<li>Click on Save. Now, you can click on Publish and the documents will be copied.</li>
			</ol>
		`);
	}
});

frappe.ui.form.on('Package Document Type', {
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
