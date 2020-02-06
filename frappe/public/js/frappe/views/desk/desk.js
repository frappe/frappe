import ChartWidget from "../widgets/chart_widget";
import WidgetGroup from "../widgets/widget_group";

export default class Desk {
	constructor({ wrapper }) {
		this.wrapper = wrapper;
		window.desk = this;
		this.pages = {}
		this.make();
	}

	make() {
		this.make_container();
		this.show_loading_state();
		this.fetch_desktop_settings().then(() => {
			this.make_sidebar();
			this.make_body();
			this.setup_events;
			this.hide_loading_state();
		});
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
			.call("frappe.desk.desktop.get_base_configuration_for_desk")
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
			// let icon_class = item.icon ? item.icon : 'frapicon-dashboard'
			// let icon = `<i class="icon ${icon_class}"></i>`;
			// if (icon_class.includes("frapicon-")) {
			// 	icon = `<img class="icon" src="/assets/frappe/icons/${
			// 		icon_class
			// 	}.svg">`;
			// }

			return $(`<div href="#" class="sidebar-item ${
				item.selected ? "selected" : ""
			}">
					<span class="sidebar-item-title">${item.name}</span>
				</div>`);
		};

		this.desktop_settings.forEach((item, idx) => {
			if (idx == 0) {
				item.selected = true;
			}
			get_sidebar_item(item).appendTo(this.sidebar);
		});
	}

	make_body() {
		this.pages['CRM'] = new DeskPage({
			container: this.body,
			page_name: "CRM"
		});
	}

	setup_events() {}
}

class DeskPage {
	constructor({ container, page_name }) {
		this.container = container;
		this.page_name = page_name;
		this.sections = {}
		this.make();
	}

	show() {

	}

	make() {
		this.make_page()
		this.get_data().then(res => {
			this.data = res.message;
			this.make_onboarding()
			// this.make_charts()
			this.make_shortcuts()
			this.make_cards()
		})
	}

	make_page() {
		this.page = $(`<div class="desk-page" data-page-name=${this.page_name}></div>`)
		this.page.appendTo(this.container)
	}

	get_data() {
		return frappe.call('frappe.desk.desktop.get_desktop_page', { page: this.page_name } )
	}

	make_onboarding() {
		this.sections['onboarding'] = new WidgetGroup({
			title: `Getting Started`,
			container: this.page,
			type: "onboarding",
			columns: 1,
			widgets:  [{
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
			}]
		});
	}

	make_charts() {
		this.sections['charts'] = new WidgetGroup({
			title: `${this.page_name} Dashboard`,
			container: this.page,
			type: "chart",
			columns: 1,
			widgets: this.data.charts
		});
	}

	make_shortcuts() {
		this.sections['shortcuts'] = new WidgetGroup({
			title: `Your Shortcuts`,
			container: this.page,
			type: "bookmark",
			columns: 3,
			allow_sorting: 1,
			widgets: this.data.shortcuts
		});
	}

	make_cards() {
		this.sections['cards'] = new WidgetGroup({
			title: `Reports & Masters`,
			container: this.page,
			type: "links",
			columns: 3,
			allow_sorting: 1,
			widgets: this.data.cards
		});
	}
}
