// specific_values = [
// 	{
// 		name: "Average",
// 		line_type: "dashed",	// "dashed" or "solid"
// 		value: 10
// 	},

// summary = [
// 	{
// 		name: "Total",
// 		color: 'blue',		// Indicator colors: 'grey', 'blue', 'red', 'green', 'orange',
// 					// 'purple', 'darkgrey', 'black', 'yellow', 'lightblue'
// 		value: 80
// 	}
// ]

// Graph: Abstract object
frappe.ui.Graph = class Graph {
	constructor({
		parent = null,

		title = '', subtitle = '',

		y = [],
		x = [],

		x_formatted = [],
		y_formatted = [],

		specific_values = [],
		summary = [],

		color = 'blue',
		mode = '',
	}) {

		if(Object.getPrototypeOf(this) === frappe.ui.Graph.prototype) {
			if(mode === 'line') {
				return new frappe.ui.LineGraph(arguments[0]);
			} else if(mode === 'bar') {
				return new frappe.ui.BarGraph(arguments[0]);
			}
			// else if(mode === 'percentage') {
			// 	return new frappe.ui.PercentageGraph(arguments[0]);
			// }
		}

		// Calculate height width and translate initially

		let height = 240;

		this.parent = parent;
		this.base_height = height;
		this.height = height - 40;

		this.title = title;
		this.subtitle = subtitle;

		this.y = y;
		this.x = x;

		this.specific_values = specific_values;
		this.summary = summary;

		this.color = color;
		this.mode = mode;

		this.$graph = null;

		frappe.require("assets/frappe/js/lib/snap.svg-min.js", this.setup.bind(this));
	}

	setup() {
		this.refresh();
	}

	refresh() {

		this.base_width = this.parent.width() - 20;
		this.width = this.base_width - 100;

		this.setup_container();

		this.setup_values();
		this.setup_utils();

		this.setup_components();
		this.make_y_axis();
		this.make_x_axis();

		this.y.map((d, i) => {
			this.make_units(d.y_tops, d.color, i);
			this.make_path(d.y_tops, d.color);
		});

		if(this.specific_values.length > 0) {
			this.show_specific_values();
		}
		this.setup_group();

		if(this.summary.length > 0) {
			this.show_summary();
		}
	}

	setup_container() {
		// Graph needs a dedicated parent element
		this.parent.empty();

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
			.addClass(this.mode + '-graph')
			.appendTo($graphics);

		this.$svg = $(`<svg class="svg" width="${this.base_width}" height="${this.base_height}"></svg>`);
		this.$graph.append(this.$svg);

		this.snap = new Snap(this.$svg[0]);
	}

	setup_values() {
		// Multiplier
		let all_values = this.specific_values.map(d => d.value);
		this.y.map(d => {
			all_values = all_values.concat(d.values);
		});
		[this.upper_limit, this.parts] = this.get_upper_limit_and_parts(all_values);
		this.multiplier = this.height / this.upper_limit;

		// Baselines
		this.set_avg_unit_width_and_x_offset();

		this.x_axis_values = this.x.map((d, i) => this.x_offset + i * this.avg_unit_width);
		this.y_axis_values = this.get_y_axis_values(this.upper_limit, this.parts);

		// Data points
		this.y.map(d => {
			d.y_tops = d.values.map( val => this.height - val * this.multiplier );
		});
	}

	set_avg_unit_width_and_x_offset() {
		this.avg_unit_width = this.width/(this.x.length - 1);
		this.x_offset = 0;
	}

	setup_components() {
		this.y_axis_group = this.snap.g().attr({ class: "y axis" });
		this.x_axis_group = this.snap.g().attr({ class: "x axis" });
		this.data_units = this.snap.g().attr({ class: "data-points" });
		this.specific_y_lines = this.snap.g().attr({ class: "specific axis" });
	}

	setup_group() {
		this.snap.g(
			this.y_axis_group,
			this.x_axis_group,
			this.data_units,
			this.specific_y_lines
		).attr({
			transform: "translate(60, 10)"  // default
		});
	}

	// make HORIZONTAL lines for y values
	make_y_axis() {
		let width, text_end_at, label_class = '';
		if(this.y_axis_mode === 'span') {		// long spanning lines
			width = this.width;
			text_end_at = -3;
		} else if(this.y_axis_mode === 'tick'){	// short label lines
			width = -6;
			text_end_at = -9;
			label_class = 'y-axis-label';
		}

		this.y_axis_values.map((point) => {
			this.y_axis_group.add(this.snap.g(
				this.snap.line(0, 0, width, 0),
				this.snap.text(text_end_at, 0, point+"").attr({
					dy: ".32em",
					class: "y-value-text"
				})
			).attr({
				class: `tick ${label_class}`,
				transform: `translate(0, ${this.height - point * this.multiplier })`
			}));
		});
	}

	// make VERTICAL lines for x values
	make_x_axis() {
		let start_at, height, text_start_at, label_class = '';
		if(this.x_axis_mode === 'span') {		// long spanning lines
			start_at = -7;
			height = this.height + 15;
			text_start_at = this.height + 25;
		} else if(this.x_axis_mode === 'tick'){	// short label lines
			start_at = this.height
			height = 6;
			text_start_at = 9;
			label_class = 'x-axis-label';
		}

		this.x_axis_group.attr({
			transform: `translate(0,${start_at})`
		});
		this.x.map((point, i) => {
			this.x_axis_group.add(this.snap.g(
				this.snap.line(0, 0, 0, height),
				this.snap.text(0, text_start_at, point).attr({
					dy: ".71em",
					class: "x-value-text"
				})
			).attr({
				class: `tick ${label_class}`,
				transform: `translate(${ this.x_axis_values[i] }, 0)`
			}));
		});
	}

	make_units(y_values, color, dataset_index) {
		let d = this.unit_args;
		y_values.map((y, i) => {
			this.data_units.add(this.draw[d.type](this.x_axis_values[i],
				y, d.args, color, dataset_index));
		});
	}

	make_path(y_values, color) { }

	show_specific_values() {
		this.specific_values.map(d => {
			this.specific_y_lines.add(this.snap.g(
				this.snap.line(0, 0, this.width - 70, 0).attr({
					class: d.line_type === "dashed" ? "dashed": ""
				}),
				this.snap.text(this.width - 95, 0, d.name.toUpperCase()).attr({
					dy: ".32em",
					class: "specific-value",
				})
			).attr({
				class: "tick",
				transform: `translate(0, ${this.height - d.value * this.multiplier })`
			}));
		});
	}

	show_summary() {
		// this.summary.map(d => {
		// 	this.$stats_container.append($(`<div class="stats">
		// 		<span class="indicator ${d.color}">${d.name}: ${d.value}</span>
		// 	</div>`));
		// });
	}

	// Helpers
	get_strwidth(string) {
		return string.length * 8;
	}

	get_upper_limit_and_parts(array) {
		let max_val = parseInt(Math.max(...array));
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

	get_y_axis_values(upper_limit, parts) {
		let y_axis = [];
		for(var i = 0; i <= parts; i++){
			y_axis.push(upper_limit / parts * i);
		}
		return y_axis;
	}

	// Objects
	setup_utils() {
		this.draw = {
			'bar': (x, y, args, color, index) => {
				let total_width = this.avg_unit_width - args.space_width;
				let start_x = x - total_width/2;

				let width = total_width / args.no_of_datasets;
				let current_x = start_x + width * index;
				return this.snap.rect(current_x, y, width, this.height - y).attr({
					class: `bar mini fill ${color}`
				});
			},
			'dot': (x, y, args, color) => {
				return this.snap.circle(x, y, args.radius).attr({
					class: `fill ${color}`
				});
			}
		}
	}
};

frappe.ui.BarGraph = class BarGraph extends frappe.ui.Graph {
	constructor(args = {}) {
		super(args);
	}

	setup_values() {
		var me = this;
		super.setup_values();
		this.x_offset = this.avg_unit_width;
		this.y_axis_mode = 'span';
		this.x_axis_mode = 'tick';
		this.unit_args = {
			type: 'bar',
			args: {
				space_width: this.y_axis_mode.length > 1 ?
					me.avg_unit_width/2 : me.avg_unit_width/8,
				no_of_datasets: this.y.length
			}
		}
	}

	set_avg_unit_width_and_x_offset() {
		this.avg_unit_width = this.width/(this.x.length + 1);
		this.x_offset = this.avg_unit_width;
	}
};

frappe.ui.LineGraph = class LineGraph extends frappe.ui.Graph {
	constructor(args = {}) {
		super(args);
	}

	setup_values() {
		super.setup_values();
		this.y_axis_mode = 'tick';
		this.x_axis_mode = 'span';
		this.unit_args = {
			type: 'dot',
			args: { radius: 4 }
		}
	}

	make_path(y_values, color) {
		let points_list = y_values.map((y, i) => (this.x_axis_values[i] + ',' + y));
		let path_str = "M"+points_list.join("L");
		this.data_units.prepend(this.snap.path(path_str).attr({class: `stroke ${color}`}));
	}
};

frappe.ui.PercentageGraph = class PercentageGraph extends frappe.ui.Graph {
	constructor({

	}) {

	}
}