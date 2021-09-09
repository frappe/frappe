import Widget from "./base_widget.js";

frappe.provide("frappe.utils");

export default class ShortcutWidget extends Widget {
	constructor(opts) {
		opts.shadow = true;
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
			bg_color: this.bg_color,
			icon_size: this.icon_size,
			icon_color: this.icon_color
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

		console.log(this);

		// this.widget[0].parentElement.parentElement.parentElement.style.flex = '0 0 50%';

		// console.log(this.widget[0].parentElement.parentElement.parentElement);

		if (this.bg_color) {
			this.widget.css('background', this.bg_color);
			this.head[0].style.justifyContent = 'center';
			this.title_field[0].style.flexDirection = 'column';
			this.title_field[0].style.fontSize = 'var(--text-base)';
			console.log(this);
		}

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

	set_count(count) {
		const get_label = () => {
			if (this.format) {
				return __(this.format).replace(/{}/g, count);
			}
			return count;
		};

		this.action_area.empty();
		const label = get_label();
		let color = this.color && count ? this.color.toLowerCase() : 'gray';
		$(`<div class="indicator-pill ellipsis ${color}">${label}</div>`).appendTo(this.action_area);
	}
}
