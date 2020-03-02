import Widget from "./base_widget.js";
import { generate_route } from "./utils";
// import { get_luminosity, shadeColor } from "./utils";

String.prototype.format = function () {
  var i = 0, args = arguments;
  return this.replace(/{}/g, function () {
    return typeof args[i] != 'undefined' ? args[i++] : '';
  });
};

export default class ShortcutWidget extends Widget {
	constructor(opts) {
		super(opts);
	}

	refresh() {
		//
	}

	setup_events() {
		this.widget.click(() => {
			let route = generate_route(this)
  			frappe.set_route(route)
		})
	}

	set_actions() {
		this.widget.addClass('shortcut-widget-box');
		const get_filter = new Function(`return ${this.stats_filter}`)
		if (this.type == "DocType" && this.stats_filter) {
			frappe.db.count(this.link_to, {
				filters: get_filter()
			}).then(count => this.set_count(count))
		}
	}

	set_title() {
		if (this.icon) {
			this.title_field[0].innerHTML = `<div>
				<i class="${this.icon}" style="color: rgb(141, 153, 166); font-size: 18px; margin-right: 6px;"></i>
				${this.label || this.name}
				</div>`
		}
		else {
			super.set_title();
		}
	}

	set_count(count) {
		const get_label = () => {
			if (this.format) {
				return this.format.format(count);
			}
			return count
		}

		this.action_area.empty();
		const label = get_label();
		const buttons = $(`<div class="small pill">${label}</div>`);
		if(this.color) {
			buttons.css('background-color', this.color);
			buttons.css('color', frappe.ui.color.get_contrast_color(this.color))
		}

		buttons.appendTo(this.action_area);
	}
}