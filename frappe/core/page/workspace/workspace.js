frappe.pages['workspace'].on_page_load = function(wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		name: 'workspace',
		title: __("Workspace"),
	});

	frappe.workspace = new Workspace(wrapper);
	$(wrapper).bind('show', function() {
		frappe.workspace.show();
	});
}

class Workspace {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = wrapper.page;
		this.prepare_container();
		this.pages = {};
		this.sidebar_items = {};
		this.sidebar_categories = [
			"Modules",
			"Domains",
			"Places",
			"Administration"
		];

		this.fetch_desktop_settings().then(() => {
			this.make_sidebar();
		})
	}
	
	show() {
		let page = this.get_page_to_show();
		this.page.set_title(`${__(page)} Workspace`);
		frappe.set_route('workspace', page);
		this.show_page(page);
	}

	prepare_container() {
		let list_sidebar = $(`<div class="list-sidebar overlay-sidebar hidden-xs hidden-sm">
			<div class="desk-sidebar list-unstyled sidebar-menu"><div>
		</div>`).appendTo(this.wrapper.find(".layout-side-section"));
		this.sidebar = list_sidebar.find(".desk-sidebar");
		
		this.body = this.wrapper.find(".layout-main-section");
	}

	get_page_to_show() {
		let default_page;
		
		if (localStorage.current_workspace) {
			default_page = localStorage.current_workspace;
		} else if (this.desktop_settings) {
			default_page = this.desktop_settings["Modules"][0].name;
		} else if (frappe.boot.allowed_workspaces) {
			default_page = frappe.boot.allowed_workspaces[0].name;
		} else {
			default_page = "Website";
		}
		
		let page = frappe.get_route()[1] || default_page;
		
		return page;
	}

	fetch_desktop_settings() {
		return frappe
			.call("frappe.desk.desktop.get_desk_sidebar_items")
			.then(response => {
				if (response.message) {
					this.desktop_settings = response.message;
				} else {
					frappe.throw({
						title: __("Couldn't Load Desk"),
						message:
							__("Something went wrong while loading Desk. <b>Please relaod the page</b>. If the problem persists, contact the Administrator"),
						indicator: "red",
						primary_action: {
							label: __("Reload"),
							action: () => location.reload()
						}
					});
				}
			});
	}

	make_sidebar() {
		this.sidebar_categories.forEach(category => {
			if (this.desktop_settings[category]) {
				this.build_sidebar_section(category, this.desktop_settings[category])
			}
		});
	}

	build_sidebar_section(title, items) {
		let sidebar_section = $(`<div class="sidebar-section">
		</div>`)
		
		// DO NOT REMOVE: Comment to load translation
		// __("Modules") __("Domains") __("Places") __("Administration")
		$(`<div class="list-sidebar-label">${__(title)}</div>`)
			.appendTo(sidebar_section);

		const get_sidebar_item = function(item) {
			return $(`<a 
						href="${"desk#workspace/" + item.name}"
						class="desk-sidebar-item ${ item.selected ? "selected" : "" }"
				>
				<div> ${frappe.utils.icon(item.icon || "folder-normal", "md")} </div>
				<div> ${item.label || item.name} </div>
			</a>`);
		};

		const make_sidebar_category_item = item => {
			if (item.name == this.get_page_to_show()) {
				item.selected = true;
				this.current_page = item.name;
			}
			
			let $item = get_sidebar_item(item);

			$item.clone().appendTo(sidebar_section);
			this.sidebar_items[item.name] = $item;
		};

		items.forEach(item => make_sidebar_category_item(item));

		sidebar_section.appendTo(this.sidebar)
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
		
		this.pages[page] ? this.pages[page].show() : this.make_page(page);
	}

	make_page(page) {
		const $page = new DesktopPage({
			container: this.body,
			page_name: page
		});

		this.pages[page] = $page;
		return $page;
	}
}

class DesktopPage {
	constructor({ container, page_name }) {
		frappe.desk_page = this;
		this.container = container;
		this.page_name = page_name;
		this.sections = {};
		this.allow_customization = false;
		this.reload();
	}

	show() {
		frappe.desk_page = this;
		this.page.show();
		if (this.sections.shortcuts) {
			this.sections.shortcuts.widgets_list.forEach(wid => {
				wid.set_actions();
			});
		}
	}

	hide() {
		this.page.hide();
	}

	reload() {
		this.in_customize_mode = false;
		this.page && this.page.remove();
		this.make();
		this.setup_events();
	}

	make() {
		this.page = $(`<div class="desk-page" data-page-name=${this.page_name}></div>`);
		this.page.appendTo(this.container);

		this.get_data().then(res => {
			this.data = res.message;
			if (!this.data) {
				delete localStorage.current_desk_page;
				frappe.set_route("workspace");
				return;
			}

			this.refresh();
		});
	}

