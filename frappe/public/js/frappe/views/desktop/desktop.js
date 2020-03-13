import ChartWidget from "../widgets/chart_widget";
import WidgetGroup from "../widgets/widget_group";

export default class Desktop {
	constructor({ wrapper }) {
		this.wrapper = wrapper;
		window.desk = this;
		this.pages = {};
		this.sidebar_items = {};
		this.sidebar_categories = [
			"Modules",
			"Domains",
			"Places",
			"Administration"
		];
		this.make();
	}

	make() {
		this.make_container();
		// this.show_loading_state();
		this.fetch_desktop_settings().then(() => {
			this.route();
			this.make_sidebar();
			this.setup_events();
			// this.hide_loading_state();
		});
	}

	route() {
		let page = this.get_page_to_show();
		this.show_page(page);
	}

	make_container() {
		this.container = $(`<div class="desk-container row">
				<div class="desk-sidebar"></div>
				<div class="desk-body"></div>
			</div>`);

		this.container.appendTo(this.wrapper);
		this.sidebar = this.container.find(".desk-sidebar");
		this.body = this.container.find(".desk-body");
	}

	show_loading_state() {
		// Add skeleton
		let loading_sidebar = $(
			'<div class="skeleton skeleton-full" style="height: 90vh;"></div>'
		);
		let loading_body = $(
			`<div class="skeleton skeleton-full" style="height: 90vh;"></div>`
		);

		// Append skeleton to body
		loading_sidebar.appendTo(this.sidebar);
		loading_body.appendTo(this.body);
	}

	hide_loading_state() {
		// Remove all skeleton
		this.container.find(".skeleton").remove();
	}

	fetch_desktop_settings() {
		return frappe
			.call("frappe.desk.desktop.get_desk_sidebar_items")
			.then(response => {
				if (response.message) {
					this.desktop_settings = response.message;
				} else {
					frappe.throw({
						title: "Couldn't Load Desk",
						message:
							"Something went wrong while loading Desk. <b>Please relaod the page</b>. If the problem persists, contact the Administrator",
						indicator: "red",
						primary_action: {
							label: "Reload",
							action: () => location.reload()
						}
					});
				}
			});
	}

	make_sidebar() {
		const get_sidebar_item = function(item) {
			return $(`<a href="${"desk#workspace/" +
				item.name}" class="sidebar-item ${
				item.selected ? "selected" : ""
			}">
					<span>${item.name}</span>
				</div>`);
		};

		const make_sidebar_category_item = item => {
			if (item.name == this.get_page_to_show()) {
				item.selected = true;
				this.current_page = item.name;
			}
			let $item = get_sidebar_item(item);
			$item.appendTo(this.sidebar);
			this.sidebar_items[item.name] = $item;
		};

		const make_category_title = name => {
			let $title = $(
				`<div class="sidebar-group-title h6 uppercase">${name}</div>`
			);
			$title.appendTo(this.sidebar);
		};

		this.sidebar_categories.forEach(category => {
			if (this.desktop_settings.hasOwnProperty(category)) {
				make_category_title(category);
				this.desktop_settings[category].forEach(item => {
					make_sidebar_category_item(item);
				});
			}
		});
	}

	show_page(page) {
		if (this.current_page && this.pages[this.current_page]) {
			this.pages[this.current_page].hide();
		}

		if (this.sidebar_items && this.sidebar_items[this.current_page]) {
			this.sidebar_items[this.current_page].removeClass("selected");
			this.sidebar_items[page].addClass("selected");
		}
		this.current_page = page;
		localStorage.current_desk_page = page;
		frappe.set_route("workspace", page);

		this.pages[page] ? this.pages[page].show() : this.make_page(page);
	}

	get_page_to_show() {
		const default_page = this.desktop_settings ? this.desktop_settings["Modules"][0].name : "Website";
		let page =
			frappe.get_route()[1] ||
			localStorage.current_desk_page ||
			default_page;
		return page;
	}

	make_page(page) {
		const $page = new DesktopPage({
			container: this.body,
			page_name: page
		});

		this.pages[page] = $page;
		return $page;
	}

	setup_events() {
		$(document).keydown(e => {
			if (e.keyCode == 9) {
				console.log("navigate");
			}
		});
	}
}

class DesktopPage {
	constructor({ container, page_name }) {
		this.container = container;
		this.page_name = page_name;
		this.sections = {};
		this.allow_customization = false
		this.make();
	}

	show() {
		this.page.show();
	}

	hide() {
		this.page.hide();
	}

	make() {
		this.make_page();
		this.get_data().then(res => {
			this.data = res.message;
			// this.make_onboarding()
			if (!this.data) {
				delete localStorage.current_desk_page;
				frappe.set_route('workspace');
				return;
			}

			this.allow_customization = this.data.allow_customization || false;

			!this.sections["onboarding"] &&
				this.data.charts.items.length &&
				this.make_charts();
			this.data.shortcuts.items.length && this.make_shortcuts();
			this.data.cards.items.length && this.make_cards();
		});
	}

	make_page() {
		this.page = $(
			`<div class="desk-page" data-page-name=${this.page_name}></div>`
		);
		this.page.appendTo(this.container);
	}

	get_data() {
		return frappe.call("frappe.desk.desktop.get_desktop_page", {
			page: this.page_name
		});
	}

	make_onboarding() {
		this.sections["onboarding"] = new WidgetGroup({
			title: `Getting Started`,
			container: this.page,
			type: "onboarding",
			columns: 1,
			widgets: [
				{
					label: "Unlock Great Customer Experience",
					subtitle: "Just a few steps, and you’re good to go.",
					steps: [
						{
							label: "Configure Lead Sources",
							completed: true
						},
						{
							label: "Add Your Leads",
							completed: false
						},
						{
							label: "Create Your First Opportunity",
							completed: false
						},
						{
							label: "Onboard your Sales Team",
							completed: false
						},
						{
							label: "Assign Territories",
							completed: false
						}
					]
				}
			]
		});
	}

	make_charts() {
		this.sections["charts"] = new WidgetGroup({
			title: this.data.charts.label || `${this.page_name} Dashboard`,
			container: this.page,
			type: "chart",
			columns: 1,
			allow_sorting: false,
			widgets: this.data.charts.items
		});
	}

	make_shortcuts() {
		this.sections["shortcuts"] = new WidgetGroup({
			title: this.data.shortcuts.label || `Your Shortcuts`,
			container: this.page,
			type: "bookmark",
			columns: 3,
			allow_sorting: this.allow_customization && frappe.is_mobile(),
			widgets: this.data.shortcuts.items
		});
	}

	make_cards() {
		let cards = new WidgetGroup({
			title: this.data.cards.label || `Reports & Masters`,
			container: this.page,
			type: "links",
			columns: 3,
			allow_sorting: this.allow_customization && frappe.is_mobile(),
			widgets: this.data.cards.items
		});

		this.sections["cards"] = cards;

		const legend = [
			{
				color: "blue",
				description: __("Important")
			},
			{
				color: "orange",
				description: __("No Records Created")
			},
			{
				color: "red",
				description: __("Has Open Entries")
			}
		].map(item => {
			return `<div class="legend-item small text-muted justify-flex-start">
				<span class="indicator ${item.color}"></span>
				<span class="link-content ellipsis" draggable="false">${item.description}</span>
			</div>`;
		});

		$(`<div class="legend">
			${legend.join("\n")}
		</div>`).insertAfter(cards.body);
	}
}