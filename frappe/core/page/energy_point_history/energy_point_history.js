frappe.pages['energy-point-history'].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Energy Point History',
		single_column: true,
		btn_primary: console.log

	});
	frappe.db.get_list('Energy Point Log', {
		filters: { user: frappe.session.user, type: ['not in', 'Review'] },
		fields: ['points', 'reason', 'rule', 'reference_doctype', 'reference_name', 'type']
	}).then((data) => {
		$(frappe.render_template('energy_point_transactions', {data: data}))
			.appendTo(page.body);
	});
}