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
		//
	}

	setup_events() {
		//
	}
}