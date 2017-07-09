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
		this.setup_y_axis();
		this.setup_x_axis();
		this.setup_graph();
		this.show_specific_values();
		this.setup_group();
		this.show_summary();
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
			.addClass('bar-graph')
			.appendTo($graphics);

		this.$svg = $(`<svg class="svg" width="${this.width}" height="${this.height}"></svg>`);
		this.$graph.append(this.$svg);

		this.snap = new Snap(this.$svg[0]);
	}

	setup_group() {
		this.snap.g(
			this.y_axis_group,
			this.x_axis_group,
			this.graph_list,
			this.specific_y_lines
		).attr({
			transform: "translate(30, 10)"  // default
		});
	}

	setup_y_axis() {
		let y_axis = this.get_y_axis(this.y_values);
		this.y_axis_group = this.snap.g().attr({
			class: "y axis"
		});

		y_axis.map((point) => {
			this.y_axis_group.add(this.snap.g(
				this.snap.line(0, 0, this.width, 0),
				this.snap.text(-3, 0, point+"").attr({
					dy: ".32em",
					class: "y-value-text"
				})
			).attr({
				class: "tick",
				transform: `translate(0, ${100 - (100/(y_axis.length-1) * y_axis.indexOf(point)) })`
			}));
		});
	}

	setup_x_axis() {
		this.x_axis_group = this.snap.g().attr({
			class: "x axis",
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

	setup_graph() {
		let upper_graph_bound = this.get_upper_limit_and_parts(this.y_values)[0];
		this.graph_list = this.snap.g().attr({
			class: "data-points",
		});

		this.y_values.map((value, i) => {
			this.graph_list.add(this.snap.g(
				this.snap.rect(
					0,
					(100 - 100/(upper_graph_bound/value)),
					18,
					100/(upper_graph_bound/value)
				)
			).attr({
				class: "bar mini",
				transform: `translate(${ 18 + i * 20 }, 0)`,
			}));
		});
	}

	show_specific_values() {
		if(this.specific_values.length > 0) {

			let upper_graph_bound = this.get_upper_limit_and_parts(this.y_values)[0];
			this.specific_y_lines = this.snap.g().attr({
				class: "specific axis",
			});

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
					transform: `translate(0, ${100 - 100/(upper_graph_bound/d.value) })`
				}));
			});
		}
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

	// Helpers
	get_upper_limit_and_parts(array) {
		let max_val = Math.max(...array);
		if((max_val+"").length <= 1) {
			return 10;
		} else {
			let multiplier = Math.pow(10, ((max_val+"").length - 1));
			let significant = Math.ceil(max_val/multiplier);
			let parts = (significant < 5) ? (significant + 1) : (Math.ceil((significant+1)/2));
			let incr = (significant < 5) ? 1 : 2;
			return [(significant + incr) * multiplier, parts];
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