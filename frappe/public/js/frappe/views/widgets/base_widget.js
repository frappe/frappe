export default class Widget {
	constructor(opts) {
		Object.assign(this, opts);
		this.make();
	}

	refresh() {
		//
	}

	customize() {

	}

	make() {
		this.make_widget();
		this.widget.appendTo(this.container);
		this.setup_events();
	}

	// get_grid() {
	// 	const width_map = {
	// 		'One Third': 'col-sm-4',
	// 		'Two Third': 'col-sm-8 ',
	// 		'Half': 'col-sm-6',
	// 		'Full': 'col-sm-12',
	// 		'auto': 'col-sm-4'
	// 	}

	// 	return width_map[this.width] || 'col-sm-12'
	// }

	make_widget() {
		this.widget = $(`<div class="widget">
			<div class="widget-head">
				<div class="widget-title"></div>
				<div class="widget-control"></div>
			</div>
		    <div class="widget-body">
		    </div>
		</div>`);

		this.title_field = this.widget.find(".widget-title");
		this.body = this.widget.find(".widget-body");
		this.action_area = this.widget.find(".widget-control");
		this.head = this.widget.find(".widget-head");
		this.set_title();
		this.set_actions();
		this.set_body();
	}

	set_title() {
		this.title_field[0].innerHTML = this.label || this.name;
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