	refresh() {
		this.page.empty();
		this.allow_customization = this.data.allow_customization || false;

		if (frappe.is_mobile()) {
			this.allow_customization = false;
		}

		this.data.onboarding && this.data.onboarding.items.length && this.make_onboarding();
		this.make_charts().then(() => {
			this.make_shortcuts();
			this.make_cards();
		});
	}

	get_data() {
		return frappe.call("frappe.desk.desktop.get_desktop_page", {
			page: this.page_name
		});
	}

	setup_events() {
		$(document.body).on('toggleFullWidth', () => this.refresh());
	}

	customize() {
		if (this.in_customize_mode) {
			return;
		}

		// We need to remove this as the  chart group will be visible during customization
		$('.widget.onboarding-widget-box').hide();

		this.customize_link.hide();
		this.save_or_discard_link.show();

		Object.keys(this.sections).forEach(section => {
			this.sections[section].customize();
		});
		this.in_customize_mode = true;

	}

	save_customization() {
		const config = {};

		if (this.sections.charts) config.charts = this.sections.charts.get_widget_config();
		if (this.sections.shortcuts) config.shortcuts = this.sections.shortcuts.get_widget_config();
		if (this.sections.cards) config.cards = this.sections.cards.get_widget_config();

		frappe.call('frappe.desk.desktop.save_customization', {
			page: this.page_name,
			config: config
		}).then(res => {
			if (res.message) {
				frappe.msgprint({ message: __("Customizations Saved Successfully"), title: __("Success")});
				this.reload();
			} else {
				frappe.throw({message: __("Something went wrong while saving customizations"), title: __("Failed")});
				this.reload();
			}
		});
	}

	make_onboarding() {
		this.onboarding_widget = frappe.widget.make_widget({
			label: this.data.onboarding.label || __(`Let's Get Started`),
			subtitle: this.data.onboarding.subtitle,
			steps: this.data.onboarding.items,
			success: this.data.onboarding.success,
			docs_url: this.data.onboarding.docs_url,
			user_can_dismiss: this.data.onboarding.user_can_dismiss,
			widget_type: 'onboarding',
			container: this.page,
			options: {
				allow_sorting: false,
				allow_create: false,
				allow_delete: false,
				allow_hiding: false,
				allow_edit: false,
				max_widget_count: 2,
			}
		});
	}

	make_charts() {
		return frappe.dashboard_utils.get_dashboard_settings().then(settings => {
			let chart_config = settings.chart_config ? JSON.parse(settings.chart_config): {};
			if (this.data.charts.items) {
				this.data.charts.items.map(chart => {
					chart.chart_settings = chart_config[chart.chart_name] || {};
				});
			}

			this.sections["charts"] = new frappe.widget.WidgetGroup({
				container: this.page,
				type: "chart",
				columns: 1,
				hidden: Boolean(this.onboarding_widget),
				options: {
					allow_sorting: this.allow_customization,
					allow_create: this.allow_customization,
					allow_delete: this.allow_customization,
					allow_hiding: false,
					allow_edit: true,
					max_widget_count: 2,
				},
				widgets: this.data.charts.items
			});
		});
	}

	make_shortcuts() {
		this.sections["shortcuts"] = new frappe.widget.WidgetGroup({
			title: this.data.shortcuts.label || __('Your Shortcuts'),
			container: this.page,
			type: "shortcut",
			columns: 3,
			options: {
				allow_sorting: this.allow_customization,
				allow_create: this.allow_customization,
				allow_delete: this.allow_customization,
				allow_hiding: false,
				allow_edit: true,
			},
			widgets: this.data.shortcuts.items
		});
	}

	make_cards() {
		let cards = new frappe.widget.WidgetGroup({
			title: this.data.cards.label || __(`Reports & Masters`),
			container: this.page,
			type: "links",
			columns: 3,
			options: {
				allow_sorting: this.allow_customization,
				allow_create: false,
				allow_delete: false,
				allow_hiding: this.allow_customization,
				allow_edit: false,
			},
			widgets: this.data.cards.items
		});

		this.sections["cards"] = cards;

		// const legend = [
		// 	{
		// 		color: "blue",
		// 		description: __("Important")
		// 	},
		// 	{
		// 		color: "yellow",
		// 		description: __("No Records Created")
		// 	}
		// ].map(item => {
		// 	return `<div class="legend-item text-muted justify-flex-start">
		// 		<span class="indicator-pill no-margin ${item.color}"></span>
		// 		<span class="link-content ellipsis" draggable="false">${item.description}</span>
		// 	</div>`;
		// });

		// $(`<div class="legend">
		// 	${legend.join("\n")}
		// </div>`).insertAfter(cards.body);
	}
}

