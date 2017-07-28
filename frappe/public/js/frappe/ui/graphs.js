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
		height = 240,

		title = '', subtitle = '',

		y = [],
		x = [],

		specific_values = [],
		summary = [],

		mode = '',
	}) {

		if(Object.getPrototypeOf(this) === frappe.ui.Graph.prototype) {
			if(mode === 'line') {
				return new frappe.ui.LineGraph(arguments[0]);
			} else if(mode === 'bar') {
				return new frappe.ui.BarGraph(arguments[0]);
			} else if(mode === 'percentage') {
				return new frappe.ui.PercentageGraph(arguments[0]);
			}
		}

		this.parent = parent;
		this.base_height = height;
		this.height = height - 40;

		this.translate_x = 60;
		this.translate_y = 10;

		this.title = title;
		this.subtitle = subtitle;

		this.y = y;
		this.x = x;

		this.specific_values = specific_values;
		this.summary = summary;

		this.mode = mode;

		this.current_hover_index = 0;
		this.current_selected_index = 0;

		this.$graph = null;

		// Validate all arguments, check passed data format, set defaults

		frappe.require("assets/frappe/js/lib/snap.svg-min.js", this.setup.bind(this));
	}

	setup() {
		this.bind_window_event();
		this.refresh();
	}

	bind_window_event() {
		$(window).on('resize orientationChange', () => {
			this.refresh();
		});
	}

	refresh() {

		this.base_width = this.parent.width();
		this.width = this.base_width - this.translate_x * 2;

		this.setup_container();
		this.setup_components();
		this.setup_values();
		this.setup_utils();

		this.make_graph_components();
		this.make_tooltip();

		if(this.summary.length > 0) {
			this.show_custom_summary();
		} else {
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
			.append($(`<div class="graph-stats-container"></div>`))
			.appendTo(this.parent);

		this.$graphics = this.container.find('.graphics');
		this.$stats_container = this.container.find('.graph-stats-container');

		this.$graph = $('<div>')
			.addClass(this.mode + '-graph')
			.appendTo(this.$graphics);

		this.$graph.append(this.make_graph_area());
	}

	make_graph_area() {
		this.$svg = $(`<svg class="svg" width="${this.base_width}" height="${this.base_height}"></svg>`);
		this.snap = new Snap(this.$svg[0]);
		return this.$svg;
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

		this.x_axis_values = this.x.values.map((d, i) => this.x_offset + i * this.avg_unit_width);
		this.y_axis_values = this.get_y_axis_values(this.upper_limit, this.parts);

		// Data points
		this.y.map(d => {
			d.y_tops = d.values.map( val => this.height - val * this.multiplier );
			d.data_units = [];
		});

		this.calc_min_tops();
	}

	set_avg_unit_width_and_x_offset() {
		this.avg_unit_width = this.width/(this.x.values.length - 1);
		this.x_offset = 0;
	}

	calc_min_tops() {
		this.y_min_tops = new Array(this.x_axis_values.length).fill(9999);
		this.y.map(d => {
			d.y_tops.map( (y_top, i) => {
				if(y_top < this.y_min_tops[i]) {
					this.y_min_tops[i] = y_top;
				}
			});
		});
	}

	setup_components() {
		this.y_axis_group = this.snap.g().attr({ class: "y axis" });
		this.x_axis_group = this.snap.g().attr({ class: "x axis" });
		this.data_units = this.snap.g().attr({ class: "data-points" });
		this.specific_y_lines = this.snap.g().attr({ class: "specific axis" });
	}

	make_graph_components() {
		this.make_y_axis();
		this.make_x_axis();
		this.y_colors = ['lightblue', 'purple', 'blue', 'green', 'lightgreen',
			'yellow', 'orange', 'red']

		this.y.map((d, i) => {
			this.make_units(d.y_tops, d.color || this.y_colors[i], i);
			this.make_path(d, d.color || this.y_colors[i]);
		});

		if(this.specific_values.length > 0) {
			this.show_specific_values();
		}
		this.setup_group();
	}

	setup_group() {
		this.snap.g(
			this.y_axis_group,
			this.x_axis_group,
			this.data_units,
			this.specific_y_lines
		).attr({
			transform: `translate(${this.translate_x}, ${this.translate_y})`
		});
	}

	// make HORIZONTAL lines for y values
	make_y_axis() {
		let width, text_end_at = -9, label_class = '', start_at = 0;
		if(this.y_axis_mode === 'span') {		// long spanning lines
			width = this.width + 6;
			start_at = -6;
		} else if(this.y_axis_mode === 'tick'){	// short label lines
			width = -6;
			label_class = 'y-axis-label';
		}

		this.y_axis_values.map((point) => {
			this.y_axis_group.add(this.snap.g(
				this.snap.line(start_at, 0, width, 0),
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
			start_at = this.height;
			height = 6;
			text_start_at = 9;
			label_class = 'x-axis-label';
		}

		this.x_axis_group.attr({
			transform: `translate(0,${start_at})`
		});
		this.x.values.map((point, i) => {
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
			let data_unit = this.draw[d.type](this.x_axis_values[i],
				y, d.args, color, dataset_index);
			this.data_units.add(data_unit);
			this.y[dataset_index].data_units.push(data_unit);
		});
	}

	make_path() { }

	make_tooltip() {
		// should be w.r.t. this.parent
		this.tip = new frappe.ui.SvgTip({
			parent: this.$graphics,
		});
		this.bind_tooltip();
	}

	bind_tooltip() {
		// should be w.r.t. this.parent, but will have to take care of
		// all the elements and padding, margins on top
		this.$graphics.on('mousemove', (e) => {
			let offset = this.$graphics.offset();
			var relX = e.pageX - offset.left - this.translate_x;
			var relY = e.pageY - offset.top - this.translate_y;

			if(relY < this.height + this.translate_y * 2) {
				this.map_tooltip_x_position_and_show(relX);
			} else {
				this.tip.hide_tip()
			}
		});
	}

	map_tooltip_x_position_and_show(relX) {
		for(var i=this.x_axis_values.length - 1; i >= 0 ; i--) {
			let x_val = this.x_axis_values[i];
			// let delta = i === 0 ? this.avg_unit_width : x_val - this.x_axis_values[i-1];
			if(relX > x_val - this.avg_unit_width/2) {
				let x = x_val + this.translate_x - 0.5;
				let y = this.y_min_tops[i] + this.translate_y;
				let title = this.x.formatted && this.x.formatted.length>0
					? this.x.formatted[i] : this.x.values[i];
				let values = this.y.map((set, j) => {
					return {
						title: set.title,
						value: set.formatted ? set.formatted[i] : set.values[i],
						color: set.color || this.y_colors[j],
					}
				});

				this.tip.set_values(x, y, title, '', values);
				this.tip.show_tip();
				break;
			}
		}
	}

	show_specific_values() {
		this.specific_values.map(d => {
			this.specific_y_lines.add(this.snap.g(
				this.snap.line(0, 0, this.width, 0).attr({
					class: d.line_type === "dashed" ? "dashed": ""
				}),
				this.snap.text(this.width + 5, 0, d.name.toUpperCase()).attr({
					dy: ".32em",
					class: "specific-value",
				})
			).attr({
				class: "tick",
				transform: `translate(0, ${this.height - d.value * this.multiplier })`
			}));
		});
	}

	show_summary() { }

	show_custom_summary() {
		this.summary.map(d => {
			this.$stats_container.append($(`<div class="stats">
				<span class="indicator ${d.color}">${d.name}: ${d.value}</span>
			</div>`));
		});
	}

	change_values(new_y) {
		let u = this.unit_args;
		this.y.map((d, i) => {
			let new_d = new_y[i];
			new_d.y_tops = new_d.values.map(val => this.height - val * this.multiplier);

			// below is equal to this.y[i].data_units..
			d.data_units.map((unit, j) => {
				let current_y_top = d.y_tops[j];
				let current_height = this.height - current_y_top;

				let new_y_top = new_d.y_tops[j];
				let new_height = current_height - (new_y_top - current_y_top);

				this.animate[u.type](unit, new_y_top, {new_height: new_height});
			});
		});

		// Replace values and formatted and tops
		this.y.map((d, i) => {
			let new_d = new_y[i];
			[d.values, d.formatted, d.y_tops] = [new_d.values, new_d.formatted, new_d.y_tops];
		});

		this.calc_min_tops();

		// create new x,y pair string and animate path
		if(this.y[0].path) {
			new_y.map((e, i) => {
				let new_points_list = e.y_tops.map((y, i) => (this.x_axis_values[i] + ',' + y));
				let new_path_str = "M"+new_points_list.join("L");
				this.y[i].path.animate({d:new_path_str}, 300, mina.easein);
			});
		}
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
		};

		this.animate = {
			'bar': (bar, new_y, args) => {
				bar.animate({height: args.new_height, y: new_y}, 300, mina.easein);
			},
			'dot': (dot, new_y) => {
				dot.animate({cy: new_y}, 300, mina.easein);
			}
		};
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
				space_width: this.y.length > 1 ?
					me.avg_unit_width/2 : me.avg_unit_width/8,
				no_of_datasets: this.y.length
			}
		};
	}

	set_avg_unit_width_and_x_offset() {
		this.avg_unit_width = this.width/(this.x.values.length + 1);
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
		};
	}

	make_path(d, color) {
		let points_list = d.y_tops.map((y, i) => (this.x_axis_values[i] + ',' + y));
		let path_str = "M"+points_list.join("L");
		d.path = this.snap.path(path_str).attr({class: `stroke ${color}`});
		this.data_units.prepend(d.path);
	}
};

