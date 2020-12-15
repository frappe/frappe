import Widget from "./base_widget.js";

frappe.provide("frappe.utils");

export default class ShortcutWidget extends Widget {
	constructor(opts) {
		super(opts);
	}

	get_config() {
		return {
			name: this.name,
			icon: this.icon,
			label: this.label,
			format: this.format,
			link_to: this.link_to,
			doc_view: this.doc_view,
			color: this.color,
			restrict_to_domain: this.restrict_to_domain,
			stats_filter: this.stats_filter,
			type: this.type,
		};
	}

	setup_events() {
		this.widget.click(() => {
			if (this.in_customize_mode) return;

			let route = frappe.utils.generate_route({
				route: this.route,
				name: this.link_to,
				type: this.type,
				is_query_report: this.is_query_report,
				doctype: this.ref_doctype,
				doc_view: this.doc_view
			});

			let filters = this.get_doctype_filter();
			if (this.type == "DocType" && filters) {
				frappe.route_options = filters;
			}
			frappe.set_route(route);
		});
	}

	set_actions() {
		if (this.in_customize_mode) return;

		this.widget.addClass("shortcut-widget-box");

		let filters = this.get_doctype_filter();
		if (this.type == "DocType" && filters) {
			frappe.db
				.count(this.link_to, {
					filters: filters,
				})
				.then((count) => this.set_count(count));
		}
	}

	get_doctype_filter() {
		let count_filter = new Function(`return ${this.stats_filter}`)();
		if (count_filter) {
			return count_filter;
		}

		return null;
	}

	set_title() {
		if (this.icon) {
			this.title_field[0].innerHTML = `<div>
				<i class="${this.icon}" style=""></i>
				${this.label || this.name}
				</div>`;
		} else {
			super.set_title();
		}
	}

	set_count(count) {
		const get_label = () => {
			if (this.format) {
				return this.format.replace(/{}/g, count);
			}
			return count;
		};

		this.action_area.empty();
		const label = get_label();
		const buttons = $(`<div class="small pill">${label}</div>`);
		if (this.color) {
			let bg_color = count ? this.color: '#EEEEEE';
			let text_color = count ? frappe.ui.color.get_contrast_color(bg_color): '#8D99A6';
			buttons.css("background-color", bg_color);
			buttons.css("color", text_color);
		}

		buttons.appendTo(this.action_area);
	}
}
