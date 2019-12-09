import { get_widget_class } from './widget'

class DeskSection {
	constructor(opts) {
		Object.assign(this, opts);
		this.widgets = {};
		this.make();
	}

	make() {
		this.make_container();
		this.make_module_widget();
		this.setup_sortable();
	}

	make_container() {
		this.section_container = $(`<div class="modules-section">
			<div class="section-header level text-muted">
				<div class="module-category h6 uppercase">${ __(this.category) } (BETA)</div>
			</div>
			<div class="modules-container"></div>
		</div>`);

		this.modules_container = this.section_container.find('.modules-container')

		this.section_container.appendTo(this.container);
	}

	make_module_widget() {
		this.modules.forEach(mod => {
			let widget_class = get_widget_class(mod.type)
			this.widgets[mod.module_name] = new widget_class({
				container: this.modules_container,
				module_data: mod
			});
		});
	}

	setup_sortable() {
		const container = this.modules_container[0]
		this.sortable = new Sortable(container, {
			animation: 150,
			onEnd: () => {
				let modules = Array.from(container.querySelectorAll('.module-box'))
					.map(node => node.dataset.moduleName);

				frappe.call('frappe.desk.moduleview.update_modules_order', {
					module_category: this.category,
					modules: modules
				});
			}
		})
	}
}

export default class Desk {
	constructor({ container }) {
		this.container = $(container);
		this.module_categories = ['Modules', 'Domains', 'Places', 'Administration'];
		this.sections = {}
		this.make();
	}

	make() {
		this.fetch_desktop_settings().then(() => {
			this.make_container();
			this.make_sections();
			this.setup_events();
		});
	}

	fetch_desktop_settings() {
		return frappe.call('frappe.desk.moduleview.get_desktop_settings')
			.then(response => {
				if (response.message) {
					this.categories = response.message
				}
			});
	}

	make_container() {
		this.modules_section_container = $(`<div class="modules-page-container">
			<a class="btn-show-hide text-muted text-medium show-or-hide-cards">
				${__('Show / Hide Cards')}
			</a></div>`);

		this.modules_section_container.appendTo(this.container);
	}

	make_sections() {
		this.module_categories.forEach(category => {
			if (this.categories.hasOwnProperty(category) && this.categories[category].length) {
				this.sections[category] = new DeskSection({
					category: category,
					modules: this.categories[category],
					container: this.modules_section_container
				});
			}
		});
	}

	setup_events() {
		this.setup_show_hide_cards();
	}

	setup_show_hide_cards() {
		return
	}
}