frappe.ui.PercentageGraph = class PercentageGraph extends frappe.ui.Graph {
	constructor(args = {}) {
		super(args);
	}

	make_graph_area() {
		this.$graphics.addClass('graph-focus-margin').attr({
			style: `margin-top: 45px;`
		});
		this.$stats_container.addClass('graph-focus-margin').attr({
			style: `padding-top: 0px; margin-bottom: 30px;`
		});
		this.$div = $(`<div class="div" width="${this.base_width}"
			height="${this.base_height}">
				<div class="progress-chart"></div>
			</div>`);
		this.$chart = this.$div.find('.progress-chart');
		return this.$div;
	}

	setup_values() {
		this.x.totals = this.x.values.map((d, i) => {
			let total = 0;
			this.y.map(e => {
				total += e.values[i];
			});
			return total;
		});

		if(!this.x.colors) {
			this.x.colors = ['green', 'blue', 'purple', 'red', 'orange',
				'yellow', 'lightblue', 'lightgreen'];
		}
	}

	setup_utils() { }
	setup_components() {
		this.$percentage_bar = $(`<div class="progress">
		</div>`).appendTo(this.$chart); // get this.height, width and avg from this if needed
	}

	make_graph_components() {
		this.grand_total = this.x.totals.reduce((a, b) => a + b, 0);
		this.x.units = [];
		this.x.totals.map((total, i) => {
			let $part = $(`<div class="progress-bar background ${this.x.colors[i]}"
				style="width: ${total*100/this.grand_total}%"></div>`);
			this.x.units.push($part);
			this.$percentage_bar.append($part);
		});
	}

	bind_tooltip() {
		this.x.units.map(($part, i) => {
			$part.on('mouseenter', () => {
				let g_off = this.$graphics.offset(), p_off = $part.offset();

				let x = p_off.left - g_off.left + $part.width()/2;
				let y = p_off.top - g_off.top - 6;
				let title = (this.x.formatted && this.x.formatted.length>0
					? this.x.formatted[i] : this.x.values[i]) + ': ';
				let percent = (this.x.totals[i]*100/this.grand_total).toFixed(1);

				this.tip.set_values(x, y, title, percent);
				this.tip.show_tip();
			});
		});
	}

	show_summary() {
		let x_values = this.x.formatted && this.x.formatted.length > 0
			? this.x.formatted : this.x.values;
		this.x.totals.map((d, i) => {
			if(d) {
				this.$stats_container.append($(`<div class="stats">
					<span class="indicator ${this.x.colors[i]}">
						<span class="text-muted">${x_values[i]}:</span>
						${d}
					</span>
				</div>`));
			}
		});
	}
};

