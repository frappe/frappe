/*

Opts:
	parent_selector: [reqd]
	label_width: default 200
	step: 24 // no of hours
	column_width: 15 // pixels
	date_format: 'YYYY-MM-DD'
	bar_height: 26
	bar_gap: 24
	arrow_curve: 15

*/

var Gantt = Class.extend({
	init: function(opts) {
		this.opts = opts;
		this.tasks = [];
		this.set_defaults();
		this.groups = {};
		this.make();
	},
	set_defaults: function() {
		var defaults = {
			label_width: 200,
			header_height: 50,
			step: 24 * 1,
			column_width: 20,
			date_format: 'YYYY-MM-DD',
			bar_height: 26,
			bar_gap: 20,
			arrow_curve: 15,
			bar_color: "rgba(94, 100, 255, 0.5)",
			bar_progress_color: "rgb(94, 100, 255)",
			padding: 20
		}
		for(key in defaults) {
			if(!this.opts[key]) this.opts[key] = defaults[key];
		}
	},
	make: function() {
		this.canvas = Snap(this.opts.parent_selector);
		this.setup_groups();
	},
	render: function() {
		this.prepare_dates();

		this.make_grid();
		this.make_dates();
		this.make_arrows();
		this.make_label();
		this.make_bars();
	},
	prepare_dates: function() {
		var me = this;
		this.tasks.forEach(function(task) {
			// momentify
			task._start = moment(task.start, me.opts.date_format);
			task._end = moment(task.end, me.opts.date_format);

			// set global start and end date
			if(!me.start || task._start < me.start) {
				me.start = task._start;
			}
			if(!me.end || task._end > me.end) {
				me.end = task._end;
			}
		});
		this.setup_dates();
	},
	add_task: function(task) {
		task._index = this.tasks.length;
		this.tasks.push(task);
	},
	setup_groups: function() {
		var me = this;
		// make groups
		["grid", "label", "date", "arrow", "progress", "bar", "details", "ruler"].forEach(function(name) {
			me.groups[name] = me.canvas.group().attr({'id': name});
		});
	},
	make_grid: function () {

		var me = this;

		var x = this.opts.label_width + this.dates.length * this.opts.column_width,
			y = this.opts.header_height + this.opts.padding + (this.opts.bar_height + this.opts.bar_gap) * this.tasks.length;

		me.canvas.rect(0,0, x, y).attr({
			"fill": "none"
		}).appendTo(me.groups.grid);

		me.canvas.rect(0,0, x, this.opts.header_height + 10).attr({
			"fill": "#fff"
		}).appendTo(me.groups.grid)

		var rows = me.canvas.group();
		var lines = me.canvas.group();
		rows.appendTo(me.groups.grid)
		lines.appendTo(me.groups.grid)

		var start_y = me.opts.header_height + me.opts.padding/2;
		this.tasks.forEach(function (task, i) {
			var width = x;
			var height = me.opts.bar_height + me.opts.padding;

			var color = '#fff'
			if(i % 2 != 0) {
				color = '#ffffff'
			}
			else {
				color = '#f5f5f5'
			}

			me.canvas.rect(0, start_y, width, height).attr({
				fill: color
			}).appendTo(rows)

			me.canvas.line(0, start_y+height, width, start_y+height).attr({
				stroke: '#EBEFF2'
			}).appendTo(lines)
			start_y += me.opts.bar_height + me.opts.padding
		})

		me.canvas.rect(0, 0, x, this.opts.header_height + 10).attr({
			"fill": "none",
			"stroke": "#e0e0e0",
			"stroke-width": 1
		}).appendTo(me.groups.grid)

		me.canvas.attr({
			// viewBox: "0 0 " + (x+10) + " " + (y+10),
			height: y,
			width: x
		})

	},
	make_dates: function() {
		var me = this;

		this.dates.forEach(function(date, i) {
			var text = '';
			var month = '';
			if(i===0) {
				text = date.format('D');
				month = date.format('MMMM');
			} else {
				if(date.date() !== me.dates[i-1].date()) {
					text = date.format('D');
				}
				if(date.month() !== me.dates[i-1].month()) {
					month = date.format('MMMM')
				}
			}
			var el_date = me.canvas.text(me.opts.label_width + (i * me.opts.column_width), me.opts.header_height, text);
			var el_month = me.canvas.text(me.opts.label_width + (i * me.opts.column_width) - 5, me.opts.header_height - 20, month).attr('text-anchor', 'start');

			me.groups.date.add(el_date);
			me.groups.date.add(el_month);
		});

		me.groups.date.attr({
			"text-anchor": "middle",
			"font-size": "12px"
		})
	},
	setup_dates: function() {
		this.dates = [];
		var cur_date = null;
		while(cur_date===null || cur_date < this.end) {
			if(!cur_date) {
				cur_date = this.start.clone();
			} else {
				cur_date = cur_date.clone().add(this.opts.step, 'hours');
			}
			this.dates.push(cur_date);
		}
	},
	make_arrows: function () {
		var me = this;
		this.tasks.forEach(function (task) {
			if(task.dependent) {
				var dependents = task.dependent.split(',');
				dependents.forEach(function (task_dependent) {
					task_dependent = task_dependent.trim()
					var dependent = me.get_task(task_dependent);
					var start_x = dependent._start.diff(me.start, 'hours')/me.opts.step * me.opts.column_width + me.opts.label_width
									+ (dependent._end.diff(dependent._start, 'hours')/me.opts.step * me.opts.column_width) / 2;
					var start_y = me.opts.header_height + me.opts.bar_height + (me.opts.bar_gap + me.opts.bar_height) * dependent._index;
					var end_x = task._start.diff(me.start, 'hours')/me.opts.step * me.opts.column_width + me.opts.label_width;
					var end_y = me.opts.header_height + me.opts.bar_height/2 + (me.opts.bar_gap + me.opts.bar_height) * task._index;

					var path = Snap.format("M {start_x} {start_y} V {offset} a {curve} {curve} 0 0 0 {curve} {curve}\
							L {end_x} {end_y} m -5 -5 l 5 5 l -5 5",
						{
							start_x: start_x,
							start_y: start_y + me.opts.padding,
							end_x: end_x - me.opts.padding,
							end_y: end_y + me.opts.padding,
							offset: end_y - me.opts.arrow_curve + me.opts.padding,
							curve: me.opts.arrow_curve
						});
					var el_arrow = me.canvas.path(path);
					me.groups.arrow.add(el_arrow);
				})
			}
		})

		me.groups.arrow.attr({
			"stroke-width" : "1.4",
			"fill" : "none",
			"stroke" : "#333"
		});

	},
	get_task: function (name) {
		var result = null;
		this.tasks.forEach(function (task) {
			if (task.name === name){
				result = task;
			}
		})
		return result;
	},
	make_label: function () {
		var me = this;
		var label_x = me.opts.label_width - me.opts.padding,
			label_y = me.opts.header_height + me.opts.bar_height/2 + me.opts.padding;

		this.tasks.forEach(function (task) {
			var el_label = me.canvas.text(label_x, label_y, task.name).appendTo(me.groups.label);
			label_y += me.opts.bar_height + me.opts.bar_gap;
		})

		me.groups.label.attr({
			"text-anchor": "end",
			"dominant-baseline": "central"
		})
	},
	make_bars: function () {
		var me = this;

		var bar_position_x,
			bar_position_y = this.opts.header_height + me.opts.padding;

		this.tasks.forEach(function (task) {
			var task_start = task._start.diff(me.start, 'hours')/me.opts.step;
			bar_position_x = me.opts.label_width + task_start * me.opts.column_width;

			var bar = new Bar({
				canvas: me.canvas,
				task: task,
				x: bar_position_x,
				y: bar_position_y,
				unit_width: me.opts.column_width,
				step: me.opts.step,
				details: me.groups.details
			});

			me.groups.bar.add(bar.group);
			bar_position_y += me.opts.bar_height + me.opts.bar_gap;
		})
	}
});

