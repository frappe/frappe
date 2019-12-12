import { get_widget_class } from "./widgets";

export default class DeskSection {
	constructor(opts) {
		Object.assign(this, opts);
		this.widgets = {};
		this.make();
	}

	make() {
		this.make_container();
		this.make_module_widget();
		this.sortable_config.enable && this.setup_sortable();
	}

	make_container() {
		const get_title = () => {
			return `<div class="section-header level text-muted">
				<div class="module-category h6 uppercase">${__(this.title)}</div>
			</div>`;
		};

		this.section_container = $(`<div class="modules-section">
			${this.hide_title ? "" : get_title()}
			<div class="modules-container"></div>
		</div>`);

		this.modules_container = this.section_container.find(
			".modules-container"
		);

		this.section_container.appendTo(this.container);
	}

	make_module_widget() {
		this.widget_config.forEach(mod => {
			let widget_class = get_widget_class(mod.type);
			this.widgets[mod.module_name] = new widget_class({
				container: this.modules_container,
				data: mod
			});
		});
	}

	setup_sortable() {
		const container = this.modules_container[0];
		this.sortable = new Sortable(container, {
			animation: 150,
			onEnd: () => {
				this.sortable_config.after_sort(container, this.options);
			}
		});
	}
}
