// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

/**
 * `/desk/dashboard-view/<name>` — the one desk dashboard route. The page loads
 * the `Dashboard` the route names before it draws anything.
 *
 * Two renderers draw the document. An installed app claims it with a
 * `dashboard_renderer` hook, and the answer rides down on the document as
 * `__onload.island_renderer` (frappe/desk/island_renderer.py). The key present
 * means an island draws the dashboard. The key absent means the legacy widget
 * renderer below draws it. There is no third answer and no null sentinel.
 *
 * A name no `Dashboard` answers to belongs to neither renderer, so the page
 * draws that state itself.
 */

frappe.provide("frappe.dashboards");
frappe.provide("frappe.dashboards.chart_sources");

// Set on <body> while an island is on screen. `dashboard_view.scss` keys the
// bounded page off this class — read the comment there for why the page stops
// document scrolling. The legacy renderer grows with its widgets and keeps the
// scroll it has always had, so the route alone cannot decide this.
const ISLAND_PAGE_CLASS = "dashboard-view-island-page";

frappe.pages["dashboard-view"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		single_column: true,
	});

	// This route draws no page head by default. An island draws its own header,
	// so desk's would be a second and emptier one above it. The head is off from
	// the start, not off once the document is loaded: that answer costs a round
	// trip, and the head would show for all of it. The two renderers that want
	// the head ask for it back when they draw.
	//
	// The page object itself stays. The body sidebar and the workspace dock
	// resolve their visibility against it, so a route with no page loses the app
	// frame too.
	page.toggle_page_head(false);

	// One container per state, all made up front. The legacy renderer empties what
	// it is given, so no two of these may share a parent they draw into.
	const content = $(wrapper).find(".page-content").empty();
	const legacy_container = $('<div class="dashboard-view-legacy">').appendTo(content);
	const island_container = $('<div class="dashboard-view-island">').appendTo(content);
	const missing_container = $('<div class="dashboard-view-missing">').appendTo(content).hide();

	// The legacy renderer has been reachable as `frappe.dashboard` for years.
	frappe.dashboard = new Dashboard(legacy_container, page);
	const island = new IslandDashboard(island_container, page);

	$(wrapper).on("show", async () => {
		const name = frappe.get_route()[1];
		// The route always carries a name. A bare /desk/dashboard-view names no
		// document, so send the reader to the list instead.
		if (!name) return frappe.set_route("List", "Dashboard");

		const route = frappe.get_route_str();
		const doc = await frappe.model.with_doc("Dashboard", name);
		// The route can move, inside this page or off it, while the call is out.
		// Two fetches can also land out of order, and the older one would draw a
		// document the reader has already left.
		if (frappe.get_route_str() !== route) return;

		if (!doc) {
			island.hide();
			frappe.dashboard.hide();
			return show_missing(name);
		}

		missing_container.hide();

		const renderer = doc.__onload?.island_renderer;
		if (renderer) {
			frappe.dashboard.hide();
			island.show(renderer);
		} else {
			island.hide();
			frappe.dashboard.show(doc);
		}
	});

	$(wrapper).on("hide", () => island.hide());

	function show_missing(name) {
		page.toggle_page_head(true);
		page.clear_menu();
		frappe.breadcrumbs.add({ module: "Desk", doctype: "Dashboard" });
		frappe.utils.set_title(__("Dashboard"));
		missing_container
			.show()
			.empty()
			.append(
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
};

/**
 * The island renderer: one container for whatever island the document names.
 *
 * The island owns the whole page — its header (breadcrumbs, title, actions), the
 * filter bar, the grid, and every state below the document, the not-permitted
 * one included. Desk hides its page head while the island is on screen, so the
 * page has one header.
 *
 * Desk passes the island name and the props through as the hook returned them.
 * It reads neither.
 */
class IslandDashboard {
	constructor(container, page) {
		this.root = container;
		this.container = container[0];
		this.page = page;

		// The renderer on screen, or the one being mounted. `null` between a hide
		// and the next show.
		this.renderer = null;
		this.handle = null;
	}

	show(renderer) {
		this.root.show();
		document.body.classList.add(ISLAND_PAGE_CLASS);

		// The legacy renderer asks for the head back when it draws, and it may have
		// drawn on this page before this document. The menu belongs to the renderer
		// on screen, so the legacy entries go with it.
		this.page.toggle_page_head(false);
		this.page.clear_menu();

		const mounted = this.renderer;
		this.renderer = renderer;

		// The same island takes the next document as props. Desk keeps the page
		// alive across route changes within it, so the island re-fetches while its
		// Vue app and shadow root stay put.
		if (mounted?.island === renderer.island) {
			this.handle?.update(renderer.props);
			return;
		}

		this.mount(renderer);
	}

	async mount(renderer) {
		try {
			const island = await frappe.ui.mount_island(renderer.island, this.container, {
				props: renderer.props,
			});
			// The page can be left, or another island routed to inside it, while
			// this module loads. Both leave this mount with nothing to draw.
			if (this.renderer?.island !== renderer.island) return island.unmount();
			this.handle = island;
			this.handle.update(this.renderer.props);
		} catch (error) {
			console.error(`could not mount the "${renderer.island}" island`, error);
		}
	}

	hide() {
		this.root.hide();
		document.body.classList.remove(ISLAND_PAGE_CLASS);
		this.renderer = null;
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

	// Takes the document the page loaded. The name it draws with is the
	// document's own, not the route segment: a link reaches this page lowercased
	// often enough that the crumb and the title would otherwise read `selling`.
	show(doc) {
		this.root.show();
		// This renderer draws its widgets, title and breadcrumb into desk's head,
		// so it asks for the head back.
		this.page.toggle_page_head(true);
		this.set_breadcrumbs(doc.name);
		this.show_dashboard(doc.name);
	}

	// This renderer gives up the page menu and body, so the next `show` draws
	// both again. Only a renderer switch inside the page reaches here. Leaving
	// the page keeps what was drawn, as it always has.
	hide() {
		this.root.hide();
		this.dashboard_name = null;
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
			// `empty()` drops the widget nodes without going through the group, so
			// an island inside a chart would stay mounted on a detached node.
			this.chart_group?.destroy();
			this.container.empty();
			this.refresh();
		}
		this.charts = {};
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