/*
	Class: Bar

	Opts:
		canvas [reqd]
		task [reqd]
		unit_width [reqd]
		x
		y
*/

var Bar = Class.extend({
	init: function (opts) {
		for(key in opts) {
			this[key] = opts[key];
		}
		this.set_defaults();
		this.prepare();
		this.draw();
		this.bind_show_details();
		this.bind_drag();
	},
	set_defaults: function () {
		var defaults = {
			height: 26,
			x: 0,
			y: 0,
			color: "rgba(94, 100, 255, 0.5)"
		}
		for(key in defaults) {
			if(!this[key]) this[key] = defaults[key];
		}
	},
	prepare: function () {
		this.duration = this.task._end.diff(this.task._start, 'hours')/this.step;
		this.width = this.unit_width * this.duration;
		this.progress_width = this.unit_width * this.duration * (this.task.progress/100);
		this.group = this.canvas.group();
	},
	draw: function () {
		var el_progress_bar = this.canvas.rect(this.x, this.y, this.progress_width, this.height, 5, 5);
		var el_bar = this.canvas.rect(this.x, this.y, this.width, this.height, 5, 5);
		this.group.add(el_bar);
		this.group.add(el_progress_bar);
		this.group.attr({
			"data-editable": 0,
			fill: this.color
		});
	},
	bind_show_details: function () {
		var me = this;

		this.group.mouseover(function (e, x, y) {
			var box = me.canvas.group();
			box.attr({
				transform: "translate(" + x +"," + y + ")"
			})

			box.appendTo(me.details);

			var line1 = me.task.name + ": " + me.task._start.format("MMM D") + " - " + me.task._end.format("MMM D");
			var el_line1 = me.canvas.text(0,0, line1).attr({
				dx: 10,
				dy: 30,
				"fill": "#424242",
				"font-weight": 500,
				"font-size": 14
			});

			me.canvas.rect(0, 0, 0, 110, 2, 2).attr({
				stroke: "#c1c1c1",
				"stroke-width": 1.1,
				fill: "#fff",
				filter: "url(#rablfilter0)"
			}).appendTo(box);

			var bbox = el_line1.getBBox();
			box.select('rect').attr({
				width: bbox.width + 20
			})

			el_line1.appendTo(box);

			var line2 = "Duration: " + me.task._end.diff(me.task._start, 'days') + " days";
			me.canvas.text(0,0, line2).attr({
				dx: 10,
				dy: 65,
				"fill": "#757575"
			}).appendTo(box);

			var line3 = "Progress: " + me.task.progress + "%";
			me.canvas.text(0,0, line3).attr({
				dx: 10,
				dy: 90,
				"fill": "#757575"
			}).appendTo(box);

			me.details.attr({
				x: x,
				y: y,
				"font-size": 14
			})
		});
		this.group.mouseout(function () {
			setTimeout(function () {
				me.details.clear();
			}, 500)
		});
	},
	bind_drag: function () {
		var me = this;

		this.group.dblclick(function (e) {
			var bar = me.group;
			var res = parseInt(bar.attr("data-editable"))
			res = 1 - res;
			bar.attr("data-editable", res);

			if(res){
				var rect = bar.select('rect');
				var rect_progress = bar.select('rect:nth-child(2)');
				var x = +rect.attr("x") + +rect.attr("width");
				var y = +rect.attr("y") + +rect.attr("height")/2;
				var resizer = me.canvas.circle(x, y, 5).attr("style", "cursor: e-resize;")
				bar.append(resizer);

				resizer.drag(function (dx, dy, posx, posy) {
					var width = +rect.attr("x")
					resizer.attr({
						cx: posx
					})
					rect.attr({
						width: posx - width
					})
					rect_progress.attr({
						width: (posx - width) * (me.task.progress/100)
					})
				}, function () {}, function () {
					bar.select('circle').remove();
				})
			}
			else {
				bar.select('circle').remove();
			}
		})
	}
})