frappe.ui.CompositeGraph = class {
	constructor({
		parent = null
	}) {
		this.parent = parent;
		this.title_name = '';
		this.title_value = '';
		this.list_values = [];

		this.x = 0;
		this.y = 0;

		this.top = 0;
		this.left = 0;

		this.setup();
	}


}

frappe.ui.Heatmap = class {
	constructor({
		parent = null
	}) {
		this.parent = parent;
		this.title_name = '';
		this.title_value = '';
		this.list_values = [];

		this.x = 0;
		this.y = 0;

		this.top = 0;
		this.left = 0;

		this.setup();
	}


}

frappe.ui.SvgTip = class {
	constructor({
		parent = null
	}) {
		this.parent = parent;
		this.title_name = '';
		this.title_value = '';
		this.list_values = [];

		this.x = 0;
		this.y = 0;

		this.top = 0;
		this.left = 0;

		this.setup();
	}

	setup() {
		this.make_tooltip();
	}

	refresh() {
		this.fill();
		this.calc_position();
		// this.show_tip();
	}

	make_tooltip() {
		this.container = $(`<div class="graph-svg-tip comparison">
			<span class="title"></span>
			<ul class="data-point-list"></ul>
			<div class="svg-pointer"></div>
		</div>`).appendTo(this.parent);
		this.hide_tip();

		this.title = this.container.find('.title');
		this.data_point_list = this.container.find('.data-point-list');

		this.parent.on('mouseleave', () => {
			this.hide_tip();
		});
	}

	fill() {
		this.title.html(`${this.title_name}<strong>${this.title_value}</strong>`);
		this.data_point_list.empty();
		this.list_values.map((set, i) => {
			let $li = $(`<li>
				<strong style="display: block;">${set.value ? set.value : '' }</strong>
				${set.title ? set.title : '' }
			</li>`).addClass(`border-top ${set.color || 'black'}`);

			this.data_point_list.append($li);
		});
	}

	calc_position() {
		this.top = this.y - this.container.height();
		this.left = this.x - this.container.width()/2;
		let max_left = this.parent.width() - this.container.width();

		let $pointer = this.container.find('.svg-pointer');

		if(this.left < 0) {
			$pointer.css({ 'left': `calc(50% - ${-1 * this.left}px)` });
			this.left = 0;
		} else if(this.left > max_left) {
			let delta = this.left - max_left;
			$pointer.css({ 'left': `calc(50% + ${delta}px)` });
			this.left = max_left;
		} else {
			$pointer.css({ 'left': `50%` });
		}
	}

	set_values(x, y, title_name = '', title_value = '', list_values = []) {
		this.title_name = title_name;
		this.title_value = title_value;
		this.list_values = list_values;
		this.x = x;
		this.y = y;
		this.refresh();
	}

	hide_tip() {
		this.container.css({
			'top': '0px',
			'left': '0px',
			'opacity': '0'
		});
	}

	show_tip() {
		this.container.css({
			'top': this.top + 'px',
			'left': this.left + 'px',
			'opacity': '1'
		});
	}
};


