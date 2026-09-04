// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

/**
 * `/desk/dashboard-view/<name>` — the one desk dashboard route. The page loads
 * the `Dashboard` the route names, clears whatever drew last, and draws one of
 * three things.
 *
 * An installed app claims the document in its own `onload` handler, which puts
 * `{name, props}` on `__onload.island`. The key present means an island draws
 * the dashboard. The key absent means the legacy widget renderer draws it. A
 * name no `Dashboard` answers to belongs to neither, and the empty state draws
 * that. There is no third answer and no null sentinel.
 *
 * Nothing is kept alive across a draw. Every entry to the page builds what it
 * draws and `clear()` releases it, so the island re-mounts rather than taking
 * the next document as props.
 */

frappe.provide("frappe.dashboards");
frappe.provide("frappe.dashboards.chart_sources");

// Set on <body> while an island is on screen. `dashboard_view.scss` keys the
// bounded page off this class — read the comment there for why the island gets a
// fixed box instead of the page scroll. The legacy renderer grows with its
// widgets and keeps the scroll it has always had, so the route alone cannot
// decide this.
const ISLAND_PAGE_CLASS = "dashboard-view-island-page";

frappe.pages["dashboard-view"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		single_column: true,
	});

	const content = $(wrapper).find(".page-content");
	// The island on screen, while one is.
	let island = null;

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

		clear();
		if (!doc) return show_missing(name);
		if (doc.__onload.island) return show_island(doc);
		show_legacy(doc);
	});

	$(wrapper).on("hide", clear);

	// Everything the last draw left, in one place, so no renderer has to know
	// what drew before it. `empty()` alone would drop the widget nodes without
	// going through the group, and an island inside a chart would stay mounted
	// on a detached node.
	function clear() {
		island?.unmount();
		island = null;
		frappe.dashboard?.destroy();
		frappe.dashboard = null;
		page.clear_menu();
		content.empty();
		document.body.classList.remove(ISLAND_PAGE_CLASS);
	}

	/** A name no `Dashboard` answers to. It draws from the name alone. */
	function show_missing(name) {
		frappe.breadcrumbs.add({ module: "Desk", doctype: "Dashboard" });
		frappe.utils.set_title(__("Dashboard"));
		content.append(
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

	/**
	 * The island renderer: one container for whatever island the document names.
	 *
	 * The island owns the body — the filter bar, the grid, and every state below
	 * the document, the not-permitted one included. Desk keeps its page head and
	 * draws the chrome from what the island reports: `title` names the page,
	 * `actions` fills the page menu
	 * (ui/island/decisions/0010-an-island-reports-title-and-actions.md).
	 *
	 * Desk passes the island name and the props through as the document carried
	 * them. It reads neither.
	 */
	function show_island(doc) {
		const container = $('<div class="dashboard-view-island">').appendTo(content);
		document.body.classList.add(ISLAND_PAGE_CLASS);

		// The document's own name until the island reports a title, so the crumb
		// trail is right for the round trip the island spends loading.
		set_island_title(doc.name, doc.name);

		island = frappe.ui.mount_island(doc.__onload.island.name, container[0], {
			...doc.__onload.island.props,
			onTitle: (title) => set_island_title(doc.name, title),
			onActions: (actions) => set_island_actions(actions),
		});
		island.ready.catch((error) =>
			console.error(`could not mount the "${doc.__onload.island.name}" island`, error)
		);
	}

	/**
	 * The page head has no title slot of its own: `page.set_title` writes into the
	 * `.title-text` crumb, which is the "Dashboard" list link, and the next
	 * `breadcrumbs.update()` overwrites it anyway. So the title is the last crumb,
	 * where the legacy renderer's document name also is, plus the browser tab.
	 */
	function set_island_title(docname, title) {
		const label = title || __("Dashboard");
		frappe.breadcrumbs.add({
			module: "Desk",
			doctype: "Dashboard",
			docname: docname,
			label: label,
		});
		frappe.utils.set_title(label);
	}

	/**
	 * `Action = { label, icon? }` plus either `onClick` or `href`. An `href` leaves
	 * the app, and desk opens what leaves it in a new tab. Desk's menu rows carry no
	 * icon, so the icon goes unread: it names a lucide icon the island ships, and
	 * desk resolves a name against its own sprite.
	 *
	 * A desk menu row is a click handler, not a link — `add_dropdown_item` writes
	 * `href="#"` itself — so the new tab is `window.open`, not a `target`.
	 *
	 * An empty list clears the menu, which hides the button with it.
	 */
	function set_island_actions(actions) {
		page.clear_menu();
		(actions || []).forEach((action) => {
			const click = action.href ? () => window.open(action.href, "_blank") : action.onClick;
			page.add_menu_item(action.label, click);
		});
	}

	// The legacy renderer has been reachable as `frappe.dashboard` for years.
	function show_legacy(doc) {
		frappe.dashboard = new Dashboard(content, page);
		frappe.dashboard.show(doc);
	}
};

class Dashboard {
	constructor(container, page) {
		$(`<div class="dashboard" style="overflow: visible; margin: var(--margin-md);">
			<div class="dashboard-graph"></div>
		</div>`).appendTo(container.empty());
		this.container = container.find(".dashboard-graph");
		this.page = page;
	}

	// Takes the document the page loaded, and draws it. The name it draws with is
	// the document's own, not the route segment: a link reaches this page
	// lowercased often enough that the crumb and the title would otherwise read
	// `selling`.
	show(doc) {
		this.dashboard_name = doc.name;
		this.set_breadcrumbs(doc.name);

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
		this.charts = {};
		this.refresh();
	}

	// The page drops the nodes. A widget group holds more than its nodes — a
	// chart widget can hold a mounted island — so it is released through itself.
	destroy() {
		this.destroyed = true;
		this.chart_group?.destroy();
	}

	set_breadcrumbs(docname) {
		frappe.breadcrumbs.add({ module: "Desk", doctype: "Dashboard", docname: docname });
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
				// The reader can leave the page while the calls are out, and a
				// group built after that holds its widgets on a detached node.
				if (this.destroyed) {
					return;
				}

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
			// as in render_charts: the page can be gone by now
			if (this.destroyed || !cards.length) {
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
