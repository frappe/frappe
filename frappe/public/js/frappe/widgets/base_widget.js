import get_dialog_constructor from './widget_dialog.js';

export default class Widget {
	constructor(opts) {
		Object.assign(this, opts);
		this.make();
	}

	refresh() {
		this.set_title();
		this.set_actions();
		this.set_body();
		this.setup_events();
	}

	get_config() {
		return {
			name: this.name,
			label: this.label
		};
	}

	customize(options) {
		this.in_customize_mode = true;
		this.action_area.empty();

		options.allow_sorting &&
			this.add_custom_button(
				frappe.utils.icon('drag', 'xs'),
				null,
				"drag-handle",
			);

		options.allow_delete &&
			this.add_custom_button(
				frappe.utils.icon('delete', 'xs'),
				() => this.delete(),
				"",
				`${__('Delete')}`
			);

		if (options.allow_hiding) {
			if (this.hidden) {
				this.widget.removeClass("hidden");
				this.body.css("opacity", 0.5);
				this.title_field.css("opacity", 0.5);
				this.footer.css("opacity", 0.5);
			}
			const classname = this.hidden ? 'fa fa-eye' : 'fa fa-eye-slash';
			const title = this.hidden ? `${__('Show')}` : `${__('Hide')}`;
			this.add_custom_button(
				`<i class="${classname}" aria-hidden="true"></i>`,
				() => this.hide_or_show(),
				"show-or-hide-button",
				title
			);

			this.show_or_hide_button = this.action_area.find(
				".show-or-hide-button"
			);
		}

		options.allow_edit &&
			this.add_custom_button(
				frappe.utils.icon("edit", "xs"),
				() => this.edit()
			);

		if (options.allow_resize) {
			const title = this.width == 'Full'? `${__('Collapse')}` : `${__('Expand')}`;
			this.add_custom_button(
				'<i class="fa fa-expand" aria-hidden="true"></i>',
				() => this.toggle_width(),
				"resize-button",
				title
			);

			this.resize_button = this.action_area.find(
				".resize-button"
			);
		}
	}

	make() {
		this.make_widget();
		this.widget.appendTo(this.container);
	}

	make_widget() {
		this.widget = $(`<div class="widget
			${ this.hidden ? "hidden" : " " }
			${ this.shadow ? "widget-shadow" : " " }
		" data-widget-name="${this.name ? this.name : ''}">
			<div class="widget-head">
				<div>
					<div class="widget-title ellipsis"></div>
					<div class="widget-subtitle"></div>
				</div>
				<div class="widget-control"></div>
			</div>
			<div class="widget-body">
		    </div>
		    <div class="widget-footer">
		    </div>
		</div>`);

		this.title_field = this.widget.find(".widget-title");
		this.subtitle_field = this.widget.find(".widget-subtitle");
		this.body = this.widget.find(".widget-body");
		this.action_area = this.widget.find(".widget-control");
		this.head = this.widget.find(".widget-head");
		this.footer = this.widget.find(".widget-footer");
		this.refresh();
	}

	set_title(max_chars) {
		let base = this.label || this.name;
		let title = max_chars ? frappe.ellipsis(base, max_chars) : base;

		if (this.icon) {
			let icon = frappe.utils.icon(this.icon);
			this.title_field[0].innerHTML = `${icon} <span>${title}</span>`;
		} else {
			this.title_field[0].innerHTML = title;
			if (max_chars) {
				this.title_field[0].setAttribute('title', this.label);
			}
		}
		this.subtitle && this.subtitle_field.html(this.subtitle);
	}

	add_custom_button(html, action, class_name = "", title="", btn_type) {
		if (!btn_type) btn_type = 'btn-secondary';
		let button = $(
			`<button class="btn ${btn_type} btn-xs ${class_name}" title="${title}">${html}</button>`
		);
		button.click(event => {
			event.stopPropagation();
			action && action();
		});
		button.appendTo(this.action_area);
	}

	delete(animate=true) {
		let remove_widget = (setup_new) => {
			this.widget.remove();
			this.options.on_delete && this.options.on_delete(this.name, setup_new);
		};

		if (animate) {
			this.widget.addClass("zoom-out");
			// wait for animation
			setTimeout(() => {
				remove_widget(true);
			}, 300);
		} else {
			remove_widget(false);
		}
	}

	edit() {
		const dialog_class = get_dialog_constructor(this.widget_type);

		this.edit_dialog = new dialog_class({
			label: this.label,
			type: this.widget_type,
			values: this.get_config(),
			primary_action: (data) => {
				Object.assign(this, data);
				data.name = this.name;

				this.refresh();
			},
			primary_action_label: __("Save")
		});

		this.edit_dialog.make();
	}

	toggle_width() {
		if (this.width == 'Full') {
			this.widget.removeClass("full-width");
			this.width = null;
			this.refresh();
		} else {
			this.widget.addClass("full-width");
			this.width = 'Full';
			this.refresh();
		}

		const title = this.width == 'Full' ? `${__('Collapse')}` : `${__('Expand')}`;
		this.resize_button.attr('title', title);
	}

	hide_or_show() {
		if (!this.hidden) {
			this.body.css("opacity", 0.5);
			this.title_field.css("opacity", 0.5);
			this.footer.css("opacity", 0.5);
			this.hidden = true;
		} else {
			this.body.css("opacity", 1);
			this.title_field.css("opacity", 1);
			this.footer.css("opacity", 1);
			this.hidden = false;
		}
		this.show_or_hide_button.empty();

		const classname = this.hidden ? 'fa fa-eye' : 'fa fa-eye-slash';
		const title = this.hidden ? `${__('Show')}` : `${__('Hide')}`;

		$(`<i class="${classname}" aria-hidden="true" title="${title}"></i>`).appendTo(
			this.show_or_hide_button
		);
	}

	setup_events() {
		//
	}

	set_actions() {
		//
	}

	set_body() {
		//
	}
}
