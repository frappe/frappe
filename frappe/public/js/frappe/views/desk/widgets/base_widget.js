export default class Widget {
	constructor(opts) {
		Object.assign(this, opts);
		this.make();
	}

	refresh() {
		//
	}

	make() {
		this.make_widget();
		this.widget.appendTo(this.container);
		this.setup_events();
	}

	make_widget() {
		this.widget = $(`<div class="border section-box">
		    <h4 class="h4 widget-title"></h4>
		    <div class="widget-body">
		    </div
		</div>`);

		this.title_field = this.widget.find('.widget-title');
		this.body = this.widget.find('.widget-body');
		this.set_title();
		this.set_body();
	}

	set_title() {
		this.title_field[0].innerHTML = this.data.label || this.data.name;
	}

	set_body() {

	}

	setup_events() {
		//
	}
}