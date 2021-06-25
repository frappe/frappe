frappe.standard_pages['Workspaces'] = function() {
	var wrapper = frappe.container.add_page('Workspaces');

	frappe.ui.make_app_page({
		parent: wrapper,
		name: 'Workspaces',
		title: __("Workspace"),
	});

	frappe.workspace = new frappe.views.Workspace(wrapper);
	$(wrapper).bind('show', function () {
		frappe.workspace.show();
	});
};

frappe.views.Workspace = class Workspace {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = wrapper.page;
		this.prepare_container();
		this.show_or_hide_sidebar();
		this.setup_dropdown();
		this.pages = {};
		this.sidebar_items = {};
		this.sidebar_categories = [
			"Modules",
			"Domains",
			"Places",
			"Administration"
		];

		this.setup_workspaces();
		this.make_sidebar();
	}

	setup_workspaces() {
		// workspaces grouped by categories
		this.workspaces = {};
		for (let page of frappe.boot.allowed_workspaces) {
			if (!this.workspaces[page.category]) {
				this.workspaces[page.category] = [];
			}
			this.workspaces[page.category].push(page);
		}
	}

	show() {
		let page = this.get_page_to_show();
		this.page.set_title(`${__(page)}`);
		this.show_page(page);
	}

	prepare_container() {
		let list_sidebar = $(`
			<div class="list-sidebar overlay-sidebar hidden-xs hidden-sm">
				<div class="desk-sidebar list-unstyled sidebar-menu"></div>
			</div>
		`).appendTo(this.wrapper.find(".layout-side-section"));
		this.sidebar = list_sidebar.find(".desk-sidebar");

		this.body = this.wrapper.find(".layout-main-section");
	}

	get_page_to_show() {
		let default_page;

		if (localStorage.current_workspace) {
			default_page = localStorage.current_workspace;
		} else if (this.workspaces) {
			default_page = this.workspaces["Modules"][0].name;
		} else if (frappe.boot.allowed_workspaces) {
			default_page = frappe.boot.allowed_workspaces[0].name;
		} else {
			default_page = "Build";
		}

		let page = frappe.get_route()[1] || default_page;
		return page;
	}

	make_sidebar() {
		this.sidebar_categories.forEach(category => {
			if (this.workspaces[category]) {
				this.build_sidebar_section(category, this.workspaces[category]);
			}
		});
	}

	build_sidebar_section(title, items) {
		let sidebar_section = $(`<div class="standard-sidebar-section"></div>`);

		// DO NOT REMOVE: Comment to load translation
		// __("Modules") __("Domains") __("Places") __("Administration")
		$(`<div class="standard-sidebar-label">${__(title)}</div>`)
			.appendTo(sidebar_section);

		const get_sidebar_item = function (item) {
			return $(`
				<a
					href="/app/${frappe.router.slug(item.name)}"
					class="desk-sidebar-item standard-sidebar-item ${item.selected ? "selected" : ""}"
				>
					<span>${frappe.utils.icon(item.icon || "folder-normal", "md")}</span>
					<span class="sidebar-item-label">${item.label || item.name}<span>
				</a>
			`);
		};

		const make_sidebar_category_item = item => {
			if (item.name == this.get_page_to_show()) {
				item.selected = true;
				this.current_page_name = item.name;
			}

			let $item = get_sidebar_item(item);

			$item.appendTo(sidebar_section);
			this.sidebar_items[item.name] = $item;
		};

		items.forEach(item => make_sidebar_category_item(item));

		sidebar_section.appendTo(this.sidebar);
	}

	show_page(page) {
		if (this.current_page_name && this.pages[this.current_page_name]) {
			this.pages[this.current_page_name].hide();
		}

		if (this.sidebar_items && this.sidebar_items[this.current_page_name]) {
			this.sidebar_items[this.current_page_name].removeClass("selected");
			this.sidebar_items[page].addClass("selected");
		}
		this.current_page_name = page;
		localStorage.current_workspace = page;

		this.pages[page] ? this.pages[page].show() : this.make_page(page);
		this.current_page = this.pages[page];
		this.setup_dropdown();
	}

	make_page(page) {
		const $page = new DesktopPage({
			container: this.body,
			page_name: page
		});

		this.pages[page] = $page;
		return $page;
	}

	customize() {
		if (this.current_page && this.current_page.allow_customization) {
			this.page.clear_menu();
			this.current_page.customize();

			this.page.set_primary_action(
				__("Save Customizations"),
				() => {
					this.current_page.save_customization();
					this.page.clear_primary_action();
					this.page.clear_secondary_action();
					this.setup_dropdown();
				},
				null,
				__("Saving")
			);

			this.page.set_secondary_action(
				__("Discard"),
				() => {
					this.current_page.reload();
					frappe.show_alert({ message: __("Customizations Discarded"), indicator: "info" });
					this.page.clear_primary_action();
					this.page.clear_secondary_action();
					this.setup_dropdown();
				}
			);
		}
	}

	setup_dropdown() {
		this.page.clear_menu();

		this.page.set_secondary_action(__('Customize'), () => {
			this.customize();
		});

		this.page.add_menu_item(__('Reset Customizations'), () => {
			this.current_page.reset_customization();
		}, 1);

		this.page.add_menu_item(__('Toggle Sidebar'), () => {
			this.toggle_side_bar();
		}, 1);
	}

	toggle_side_bar() {
		let show_workspace_sidebar = JSON.parse(localStorage.show_workspace_sidebar || "true");
		show_workspace_sidebar = !show_workspace_sidebar;
		localStorage.show_workspace_sidebar = show_workspace_sidebar;
		this.show_or_hide_sidebar();
		$(document.body).trigger("toggleDeskSidebar");
	}

	show_or_hide_sidebar() {
		let show_workspace_sidebar = JSON.parse(localStorage.show_workspace_sidebar || "true");
		$('#page-workspace .layout-side-section').toggleClass('hidden', !show_workspace_sidebar);
	}
};

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
	}

	make() {
		this.page = $(`<div class="desk-page" data-page-name=${this.page_name}></div>`);
		this.page.append(frappe.render_template('workspace_loading_skeleton'));
		this.page.appendTo(this.container);

		this.get_data().then(() => {
			if (Object.keys(this.data).length == 0) {
				delete localStorage.current_workspace;
				frappe.set_route("workspace");
				return;
			}
			this.refresh();
		}).finally(this.page.find('.workspace_loading_skeleton').remove);
	}

	refresh() {
		this.page.empty();
		this.allow_customization = this.data.allow_customization || false;

		if (frappe.is_mobile()) {
			this.allow_customization = false;
		}

		this.data.onboarding && this.data.onboarding.items.length && this.make_onboarding();
		this.make_charts();
		this.make_shortcuts();
		this.make_cards();
	}

	get_data() {
		return frappe.xcall("frappe.desk.desktop.get_desktop_page", {
			page: this.page_name
		}).then(data => {
			this.data = data;
			if (Object.keys(this.data).length == 0) return;

			return frappe.dashboard_utils.get_dashboard_settings().then(settings => {
				let chart_config = settings.chart_config ? JSON.parse(settings.chart_config) : {};
				if (this.data.charts.items) {
					this.data.charts.items.map(chart => {
						chart.chart_settings = chart_config[chart.chart_name] || {};
					});
				}
			});
		});
	}

	customize() {
		if (this.in_customize_mode) {
			return;
		}

		// We need to remove this as the  chart group will be visible during customization
		$('.widget.onboarding-widget-box').hide();

		Object.keys(this.sections).forEach(section => {
			this.sections[section].customize();
		});
		this.in_customize_mode = true;

	}

	save_customization() {
		frappe.dom.freeze();
		const config = {};

		if (this.sections.charts) config.charts = this.sections.charts.get_widget_config();
		if (this.sections.shortcuts) config.shortcuts = this.sections.shortcuts.get_widget_config();
		if (this.sections.cards) config.cards = this.sections.cards.get_widget_config();

		frappe.call('frappe.desk.desktop.save_customization', {
			page: this.page_name,
			config: config
		}).then(res => {
			frappe.dom.unfreeze();
			if (res.message) {
				frappe.show_alert({ message: __("Customizations Saved Successfully"), indicator: "green" });
				this.reload();
			} else {
				frappe.throw({ message: __("Something went wrong while saving customizations"), indicator: "red" });
				this.reload();
			}
		});
	}

	reset_customization() {
		frappe.call('frappe.desk.desktop.reset_customization', {
			page: this.page_name
		}).then(() => {
			frappe.show_alert({ message: __("Removed page customizations"), indicator: "green" });
			this.reload();
		});
	}

	make_onboarding() {
		this.onboarding_widget = frappe.widget.make_widget({
			label: this.data.onboarding.label || __("Let's Get Started"),
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
		this.sections["charts"] = new frappe.widget.WidgetGroup({
			container: this.page,
			type: "chart",
			columns: 1,
			class_name: "widget-charts",
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
			title: this.data.cards.label || __("Reports & Masters"),
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
	}
}


