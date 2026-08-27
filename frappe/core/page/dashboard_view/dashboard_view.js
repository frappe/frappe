// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

/**
 * `/app/dashboard-view/<reference>` — the one desk dashboard route. Two
 * renderers draw it: the `insights.dashboard` island, or the legacy widget
 * dashboard below.
 *
 * There is one route, not a second page beside this one. Every link ever
 * written to a desk dashboard points here, so a site that turns Insights
 * rendering on upgrades in place and keeps its sidebars.
 *
 * The page asks `frappe/utils/dashboard_renderer.py` once per route and
 * branches on the answer. That module decides what a reference names and which
 * renderer draws it.
 */

frappe.provide("frappe.dashboards");
frappe.provide("frappe.dashboards.chart_sources");

const ISLAND = "insights.dashboard";

// Set on <body> while the island renderer is on screen. `dashboard_view.scss`
// keys the bounded page off this class — read the comment there for why the
// page stops document scrolling. The legacy renderer grows with its widgets and
// keeps the scroll it has always had, so the route alone cannot decide this.
const ISLAND_PAGE_CLASS = "dashboard-view-island-page";

frappe.pages["dashboard-view"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		single_column: true,
	});

	// This route draws no page head by default. The island draws its own header,
	// so desk's would be a second and emptier one above it. The head is off from
	// the start, not off once the renderer is known: that answer costs a round
	// trip on a site with Insights, and the head would show for all of it. The
	// legacy renderer asks for the head back when it draws.
	//
	// The page object itself stays. The body sidebar and the workspace dock
	// resolve their visibility against it, so a route with no page loses the app
	// frame too.
	page.toggle_page_head(false);

	// One container per renderer, both made up front. The legacy renderer empties
	// what it is given, so the two must never share a parent they draw into.
	const content = $(wrapper).find(".page-content").empty();
	const legacy_container = $('<div class="dashboard-view-legacy">').appendTo(content);
	const island_container = $('<div class="dashboard-view-island">').appendTo(content);

	// The legacy renderer has been reachable as `frappe.dashboard` for years.
	frappe.dashboard = new Dashboard(legacy_container, page);
	const insights = new InsightsDashboard(island_container, page);

	$(wrapper).on("show", async () => {
		const route = frappe.get_route_str();
		const reference = frappe.get_route().slice(1).join("/");

		const renderer = await frappe.ui.get_dashboard_renderer(reference);
		// The route can move, inside this page or off it, while the call is out.
		if (frappe.get_route_str() !== route) return;

		if (renderer === "insights") {
			frappe.dashboard.hide();
			insights.show(reference);
		} else {
			insights.hide();
			frappe.dashboard.show();
		}
	});

	$(wrapper).on("hide", () => insights.hide());
};

/**
 * The Insights renderer: one container for the `insights.dashboard` island.
 *
 * The island owns the whole page — its header (breadcrumbs, title, freshness,
 * actions), the filter bar, the grid, and every state, including the one it
 * shows when a reference resolves to nothing. Desk hides its page head while
 * the island is on screen, so the page has one header.
 *
 * The reference passes through as the route wrote it. A reference can span
 * segments (`insights/sales-performance`), and Insights resolves it. Desk never
 * parses it.
 */
class InsightsDashboard {
	constructor(container, page) {
		this.root = container;
		this.container = container[0];
		this.page = page;

		// The island mounts once and takes a new reference as a prop after that.
		// Desk keeps the page alive across route changes within it, so the island
		// re-fetches while the Vue app and its shadow root stay put.
		this.handle = null;
		this.mounting = false;
		this.reference = null;
	}

	show(reference) {
		this.root.show();
		document.body.classList.add(ISLAND_PAGE_CLASS);

		// The head is already off for this route, and it carried little: a generic
		// "Dashboard" title, and a breadcrumb that went blank when the route moved
		// inside the page. The island's own header carries both correctly. The menu
		// belongs to the renderer on screen, so the legacy entries go with it.
		this.page.clear_menu();

		if (this.handle || this.mounting) {
			if (reference === this.reference) return;
			this.reference = reference;
			this.handle?.update({ dashboard: reference });
			return;
		}

		this.reference = reference;
		this.mounting = true;
		frappe.ui
			.mount_island(ISLAND, this.container, { props: { dashboard: reference } })
			.then((island) => {
				this.mounting = false;
				// The page can be left, or a legacy dashboard routed to inside it,
				// while the island's module loads. Both clear the reference.
				if (this.reference === null) return island.unmount();
				this.handle = island;
				this.handle.update({ dashboard: this.reference });
			})
			.catch((error) => {
				this.mounting = false;
				console.error(`could not mount the "${ISLAND}" island`, error);
			});
	}

	hide() {
		this.root.hide();
		document.body.classList.remove(ISLAND_PAGE_CLASS);
		this.reference = null;
		this.handle?.unmount();
		this.handle = null;
	}
}

class Dashboard {
	constructor(container, page) {
		this.root = container;
		$(`<div class="dashboard" style="overflow: visible; margin: var(--margin-md);">
			<div class="dashboard-graph"></div>
		</div>`).appendTo(container.empty());
		this.container = container.find(".dashboard-graph");
		this.page = page;
	}

