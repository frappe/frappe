nts.route_history_queue = [];
const routes_to_skip = ["Form", "social", "setup-wizard", "recorder"];

const save_routes = nts.utils.debounce(() => {
	if (nts.session.user === "Guest") return;
	const routes = nts.route_history_queue;
	if (!routes.length) return;

	nts.route_history_queue = [];

	nts
		.xcall("nts.desk.doctype.route_history.route_history.deferred_insert", {
			routes: routes,
		})
		.catch(() => {
			nts.route_history_queue.concat(routes);
		});
}, 10000);

nts.router.on("change", () => {
	const route = nts.get_route();
	if (is_route_useful(route)) {
		nts.route_history_queue.push({
			creation: nts.datetime.now_datetime(),
			route: nts.get_route_str(),
		});

		save_routes();
	}
});

function is_route_useful(route) {
	if (!route[1]) {
		return false;
	} else if ((route[0] === "List" && !route[2]) || routes_to_skip.includes(route[0])) {
		return false;
	} else {
		return true;
	}
}