frappe.provide("frappe.ui.graphs");

frappe.ui.graphs.get_timeseries = function(start, frequency, length) {

}

frappe.ui.graphs.map_c3 = function(chart) {
	if (chart.data) {
		let data = chart.data;
		let mode = chart.chart_type || 'line';
		if(mode === 'pie') {
			mode = 'percentage';
		}

		let x = {}, y = [];

		if(data.columns) {
			let columns = data.columns;

			x.values = columns.filter(col => {
				return col[0] === data.x;
			})[0];

			if(x.values && x.values.length) {
				let dataset_length = x.values.length;
				let dirty = false;
				columns.map(col => {
					if(col[0] !== data.x) {
						if(col.length === dataset_length) {
							let title = col[0];
							col.splice(0, 1);
							y.push({
								title: title,
								values: col,
							});
						} else {
							dirty = true;
						}
					}
				})

				if(dirty) {
					return;
				}

				x.values.splice(0, 1);

				return {
					mode: mode,
					y: y,
					x: x
				}

			}
		} else if(data.rows) {
			let rows = data.rows;
			x.values = rows[0];

			rows.map((row, i) => {
				if(i === 0) {
					x.values = row;
				} else {
					y.push({
						title: 'data' + i,
						values: row,
					})
				}
			});

			return {
				mode: mode,
				y: y,
				x: x
			}
		}
	}
}
