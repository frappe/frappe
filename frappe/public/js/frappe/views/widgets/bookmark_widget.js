import Widget from "./base_widget.js";

String.prototype.format = function () {
  var i = 0, args = arguments;
  return this.replace(/{}/g, function () {
    return typeof args[i] != 'undefined' ? args[i++] : '';
  });
};

export default class BookmarkWidget extends Widget {
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
		this.widget.addClass('shortcut-widget-box')

		const options = this.options;

		const get_label = () => {
			if (options.format_string) {
				return options.format_string.format(options.count);
			}
			return this.count
		}

		if (!options || !options.count) return

		this.action_area.empty();
		const label = get_label();
		const buttons = $(`<div class="small pill pill-${options.color}">${label}</div>`);
		buttons.appendTo(this.action_area);
	}
}