	async show() {
		this.root.show();
		// This renderer draws its widgets, title and breadcrumb into desk's head,
		// so it asks for the head back.
		this.page.toggle_page_head(true);
		this.route = frappe.get_route();
		if (this.route.length > 1) {
			// from route
			const reference = this.route.slice(-1)[0];
			// The route is shared with the Insights renderer, so a reference that
			// names no `Dashboard` reaches this renderer whenever Insights rendering
			// is off. Without this check `render_cards` and `render_charts` both run
			// and both raise desk's global "not found" dialog for one route.
			//
			// The lookup answers with the document's own name, not the reference the
			// link was written with. A route reaches here lowercased often enough
			// that the crumb and the title would otherwise read `selling`.
			const { message } = await frappe.db.get_value("Dashboard", reference, "name");
			if (message?.name) {
				this.set_breadcrumbs(message.name);
				this.show_dashboard(message.name);
			} else {
				this.set_breadcrumbs();
				this.show_missing(reference);
			}
		} else {
			this.set_breadcrumbs();
			// last opened
			if (frappe.last_dashboard) {
				frappe.set_re_route("dashboard-view", frappe.last_dashboard);
			} else {
				// default dashboard
				frappe.db.get_list("Dashboard", { filters: { is_default: 1 } }).then((data) => {
					if (data && data.length) {
						frappe.set_re_route("dashboard-view", data[0].name);
					} else {
						// no default, get the latest one
						frappe.db.get_list("Dashboard", { limit: 1 }).then((data) => {
							if (data && data.length) {
								frappe.set_re_route("dashboard-view", data[0].name);
							} else {
								// create a new dashboard!
								frappe.new_doc("Dashboard");
							}
						});
					}
				});
			}
		}
	}

	// This renderer gives up the page menu and body, so the next `show` draws
	// both again. Only a renderer switch inside the page reaches here. Leaving
	// the page keeps what was drawn, as it always has.
	hide() {
		this.root.hide();
		this.dashboard_name = null;
	}

	// The reference names nothing this renderer can draw. `dashboard_name` stays
	// empty so the next real dashboard on this route draws itself again.
	show_missing(name) {
		this.dashboard_name = null;
		frappe.utils.set_title(__("Dashboard"));
		this.page.clear_menu();
		this.container.empty().append(
			frappe.ui.empty_state({
				icon: "layout-dashboard",
				title: __("No dashboard named {0}", [name]),
				description: __("Check the link, or open one from the dashboard list."),
				actions: [
					{
						label: __("Dashboard List"),
						variant: "subtle",
						onclick: () => frappe.set_route("List", "Dashboard"),
					},
				],
			})
		);
	}

	show_dashboard(current_dashboard_name) {
		if (this.dashboard_name !== current_dashboard_name) {
			this.dashboard_name = current_dashboard_name;
			let title = this.dashboard_name;
			if (!this.dashboard_name.toLowerCase().includes(__("dashboard"))) {
				// ensure dashboard title has "dashboard"
				title = __("{0} Dashboard", [__(title)]);
			}
			// The page head has no title slot: `set_title` writes into the
			// `.title-text` crumb, which is the "Dashboard" list link. Naming the
			// browser tab directly leaves the crumb trail intact.
			frappe.utils.set_title(__(title));
			this.set_dropdown();
			this.container.empty();
			this.refresh();
		}
		this.charts = {};
		frappe.last_dashboard = current_dashboard_name;
	}

	set_breadcrumbs(label) {
		frappe.breadcrumbs.add({ module: "Desk", doctype: "Dashboard", label: label });
	}

	refresh() {
		frappe.run_serially([() => this.render_cards(), () => this.render_charts()]);
	}

	render_charts() {
		return this.get_permitted_items(
			"frappe.desk.doctype.dashboard.dashboard.get_permitted_charts"
		).then((charts) => {
			if (!charts.length) {
				return;
			}

			frappe.dashboard_utils.get_dashboard_settings().then((settings) => {
				let chart_config = settings.chart_config ? JSON.parse(settings.chart_config) : {};
				this.charts = charts.map((chart) => {
					return {
						chart_name: chart.chart,
						label: chart.chart,
						chart_settings: chart_config[chart.chart] || {},
						...chart,
					};
				});

				this.chart_group = new frappe.widget.WidgetGroup({
					title: null,
					container: this.container,
					type: "chart",
					columns: 2,
					options: {
						allow_sorting: false,
						allow_create: false,
						allow_delete: false,
						allow_hiding: false,
						allow_edit: false,
					},
					widgets: this.charts,
				});
			});
		});
	}

	render_cards() {
		return this.get_permitted_items(
			"frappe.desk.doctype.dashboard.dashboard.get_permitted_cards"
		).then((cards) => {
			if (!cards.length) {
				return;
			}

			this.number_cards = cards.map((card) => {
				return {
					name: card.card,
				};
			});

			this.number_card_group = new frappe.widget.WidgetGroup({
				container: this.container,
				type: "number_card",
				columns: 3,
				options: {
					allow_sorting: false,
					allow_create: false,
					allow_delete: false,
					allow_hiding: false,
					allow_edit: false,
				},
				widgets: this.number_cards,
			});
		});
	}

	get_permitted_items(method) {
		return frappe
			.xcall(method, {
				dashboard_name: this.dashboard_name,
			})
			.then((items) => {
				return items;
			});
	}

	set_dropdown() {
		this.page.clear_menu();

		this.page.add_menu_item(__("Edit"), () => {
			frappe.set_route("Form", "Dashboard", frappe.dashboard.dashboard_name);
		});

		this.page.add_menu_item(__("New"), () => {
			frappe.new_doc("Dashboard");
		});

		this.page.add_menu_item(__("Refresh All"), () => {
			this.chart_group && this.chart_group.widgets_list.forEach((chart) => chart.refresh());
			this.number_card_group &&
				this.number_card_group.widgets_list.forEach((card) => card.render_card());
		});

		frappe.db.get_list("Dashboard").then((dashboards) => {
			dashboards.map((dashboard) => {
				let name = dashboard.name;
				if (name != this.dashboard_name) {
					this.page.add_menu_item(
						name,
						() => frappe.set_route("dashboard-view", name),
						1
					);
				}
			});
		});
	}
}
