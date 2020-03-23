export default class NewWidget {
	constructor(opts) {
		Object.assign(this, opts);
		this.make();
		window.wid = this;
	}

	refresh() {
		//
	}

	customize() {
		return
	}

	make() {
		this.make_widget();
		this.widget.appendTo(this.container);
		this.setup_events();
	}

	make_widget() {
		this.widget = $(`<div class="widget new-widget">
				+ New
			</div>`);
		this.body = this.widget
		this.set_body();
	}

	delete() {
		this.widget.remove();
	}

	set_actions() {
		//
	}

	set_body() {
		//
	}

	setup_events() {
		//
	}
}