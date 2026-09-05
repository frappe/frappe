// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

/**
 * `/desk/dashboard-view/<name>` is the one desk dashboard route. The page loads
 * the `Dashboard` the route names, clears whatever drew last, and shows one of
 * three states.
 *
 * An installed app claims the document in its own `onload` handler, which puts
 * `{name, props}` on `__onload.island`. When the key is present, an island
 * draws the dashboard. When the key is absent, the legacy widget renderer draws
 * it. An unknown name belongs to neither, and the page shows the missing state.
 * There is no third answer and no null sentinel.
 *
 * Nothing stays alive across a draw. Every entry to the page builds what it
 * draws, and `clear()` releases it, so the island re-mounts instead of taking
 * the next document as props.
 */

frappe.provide("frappe.dashboards");
frappe.provide("frappe.dashboards.chart_sources");

// Set on <body> while an island is on screen. `dashboard_view.scss` keys the
// bounded page off this class. The comment there says why the island gets a
// fixed box instead of the page scroll. The legacy renderer grows with its
// widgets and keeps the page scroll, so the route alone cannot decide this.
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
		// The route can move, inside this page or off it, while the fetch is
		// pending. Two fetches can also land out of order, and the older one would
		// draw a document the reader left.
		if (frappe.get_route_str() !== route) return;

		clear();
		if (!doc) return show_missing(name);
		// `as_dict` drops an empty `__onload`, so no key at all is the common case.
		if (doc.__onload?.island) return show_island(doc);
		show_legacy(doc);
	});

	$(wrapper).on("hide", clear);

	// Releases everything the last draw left, in one place, so no renderer has
	// to know what drew before it. `empty()` alone would drop the widget nodes
	// without the group, and an island inside a chart would stay mounted on a
	// detached node.
	function clear() {
		island?.unmount();
		island = null;
		frappe.dashboard?.destroy();
		frappe.dashboard = null;
		page.clear_menu();
		content.empty();
		document.body.classList.remove(ISLAND_PAGE_CLASS);
	}

	/** The missing state, for an unknown dashboard name. It needs only the name. */
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
	 * The island renderer. One container holds whatever island the document names.
	 *
	 * The island owns the body: the filter bar, the grid, and every state below
	 * the document, the not-permitted one included. Desk keeps its page head and
	 * sets the chrome from what the island reports. `title` names the page, and
	 * `actions` fills the page menu. See
	 * ui/island/decisions/0010-a-page-island-reports-title-and-actions.md.
	 *
	 * Desk passes the island name and the props through as the document carried
	 * them. It reads neither.
	 */
	function show_island(doc) {
		const container = $('<div class="dashboard-view-island">').appendTo(content);
		document.body.classList.add(ISLAND_PAGE_CLASS);

		// The document's own name until the island reports a title, so the crumb
		// trail is right while the island loads.
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
	 * The page head has no title slot of its own. `page.set_title` writes into the
	 * `.title-text` crumb, which is the "Dashboard" list link, and the next
	 * `breadcrumbs.update()` overwrites it. So the title goes to the last crumb,
	 * where the legacy renderer puts the document name, and to the browser tab.
	 * `Dashboard.show` below relies on the same fact.
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
	 * An `Action` is `{ label, icon? }` plus either `onClick` or `href`. An `href`
	 * leads out of the app, and desk opens it in a new tab. Desk's menu rows carry
	 * no icon, so the icon goes unread. It names a lucide icon the island ships,
	 * and desk resolves a name against its own sprite.
	 *
	 * A desk menu row is a click handler, not a link, because `add_dropdown_item`
	 * writes `href="#"` itself. So the new tab is `window.open`, not a `target`.
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

	// The global `frappe.dashboard` predates this page's states. It stays for
	// whatever reaches the legacy renderer through it.
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

	// Draws the document the page loaded. The name is the document's own, not
	// the route segment. A link often reaches this page lowercased, and the
	// crumb and the title would otherwise read `selling`.
	show(doc) {
		this.dashboard_name = doc.name;
		this.set_breadcrumbs(doc.name);

		let title = this.dashboard_name;
		if (!this.dashboard_name.toLowerCase().includes(__("dashboard"))) {
			// ensure dashboard title has "dashboard"
			title = __("{0} Dashboard", [__(title)]);
		}
		// See `set_island_title` for why the title goes to the browser tab and
		// not to `page.set_title`.
		frappe.utils.set_title(__(title));
		this.set_dropdown();
		this.charts = {};
		this.refresh();
	}

	// The page drops the nodes. A widget group holds more than its nodes,
	// because a chart widget can hold a mounted island, so the group releases
	// itself.
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
				// The reader can leave the page while the calls are pending, and a
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
