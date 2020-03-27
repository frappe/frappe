import ChartWidget from "../widgets/chart_widget";
import BaseWidget from "../widgets/base_widget";
import ShortcutWidget from "../widgets/shortcut_widget";
import LinksWidget from "../widgets/links_widget";
import OnboardingWidget from "../widgets/onboarding_widget";

frappe.provide('frappe.widget')

const widget_factory = {
	chart: ChartWidget,
	base: BaseWidget,
	bookmark: ShortcutWidget,
	links: LinksWidget,
	onboarding: OnboardingWidget
};

export default class WidgetGroup {
	constructor(opts) {
		Object.assign(this, opts);
		// opts = {
		// 	title: "CRM Dashboard",
		//  container: $(''),
		// 	widgets: [
		// 		{type: "dashboard", width: "Full", options: {}}.
		// 		{type: "dashboard", width: "Full", options: {}}
		// 	],
		// 	allow_delete: true,
		// 	allow_create: true,
		// 	allow_rearrange: true,
		// 	hide_edit_option: false,
		// 	collapsible: false
		// }
		window.wid_area = this;
		this.make();
	}

	make() {
		this.make_container();
		this.refresh();
	}

	refresh() {
		this.title && this.set_title(this.title);
		this.widgets && this.make_widgets();
		this.allow_sorting && this.setup_sortable();
	}

	make_container() {
		const widget_area = $(`<div class="widget-group">
				<div class="widget-group-head">
					<div class="widget-group-title h6 uppercase"></div>
					<div class="widget-group-control h6 text-muted"></div>
				</div>
				<div class="widget-group-body grid-col-${this.columns}">
				</div>
			</div>`);
		this.widget_area = widget_area;
		this.title_area = widget_area.find(".widget-group-title");
		this.control_area = widget_area.find(".widget-group-control");
		this.body = widget_area.find(".widget-group-body");
		widget_area.appendTo(this.container);
	}

	set_title(title) {
		this.title_area[0].innerText = this.title;
	}

	make_widgets() {
		this.body.empty()
		const widget_class = widget_factory[this.type];

		this.widgets.forEach(widget => {
			new widget_class({
				...widget,
				container: this.body
			})
		});
	}

	setup_sortable() {
		const container = this.body[0];
		this.sortable = new Sortable(container, {
			animation: 150,
			onEnd: () => {
				console.log("Sorting")
			},
			// onChoose: (evt) => this.sortable_config.on_choose(evt, container),
			// onStart: (evt) => this.sortable_config.on_start(evt, container)
		});
	}
}

frappe.widget.WidgetGroup = WidgetGroup;