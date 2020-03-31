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
			docname: this.docname,
			label: this.label
		};
	}

	customize(options) {
		this.action_area.empty();

		options.allow_delete &&
			this.add_custom_button(
				'<i class="fa fa-trash" aria-hidden="true"></i>',
				() => this.delete()
			);

		options.allow_sorting &&
			this.add_custom_button(
				'<i class="fa fa-arrows" aria-hidden="true"></i>',
				null,
				"drag-handle"
			);

		if (options.allow_hiding) {
			if (this.hidden) {
				this.widget.removeClass("hidden");
				this.body.css("opacity", 0.5);
				this.title_field.css("opacity", 0.5);
				this.footer.css("opacity", 0.5);
			}
			const classname = this.hidden ? 'fa fa-eye' : 'fa fa-eye-slash';
			this.add_custom_button(
				`<i class="${classname}" aria-hidden="true"></i>`,
				() => this.hide_or_show(),
				"show-or-hide-button"
			);

			this.show_or_hide_button = this.action_area.find(
				".show-or-hide-button"
			);
		}

		options.allow_edit &&
			this.add_custom_button(
				'<i class="fa fa-pencil" aria-hidden="true"></i>',
				() => this.edit()
			);
	}

	make() {
		this.make_widget();
		this.widget.appendTo(this.container);
	}

	make_widget() {
		this.widget = $(`<div class="widget ${
			this.hidden ? "hidden" : ""
		}" data-widget-name=${this.docname ? this.docname : this.name}>
			<div class="widget-head">
				<div class="widget-title"></div>
				<div class="widget-control"></div>
			</div>
		    <div class="widget-body">
		    </div>
		    <div class="widget-footer">
		    </div>
		</div>`);

		this.title_field = this.widget.find(".widget-title");
		this.body = this.widget.find(".widget-body");
		this.action_area = this.widget.find(".widget-control");
		this.head = this.widget.find(".widget-head");
		this.footer = this.widget.find(".widget-footer");
		this.refresh();
	}

	set_title() {
		this.title_field[0].innerHTML = this.label || this.name;
	}

	add_custom_button(html, action, class_name = "") {
		let button = $(
			`<button class="btn btn-default btn-xs ${class_name}">${html}</button>`
		);
		button.click(event => {
			event.stopPropagation();
			action && action();
		});
		button.appendTo(this.action_area);
	}

	delete() {
		this.widget.addClass("zoomOutDelete");
		// wait for animation
		setTimeout(() => {
			this.widget.remove();
			this.options.on_delete && this.options.on_delete(this.name);
		}, 300);
	}

	edit() {
		frappe.model.with_doctype(this.doctype, () => {
			let new_dialog = new frappe.ui.Dialog({
				title: __("Edit"),
				fields: frappe.get_meta(this.doctype).fields,
				primary_action: (data) => {
					if (this.doctype == 'Desk Chart' && !data.label) {
						data.label = data.chart_name;
					}

					if (this.doctype == 'Desk Shortcut') {
						data.label = data.link_to;
					}

					new_dialog.hide();
					console.log("DATA", data)
					Object.assign(this, data);
					this.set_title();
					this.set_actions();
					this.set_body();
					this.setup_events();
				},
				primary_action_label: __("Save"),
			});

			new_dialog.show();
			new_dialog.set_values(this.get_config());
		});
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
		$(`<i class="${classname}" aria-hidden="true"></i>`).appendTo(
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
