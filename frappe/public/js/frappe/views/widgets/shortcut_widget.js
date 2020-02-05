import Widget from "./base_widget.js";
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
		//
	}

	set_actions() {
		this.widget.addClass('shortcut-widget-box');
		const get_filter = new Function(`return ${this.stats_filter}`)
		console.log(get_filter())
		if (this.type == "DocType" && this.stats_filter) {
			frappe.db.count(this.link_to, {
				filters: get_filter()
			}).then(count => this.set_count(count))
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