export default class Widget {
	constructor(opts) {
		Object.assign(this, opts);
		this.make();
	}

	refresh() {
		this.set_title();
		this.set_actions();
		this.set_body();
	}

	get_config() {
		return {
			name: this.name,
			docname: this.docname,
			label: this.label,
		}
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
		options.allow_hiding &&
			this.add_custom_button(
				'<i class="fa fa-eye-slash" aria-hidden="true"></i>',
				() => this.hide()
			);
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
		this.widget = $(`<div class="widget" data-widget-name=${
			this.docname ? this.docname : this.name
		}>
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
		this.set_title();
		this.set_actions();
		this.set_body();
	}

	set_title() {
		this.title_field[0].innerHTML = this.label || this.name;
	}

	add_custom_button(html, action, class_name = "") {
		let button = $(
			`<button class="btn btn-default btn-xs ${class_name}">${html}</button>`
		);
		action && button.on("click", () => action());
		button.appendTo(this.action_area);
	}

	delete() {
		this.widget.addClass("zoomOutDelete");
		// wait for animation
		setTimeout(() => {
			this.widget.remove();
			this.on_delete && this.on_delete(this.name);
		}, 300);
	}

	edit() {
		this.on_edit && this.on_edit(this.name);
	}

	hide() {
		this.body.css("opacity", 0.5);
		this.title_field.css("opacity", 0.5);
		this.footer.css("opacity", 0.5);
	}

	set_actions() {
		//
	}

	set_body() {
		//
	}
}
