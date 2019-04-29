frappe.provide('frappe.route');
frappe.route_history_queue = [];
const routes_to_skip = ['Form', 'social'];

const save_routes = frappe.utils.debounce(() => {
	const routes = frappe.route_history_queue;
	frappe.route_history_queue = [];
	frappe.xcall('frappe.deferred_insert.deferred_insert', {
		'doctype': 'Route History',
		'records': routes
	}).catch(() => {
		frappe.route_history_queue.concat(routes);
	});
}, 10000);

frappe.route.on('change', () => {
	const route = frappe.get_route();
	if (is_route_useful(route)) {
		frappe.route_history_queue.push({
			'user': frappe.session.user,
			'creation': frappe.datetime.now_datetime(),
			'route': frappe.get_route_str()
		});

		save_routes();
	}
});

function is_route_useful(route) {
	if (!route[1]) {
		return false;
	} else if ((route[0] === 'List' && !route[2]) || routes_to_skip.includes(route[0])) {

		return false;
	} else {
		return true;
	}
}