// specific_values = [
// 	{
// 		name: "Average",
// 		line_type: "dashed",	// "dashed" or "solid"
// 		value: 10
// 	},

// summary_values = [
// 	{
// 		name: "Total",
// 		color: 'blue',		// Indicator colors: 'grey', 'blue', 'red', 'green', 'orange',
// 					// 'purple', 'darkgrey', 'black', 'yellow', 'lightblue'
// 		value: 80
// 	}
// ]

frappe.ui.Graph = class Graph {
	constructor({
		parent = null,

		width = 0, height = 0,
		title = '', subtitle = '',

		y_values = [],
		x_points = [],

		specific_values = [],
		summary_values = [],

		color = '',
		mode = '',
	} = {}) {

		if(Object.getPrototypeOf(this) === frappe.ui.Graph.prototype) {
			if(mode === 'line-graph') {
				return new frappe.ui.LineGraph(arguments[0]);
			} else if(mode === 'bar-graph') {
				return new frappe.ui.BarGraph(arguments[0]);
			}
		}

		this.parent = parent;

		this.width = width;
		this.height = height;

		this.title = title;
		this.subtitle = subtitle;

		this.y_values = y_values;
		this.x_points = x_points;

		this.specific_values = specific_values;
		this.summary_values = summary_values;

		this.color = color;
		this.mode = mode;

		this.$graph = null;

		frappe.require("assets/frappe/js/lib/snap.svg-min.js", this.setup.bind(this));
	}

	setup() {
		this.setup_container();
		this.refresh();
	}

	refresh() {
		this.setup_values();
		this.setup_components();
		this.make_y_axis();
		this.make_x_axis();
		this.make_units();
		if(this.specific_values.length > 0) {
			this.show_specific_values();
		}
		this.setup_group();

		if(this.summary_values.length > 0) {
			this.show_summary();
		}
	}

	setup_container() {
		this.container = $('<div>')
			.addClass('graph-container')
			.append($(`<h6 class="title" style="margin-top: 15px;">${this.title}</h6>`))
			.append($(`<h6 class="sub-title uppercase">${this.subtitle}</h6>`))
			.append($(`<div class="graphics"></div>`))
			.append($(`<div class="stats-container"></div>`))
			.appendTo(this.parent);

		let $graphics = this.container.find('.graphics');
		this.$stats_container = this.container.find('.stats-container');

		this.$graph = $('<div>')
			.addClass(this.mode)
			.appendTo($graphics);

		this.$svg = $(`<svg class="svg" width="${this.width}" height="${this.height}"></svg>`);
		this.$graph.append(this.$svg);

		this.snap = new Snap(this.$svg[0]);
	}

	setup_values() {
		this.upper_graph_bound = this.get_upper_limit_and_parts(this.y_values)[0];
		this.y_axis = this.get_y_axis(this.y_values);
		this.avg_unit_width = (this.width-100)/(this.x_points.length - 1);
	}

	setup_components() {
		this.y_axis_group = this.snap.g().attr({
			class: "y axis"
		});

		this.x_axis_group = this.snap.g().attr({
			class: "x axis"
		});

		this.graph_list = this.snap.g().attr({
			class: "data-points",
		});

		this.specific_y_lines = this.snap.g().attr({
			class: "specific axis",
		});
	}

	setup_group() {
		this.snap.g(
			this.y_axis_group,
			this.x_axis_group,
			this.graph_list,
			this.specific_y_lines
		).attr({
			transform: "translate(60, 10)"  // default
		});
	}

	show_specific_values() {
		this.specific_values.map(d => {
			this.specific_y_lines.add(this.snap.g(
				this.snap.line(0, 0, this.width - 50, 0).attr({
					class: d.line_type === "dashed" ? "dashed": ""
				}),
				this.snap.text(this.width - 100, 0, d.name.toUpperCase()).attr({
					dy: ".32em",
					class: "specific-value",
				})
			).attr({
				class: "tick",
				transform: `translate(0, ${100 - 100/(this.upper_graph_bound/d.value) })`
			}));
		});
	}

	show_summary() {
		this.summary_values.map(d => {
			this.$stats_container.append($(`<div class="stats">
				<span class="indicator ${d.color}">${d.name}: ${d.value}</span>
			</div>`));
		});
	}

	// Helpers
	get_upper_limit_and_parts(array) {
		let specific_values = this.specific_values.map(d => d.value);
		let max_val = parseInt(Math.max(...array, ...specific_values));
		if((max_val+"").length <= 1) {
			return [10, 5];
		} else {
			let multiplier = Math.pow(10, ((max_val+"").length - 1));
			let significant = Math.ceil(max_val/multiplier);
			if(significant % 2 !== 0) significant++;
			let parts = (significant < 5) ? significant : significant/2;
			return [significant * multiplier, parts];
		}
	}

	get_y_axis(array) {
		let upper_limit, parts;
		[upper_limit, parts] = this.get_upper_limit_and_parts(array);
		let y_axis = [];
		for(var i = 0; i <= parts; i++){
			y_axis.push(upper_limit / parts * i);
		}
		return y_axis;
	}
};

