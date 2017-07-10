// specific_values = [
// 	{
// 		name: "Average",
// 		line_type: "dashed",
// 		value: 10
// 	},
// 	{
// 		name: "Goal",
// 		line_type: "solid",
// 		value: 120
// 	}
// ]

// summary_values = [
// 	{
// 		name: "Total",
// 		color: 1,
// 		value: 80
// 	},
// 	{
// 		name: "Goal",
// 		color: 0,
// 		value: 120
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
			.append($(`<h5 class="title">${this.title}</h5>`))
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
			transform: "translate(40, 10)"  // default
		});
	}

	show_summary() {
		this.summary_values.map(d => {
			this.$stats_container.append($(`<div class="stats ${d.name.toLowerCase() + '-stats '}
			${d.color?' graph-data':''}">
				<span class="stats-title">${d.name}</span>
				<span class="stats-value">${d.value}</span>
			</div>`));
		});
	}

	get_upper_limit_and_parts(array) {
		let specific_values = this.specific_values.map(d => d.value);
		let max_val = Math.max(...array, ...specific_values);
		if((max_val+"").length <= 1) {
			return 10;
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
				transform: `translate(${ 27 + i * 20 }, 0)`
			}));
		});
	}

	make_units() {
		this.y_values.map((value, i) => {
			this.graph_list.add(this.snap.g(
				this.snap.rect(
					0,
					(100 - 100/(this.upper_graph_bound/value)),
					18,
					100/(this.upper_graph_bound/value)
				)
			).attr({
				class: "bar mini",
				transform: `translate(${ 18 + i * 20 }, 0)`,
			}));
		});
	}

	show_specific_values() {
		this.specific_values.map(d => {
			this.specific_y_lines.add(this.snap.g(
				this.snap.line(0, 0, this.width - 110, 0).attr({
					class: d.line_type === "dashed" ? "dashed": ""
				}),
				this.snap.text(this.width - 110, 0, d.name.toUpperCase()).attr({
					dy: ".32em",
					class: "specific-value",
				})
			).attr({
				class: "tick",
				transform: `translate(0, ${100 - 100/(this.upper_graph_bound/d.value) })`
			}));
		});
	}
}

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
				transform: `translate(${ i * (this.width-50)/(this.x_points.length - 1) }, 0)`
			}));
		});
	}

	make_units() {
		let points_list = []
		this.y_values.map((value, i) => {
			let x = i * (this.width-50)/(this.x_points.length - 1);
			let y = (100 - 100/(this.upper_graph_bound/value));
			this.graph_list.add(this.snap.circle( x, y, 4));
			points_list.push(x+","+y);
		});

		this.make_path("M"+points_list.join("L"));
	}

	make_path(path_str) {
		this.graph_list.prepend(this.snap.path(path_str));
	}

	show_specific_values() {
		this.specific_values.map(d => {
			this.specific_y_lines.add(this.snap.g(
				this.snap.line(0, 0, this.width - 110, 0).attr({
					class: d.line_type === "dashed" ? "dashed": ""
				}),
				this.snap.text(this.width - 110, 0, d.name.toUpperCase()).attr({
					dy: ".32em",
					class: "specific-value",
				})
			).attr({
				class: "tick",
				transform: `translate(0, ${100 - 100/(this.upper_graph_bound/d.value) })`
			}));
		});
	}

}