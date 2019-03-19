frappe.pages['energy-point-history'].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Transaction',
		single_column: true,
		btn_primary: console.log

	});
	console.log(page);
	frappe.db.get_list('Energy Point Log', {
		filters: { user: frappe.session.user },
		fields: ['point', 'reason']
	})
	.then((data) => {
		console.log(data);
		$(frappe.render_template('energy_point_transactions', {data: data}))
			.appendTo(page.body);
	})
}