frappe.ui.BarGraph = class BarGraph extends frappe.ui.Graph {
	constructor(args = {}) {
		super(args);
	}

	setup_values() {
		super.setup_values();
		this.avg_unit_width = (this.width-50)/(this.x_points.length + 2);
	}

	make_y_axis() {
		this.y_axis.map((point) => {
			this.y_axis_group.add(this.snap.g(
				this.snap.line(0, 0, this.width, 0),
				this.snap.text(-3, 0, point+"").attr({
					dy: ".32em",
					class: "y-value-text"
				})
			).attr({
				class: "tick",
				transform: `translate(0, ${100 - (100/(this.y_axis.length-1) * this.y_axis.indexOf(point)) })`
			}));
		});
	}

	make_x_axis() {
		this.x_axis_group.attr({
			transform: "translate(0,100)"
		});
		this.x_points.map((point, i) => {
			this.x_axis_group.add(this.snap.g(
				this.snap.line(0, 0, 0, 6),
				this.snap.text(0, 9, point).attr({
					dy: ".71em",
					class: "x-value-text"
				})
			).attr({
				class: "tick x-axis-label",
				transform: `translate(${ ((this.avg_unit_width - 5)*3/2) + i * (this.avg_unit_width + 5) }, 0)`
			}));
		});
	}

	make_units() {
		this.y_values.map((value, i) => {
			this.graph_list.add(this.snap.g(
				this.snap.rect(
					0,
					(100 - 100/(this.upper_graph_bound/value)),
					this.avg_unit_width - 5,
					100/(this.upper_graph_bound/value)
				)
			).attr({
				class: "bar mini",
				transform: `translate(${ (this.avg_unit_width - 5) + i * (this.avg_unit_width + 5) }, 0)`,
			}));
		});
	}
};

frappe.ui.LineGraph = class LineGraph extends frappe.ui.Graph {
	constructor(args = {}) {
		super(args);
	}

	make_y_axis() {
		this.y_axis.map((point) => {
			this.y_axis_group.add(this.snap.g(
				this.snap.line(0, 0, -6, 0),
				this.snap.text(-9, 0, point+"").attr({
					dy: ".32em",
					class: "y-value-text"
				})
			).attr({
				class: "tick",
				transform: `translate(0, ${100 - (100/(this.y_axis.length-1)
					* this.y_axis.indexOf(point)) })`
			}));
		});
	}

	make_x_axis() {
		this.x_axis_group.attr({
			transform: "translate(0,-7)"
		});
		this.x_points.map((point, i) => {
			this.x_axis_group.add(this.snap.g(
				this.snap.line(0, 0, 0, this.height - 25),
				this.snap.text(0, this.height - 15, point).attr({
					dy: ".71em",
					class: "x-value-text"
				})
			).attr({
				class: "tick",
				transform: `translate(${ i * this.avg_unit_width }, 0)`
			}));
		});
	}

	make_units() {
		let points_list = [];
		this.y_values.map((value, i) => {
			let x = i * this.avg_unit_width;
			let y = (100 - 100/(this.upper_graph_bound/value));
			this.graph_list.add(this.snap.circle( x, y, 4));
			points_list.push(x+","+y);
		});

		this.make_path("M"+points_list.join("L"));
	}

	make_path(path_str) {
		this.graph_list.prepend(this.snap.path(path_str));
	}

};
