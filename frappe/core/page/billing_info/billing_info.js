frappe.pages['billing-info'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Billing Info',
		single_column: true
	});

	frappe.call({
		method: "frappe.core.page.billing_info.billing_info.get_billing_details",
		callback: function(r) {
			var billing_info = r.message;

			$(frappe.render_template("billing_info", billing_info)).appendTo(page.main);

			$(page.main).find('.btn-primary').on('click', () => {
				setup_billing_address($(page.main))
			});
		}
	});

}

setup_billing_address = function(page){
	var d = new frappe.ui.Dialog({
			title: __('New Address'),
			fields: [
				{
					"label": "Adress Title",
					"fieldname": "address_title",
					"fieldtype": "Data",
					"reqd": 1
				},
				{
					"label": "Address Type",
					"fieldname": "address_type",
					"fieldtype": "Data",
					"read_only": 1,
					"default": "Billing"
				},
				{
					"label": "Address Line 1",
					"fieldname": "address_line1",
					"fieldtype": "Data",
					"reqd": 1
				},
				{
					"label": "Address Line 2",
					"fieldname": "address_line2",
					"fieldtype": "Data"
				},
				{
					"fieldname": "cb1",
					"fieldtype": "Column Break",
				},
				{
					"label": "City",
					"fieldname": "city",
					"fieldtype": "Data",
					"reqd": 1
				},
				{
					"label": "State",
					"fieldname": "state",
					"fieldtype": "Data"
				},
				{
					"label": "Country",
					"fieldname": "country",
					"fieldtype": "Data",
					"reqd": 1
				},
				{
					"label": "Pincode",
					"fieldname": "pincode",
					"fieldtype": "Data"
				},
				{
					"label": "GST Details",
					"fieldname": "gst_details",
					"fieldtype": "Section Break",
					"depends_on": "eval:doc.country && doc.country.toLowerCase()=='india'"
				},
				{
					"label": "GSTIN",
					"fieldname": "gstin",
					"fieldtype": "Data"
				}
			],
			primary_action: function() {
				var data = d.get_values();
				d.hide()
				
				frappe.call({
					method: "frappe.core.page.billing_info.billing_info.setup_billing_address",
					args: {
						data: data
					},
					freeze: true,
					freeze_message: __('Saving Address'),
					callback: function(r){
						frappe.ui.toolbar.clear_cache();
					}
				})
			},
		});
	
	d.show();
}
