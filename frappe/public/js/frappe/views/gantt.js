/*

Opts:
	parent_selector: [reqd]
	label_width: default 200
	step: 24 // no of hours
	column_width: 15 // pixels
	date_format: 'YYYY-MM-DD'
	bar.height: 26
	arrow.curve: 15

*/

var Gantt = Class.extend({
	init: function(opts) {
		this.opts = opts;
		this.events = this.opts.events;
		this.set_defaults();
		this.prepare();
		this.render();
	},
	set_defaults: function() {
		var defaults = {
			label_width: 38,
			header_height: 50,
			column_width: 30,
			step: 24,
			valid_view_modes: [
				"Quarter Day",
				"Half Day",
				"Day",
				"Week",
				"Month"
			],
			bar: {
				height: 20
			},
			arrow: {
				curve: 5
			},
			view_mode: 'Day',
			padding: 18,
			date_format: 'DD-MM-YYYY'
		};
		for(var key in defaults) {
			if(defaults.hasOwnProperty(key)) {
				if(!this.opts[key]) this.opts[key] = defaults[key];
			}
		}

		this._bars = [];
		this._arrows = [];
		this.groups = {};

		//prepare tasks
		var me = this;
		this.tasks = this.opts.tasks.map(function(task, i) {
			// momentify
			task._start = moment(task.start, me.opts.date_format);
			task._end = moment(task.end, me.opts.date_format);
			//index
			task._index = i;
			//invalid dates
			if(!task.start || !task.end) {
				task._start = moment().startOf('day');
				task._end = moment().startOf('day').add(2, 'days');
				task.invalid = true;
			}
			return task;
		});
		//default view mode
		this.set_scale(this.opts.view_mode);
	},
	prepare: function() {
		//TODO: check for valid dates
		this.start = this.end = undefined;
		this.prepare_dates();
		this.render_canvas();
	},
	render: function() {
		this.clear();
		this.setup_groups();
		this.make_grid();
		this.make_dates();
		this.make_bars();
		this.make_arrows();
		this.set_arrows_on_bars();
		this.setup_events();
		this.set_width();
		this.set_scroll_position();
		this.bind();
	},
	bind: function() {
		this.bind_grid_click();
	},
	render_canvas: function() {
		this.canvas = Snap(this.opts.parent_selector);
		this.canvas.addClass("gantt");
	},
	clear: function () {
		this.canvas.clear();
		this._bars = [];
		this._arrows = [];
	},
	prepare_dates: function() {
		var me = this;
		this.tasks.forEach(function(task) {
			// set global start and end date
			if(!me.start || task._start < me.start) {
				me.start = task._start;
			}
			if(!me.end || task._end > me.end) {
				me.end = task._end;
			}
		});
		this.set_gantt_dates();
		this.setup_dates();
	},
	set_gantt_dates: function() {
		var me = this;
		if(me.view_is(['Quarter Day','Half Day'])) {
			me.start = me.start.clone().subtract(7, 'day');
			me.end = me.end.clone().add(7, 'day');
		} else if(me.view_is('Month')) {
			me.start = me.start.clone().startOf('year');
			me.end = me.end.clone().endOf('month').add(1, 'year');
		} else {
			me.start = me.start.clone().startOf('month').subtract(1, 'month');
			me.end = me.end.clone().endOf('month').add(1, 'month');
		}
	},
	setup_dates: function() {
		this.dates = [];
		var cur_date = null;
		while(cur_date === null || cur_date < this.end) {
			if(!cur_date) {
				cur_date = this.start.clone();
			} else {
				cur_date = this.view_is('Month') ?
					cur_date = cur_date.clone().add(1, 'month'):
					cur_date.clone().add(this.opts.step, 'hours');
			}
			this.dates.push(cur_date);
		}
	},
	setup_groups: function() {
		var me = this;
		// make group layers
		["grid", "date", "arrow",
		"progress", "bar", "details"].forEach(function(name) {
			me.groups[name] = me.canvas.group().attr({'id': name});
		});
	},
	get_view_modes: function() {
		return this.opts.valid_view_modes || [];
	},
	set_view_mode: function(mode) {
		this.set_scale(mode);
		this.prepare();
		this.render();
	},
	set_scale: function (scale) {
		this.view_mode = scale;

		//fire viewmode_change event
		this.events.on_viewmode_change(scale);
		if(scale === 'Day') {
			this.opts.step = 24;
			this.opts.column_width = 38;
		}
		else if(scale === 'Half Day') {
			this.opts.step = 24 / 2;
			this.opts.column_width = 38;
		}
		else if(scale === 'Quarter Day') {
			this.opts.step = 24 / 4;
			this.opts.column_width = 38;
		}
		else if(scale === 'Week') {
			this.opts.step = 24 * 7;
			this.opts.column_width = 140;
		}
		else if(scale === 'Month') {
			this.opts.step = 24 * 30;
			this.opts.column_width = 120;
		}
	},
	add_task: function(task) {
		task._index = this.tasks.length;
		this.tasks.push(task);
		this.prepare_dates();
	},
	set_width: function () {
		var cur_width = this.canvas.node.getBoundingClientRect().width;
		var actual_width = this.canvas.getBBox().width;
		if(cur_width < actual_width)
			this.canvas.attr("width", actual_width);
	},
	set_scroll_position: function() {
		var parent_element = document.querySelector(this.opts.parent_selector).parentElement; 
		if(!parent_element) return;
		var scroll_pos = this.get_min_date().diff(this.start, 'hours') /
			this.opts.step * this.opts.column_width;
		parent_element.scrollLeft = scroll_pos;
	},
	get_min_date: function() {
		return this.tasks.reduce(function(acc, curr) {
			return curr._start.isSameOrBefore(acc._start) ? curr : acc;
		})._start;
	},
	make_grid: function () {
		this.make_grid_background();
		this.make_grid_rows();
		this.make_grid_header();
		this.make_grid_ticks();
		this.make_grid_highlights();
	},
	make_grid_background: function () {
		var me = this;
		var grid_width = this.opts.label_width + this.dates.length * this.opts.column_width,
			grid_height = this.opts.header_height + this.opts.padding +
				(this.opts.bar.height + this.opts.padding) * this.tasks.length;

		this.canvas.rect(0,0, grid_width, grid_height)
			.addClass('grid-background')
			.appendTo(this.groups.grid);

		this.canvas.attr({
			// viewBox: "0 0 " + (x+10) + " " + (y+10),
			height: grid_height + me.opts.padding,
			width: "100%"
		});
	},
	make_grid_header: function () {
		var me = this;
		var header_width = this.opts.label_width + this.dates.length * this.opts.column_width,
			header_height = this.opts.header_height + 10;
		me.canvas.rect(0,0, header_width, header_height)
			.addClass('grid-header')
			.appendTo(me.groups.grid);
	},
	make_grid_rows: function () {
		var
		me = this,
		rows = me.canvas.group()
			.appendTo(me.groups.grid),
		lines = me.canvas.group()
			.appendTo(me.groups.grid),

		row_width = me.opts.label_width + me.dates.length * me.opts.column_width,
		row_height = me.opts.bar.height + me.opts.padding,
		row_y = me.opts.header_height + me.opts.padding/2;

		this.tasks.forEach(function (task, i) {
			me.canvas.rect(0, row_y, row_width, row_height)
				.addClass("grid-row")
				.appendTo(rows);

			me.canvas.line(0, row_y + row_height, row_width, row_y + row_height)
				.addClass('row-line')
				.appendTo(lines);
			row_y += me.opts.bar.height + me.opts.padding;
		});
	},
	make_grid_ticks: function () {
		var me = this;
		var tick_x = me.opts.label_width;
		var tick_y = me.opts.header_height + me.opts.padding/2;
		var tick_height = (me.opts.bar.height + me.opts.padding) * me.tasks.length;

		this.dates.forEach(function(date) {
			var tick_class = 'tick';
			//thick tick for monday
			if(me.view_mode === 'Day' && date.day() === 1) {
				tick_class += ' thick';
			}
			//thick tick for first week
			if(me.view_mode === 'Week' && date.date() >= 1 && date.date() < 8) {
				tick_class += ' thick';
			}
			//thick ticks for quarters
			if(me.view_mode === 'Month' && date.month() % 3 === 0) {
				tick_class += ' thick';
			}

			me.canvas.path(Snap.format("M {x} {y} v {height}", {
				x: tick_x,
				y: tick_y,
				height: tick_height
			}))
			.addClass(tick_class)
			.appendTo(me.groups.grid);

			if(me.view_mode === 'Month') {
				tick_x += date.daysInMonth() * me.opts.column_width/30;
			} else {
				tick_x += me.opts.column_width;
			}
		});
	},
	make_grid_highlights: function() {
		var me = this;
		//highlight today's date
		if(me.view_mode === 'Day') {
			var x = me.opts.label_width +
				moment().startOf('day').diff(me.start, 'hours') / me.opts.step *
				me.opts.column_width,
			y = 0,
			width = me.opts.column_width,
			height = (me.opts.bar.height + me.opts.padding) * me.tasks.length +
				me.opts.header_height + me.opts.padding/2;
			me.canvas.rect(x, y, width, height)
				.addClass('today-highlight')
				.appendTo(me.groups.grid);
		}
	},
	make_dates: function() {
		var me = this;

		this.dates.forEach(function(date, i) {
			var primary_text = '';
			var secondary_text = '';
			if(i===0) {
				primary_text = me.get_date_text(date, "primary");
				secondary_text = me.get_date_text(date);
			} else {
				if(me.view_mode === 'Day') {
					primary_text = date.date() !== me.dates[i-1].date() ?
						me.get_date_text(date, "primary") : "";
					secondary_text = date.month() !== me.dates[i-1].month() ?
						me.get_date_text(date) : "";
				}
				else if(me.view_mode === 'Quarter Day') {
					primary_text = me.get_date_text(date, "primary");
					secondary_text = date.date() !== me.dates[i-1].date() ?
						me.get_date_text(date) : "";
				}
				else if(me.view_mode === 'Half Day') {
					primary_text = me.get_date_text(date, "primary");
					secondary_text = date.date() !== me.dates[i-1].date() ?
						me.get_date_text(date) : "";
				}
				else if(me.view_mode === 'Week') {
					primary_text = me.get_date_text(date, "primary");
					secondary_text = date.month() !== me.dates[i-1].month() ?
						me.get_date_text(date) : "";
				}
				else if(me.view_mode === 'Month') {
					primary_text = me.get_date_text(date, "primary");
					secondary_text = date.year() !== me.dates[i-1].year() ?
						me.get_date_text(date) : "";
				}
			}
			var primary_text_x = me.opts.label_width + (i * me.opts.column_width),
				primary_text_y = me.opts.header_height,
				secondary_text_x = me.opts.label_width + (i * me.opts.column_width),
				secondary_text_y = me.opts.header_height - 25;

			if(me.view_mode === 'Month') {
				primary_text_x += (date.daysInMonth() * me.opts.column_width/30)/2;
				secondary_text_x += (me.opts.column_width * 12)/2;
			}
			if(me.view_mode === 'Week') {
				primary_text_x += me.opts.column_width/2;
				secondary_text_x += (me.opts.column_width * 4)/2;
			}
			if(me.view_mode === 'Day') {
				primary_text_x += me.opts.column_width/2;
				secondary_text_x += (me.opts.column_width * 30)/2;
			}
			if(me.view_mode === 'Quarter Day') {
				secondary_text_x += (me.opts.column_width * 4)/2;
			}
			if(me.view_mode === 'Half Day') {
				secondary_text_x += (me.opts.column_width * 2)/2;
			}

			me.canvas.text(primary_text_x, primary_text_y, primary_text)
				.addClass('primary-text')
				.appendTo(me.groups.date);
			if(secondary_text) {
				var $secondary_text = me.canvas.text(secondary_text_x, secondary_text_y, secondary_text)
					.addClass('secondary-text')
					.appendTo(me.groups.date);

				if($secondary_text.getBBox().x2 > me.groups.grid.getBBox().width) {
					$secondary_text.remove();
				}
			}
		});
	},
	get_date_text: function(date, primary) {
		var scale = this.view_mode;
		var text = "";
		if(scale === 'Day') {
			text = (primary) ? date.format('D') : date.format('MMMM');
		}
		else if(scale === 'Quarter Day' || scale === 'Half Day') {
			text = (primary) ? date.format('HH') : date.format('D MMM');
		}
		else if(scale === 'Week') {
			text = (primary) ? "Week " + date.format('W') : date.format('MMMM');
		}
		else if(scale === 'Month') {
			text = (primary) ? date.format('MMMM') : date.format('YYYY');
		}
		return text;
	},
	make_arrows: function () {
		var me = this;
		this.tasks.forEach(function (task) {
			if(task.dependent) {
				var dependents = task.dependent.split(',');
				dependents.forEach(function (task_dependent) {
					var dependent = me.get_task(task_dependent.trim());
					if(!dependent) return;
					var arrow = new Arrow({
						gantt: me,
						from_task: me._bars[dependent._index],
						to_task: me._bars[task._index]
					});
					me.groups.arrow.add(arrow.element);
					me._arrows.push(arrow);
				});
			}
		});
	},

	make_label: function () {
		var me = this;
		var label_x = me.opts.label_width - me.opts.padding,
			label_y = me.opts.header_height + me.opts.bar.height/2 + me.opts.padding;

		this.tasks.forEach(function (task) {
			me.canvas.text(label_x, label_y, task.name).appendTo(me.groups.label);
			label_y += me.opts.bar.height + me.opts.padding;
		});

		me.groups.label.attr({
			"text-anchor": "end",
			"dominant-baseline": "central"
		});
	},
	make_bars: function () {
		var me = this;

		this.tasks.forEach(function (task, i) {
			var bar = new Bar({
				canvas: me.canvas,
				task: task,
				gantt: {
					offset: me.opts.label_width,
					unit_width: me.opts.column_width,
					step: me.opts.step,
					start: me.start,
					header_height: me.opts.header_height,
					padding: me.opts.padding,
					view_mode: me.view_mode
				},
				popover_group: me.groups.details
			});
			me._bars.push(bar);
			me.groups.bar.add(bar.group);
		});
	},
	set_arrows_on_bars: function() {
		var me = this;
		this._bars.forEach(function(bar) {
			bar.arrows = me._arrows.filter(function(arrow) {
				if(arrow.from_task.task.id === bar.task.id || arrow.to_task.task.id === bar.task.id)
					return arrow;
			});
		});
	},
	setup_events: function() {
		var me = this;
		this._bars.forEach(function(bar) {
			bar.events.on_date_change = me.events.bar_on_date_change;
			bar.events.on_progress_change = me.events.bar_on_progress_change;
			bar.click(me.events.bar_on_click);
		});
	},
	bind_grid_click: function() {
		var me = this;
		this.groups.grid.click(function() {
			me.canvas.selectAll('.bar-wrapper').forEach(function(el) {
				el.removeClass('active');
			});
		});
	},
	view_is: function(modes) {
		var me = this;
		if (typeof modes === 'string') {
			return me.view_mode === modes;
		} else {
			modes.reduce(function(acc, curr) {
				return (me.view_mode === curr) || acc
			}, false);
			// for (var i = 0; i < modes.length; i++) {
			// 	if(me.gantt.view_mode === modes[i]) return true;
			// }
			// return false;
		}
	},
	get_task: function (id) {
		var result = null;
		this.tasks.forEach(function (task) {
			if (task.id === id){
				result = task;
			}
		});
		return result;
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
		for(var key in opts) {
			if(opts.hasOwnProperty(key))
				this[key] = opts[key];
		}
		this.set_defaults();
		this.prepare();
		this.draw();
		this.bind();
		this.action_completed = false;
	},
	set_defaults: function () {
		var defaults = {
			height: 20,
			corner_radius: 3,
			events: {}
		};
		for(var key in defaults) {
			if(defaults.hasOwnProperty(key))
				if(!this[key]) this[key] = defaults[key];
		}
	},
	prepare: function () {
		this.prepare_values();
		this.prepare_plugins();
	},
	prepare_values: function() {
		if(!this.task.start || !this.task.end){
			this.invalid = true;
		}
		this.x = this.compute_x();
		this.y = this.compute_y();
		this.duration = (this.task._end.diff(this.task._start, 'hours') + 24)/this.gantt.step;
		this.width = this.gantt.unit_width * this.duration;
		this.progress_width = this.gantt.unit_width * this.duration * (this.task.progress/100) || 0;
		this.group = this.canvas.group().addClass('bar-wrapper');
		this.bar_group = this.canvas.group().addClass('bar-group').appendTo(this.group);
		this.handle_group = this.canvas.group().addClass('handle-group').appendTo(this.group);
	},
	prepare_plugins: function() {
		this.filters = {};
		Snap.plugin(function (Snap, Element, Paper, global, Fragment) {
			Element.prototype.get = function (attr) {
				return +this.attr(attr);
			};
			Element.prototype.getX = function () {
				return this.get("x");
			};
			Element.prototype.getEndX = function () {
				return this.getX() + this.getWidth();
			};
			Element.prototype.getY = function () {
				return this.get("y");
			};
			Element.prototype.getWidth = function () {
				return this.get("width");
			};
		});
	},
	draw: function () {
		this.draw_bar();
		this.draw_progress_bar();
		this.draw_label();
		this.draw_resize_handles();
	},
	draw_bar: function() {
		this.$bar = this.canvas.rect(this.x, this.y,
			this.width, this.height,
			this.corner_radius, this.corner_radius)
			.addClass("bar")
			.appendTo(this.bar_group);
		if(this.invalid) {
			this.$bar.addClass('bar-invalid');
		}
	},
	draw_progress_bar: function() {
		if(this.invalid) return;
		this.$bar_progress = this.canvas.rect(this.x, this.y,
			this.progress_width, this.height,
			this.corner_radius, this.corner_radius)
			.addClass("bar-progress")
			.appendTo(this.bar_group);
	},
	draw_label: function() {
		this.canvas.text(this.x + this.width/2,
				this.y + this.height/2,
				this.task.name)
			.addClass("bar-label")
			.appendTo(this.bar_group);
		this.update_label_position();
	},
	draw_resize_handles: function() {
		if(this.invalid) return;
		var bar = this.$bar,
		bar_progress = this.$bar_progress;

		this.canvas.rect(bar.getX() + bar.getWidth() - 9, bar.getY() + 1,
			8, this.height - 2, this.corner_radius, this.corner_radius)
				.addClass('handle right')
				.appendTo(this.handle_group);
		this.canvas.rect(bar.getX() + 1, bar.getY() + 1,
			8, this.height - 2, this.corner_radius, this.corner_radius)
			.addClass('handle left')
			.appendTo(this.handle_group);

		if(this.task.progress && this.task.progress < 100) {
			this.canvas.polygon(
				bar_progress.getEndX() - 5, bar_progress.getY() + bar_progress.get("height"),
				bar_progress.getEndX() + 5, bar_progress.getY() + bar_progress.get("height"),
				bar_progress.getEndX(), bar_progress.getY() + bar_progress.get("height") - 8.66
			)
			.addClass('handle progress')
			.appendTo(this.handle_group)
		}
	},
	draw_invalid_bar: function() {
		var x = this.gantt.offset +
			(moment().startOf('day').diff(this.gantt.start, 'hours') /
			this.gantt.step *
			this.gantt.unit_width);

		this.canvas.rect(x, this.y,
			this.gantt.unit_width*2, this.height,
			this.corner_radius, this.corner_radius)
			.addClass("bar-invalid")
			.appendTo(this.bar_group);
			//continue here
		this.canvas.text(x + this.gantt.unit_width,
				this.y + this.height/2,
				'Dates not set')
			.addClass("bar-label big")
			.appendTo(this.bar_group);
	},
	bind: function () {
		if(this.invalid) return;
		this.show_details();
		this.bind_resize();
		this.bind_drag();
		this.bind_resize_progress();
	},
	show_details: function () {
		var me = this;

		var details_box = me.popover_group.select('.details-wrapper');
		if(!details_box) {
			details_box = me.canvas.group().addClass('details-wrapper');
			details_box.appendTo(me.popover_group);
			me.canvas.rect(0, 0, 0, 110, 2, 2)
				.addClass('details-container')
				.appendTo(details_box);
			me.canvas.text(0, 0, "")
				.attr({ dx: 10, dy: 30 })
				.addClass('details-heading')
				.appendTo(details_box);
			me.canvas.text(0, 0, "")
				.attr({ dx: 10, dy: 65 })
				.addClass('details-body')
				.appendTo(details_box);
			me.canvas.text(0, 0, "")
				.attr({ dx: 10, dy: 90 })
				.addClass('details-body')
				.appendTo(details_box);
		}


		this.group.mouseover(function (e, x, y) {
			me.popover_group.removeClass('hide');

			var pos = me.get_details_position();
			details_box.transform("t" + pos.x + "," + pos.y);

			var heading = me.task.name + ": " +
				me.task._start.format("MMM D") + " - " +
				me.task._end.format("MMM D");

			var $heading = me.popover_group.select('.details-heading');
			$heading.attr('text', heading);

			var bbox = $heading.getBBox();
			details_box.select('.details-container').attr({
				width: bbox.width + 20
			});

			var body1 = "Duration: " +
				me.task._end.diff(me.task._start, 'days') + " days";
			var body2 = me.task.progress ?
				"Progress: " + me.task.progress + "%" : "";

			var $body = me.popover_group.selectAll('.details-body');
			$body[0].attr('text', body1);
			$body[1].attr('text', body2);
		});
		this.group.mouseout(function () {
			setTimeout(function () {
				me.popover_group.addClass('hide');
			}, 500);
		});
	},
	get_details_position: function () {
		return {
			x: this.$bar.getEndX() + 2,
			y: this.$bar.getY() - 10
		};
	},
	bind_resize: function() {
		var me = this;
		var bar = this.$bar;
		var handle = me.get_handles();
		handle.right.drag(onmove_right, onstart, onstop_right);
		handle.left.drag(onmove_left, onstart, onstop_left);

		function onstart() {
			bar.ox = bar.getX();
			bar.oy = bar.getY();
			bar.owidth = bar.getWidth();
			this.ox = this.getX();
			this.oy = this.getY();
			bar.finaldx = 0;
		}

		function onmove_right(dx, dy) {
			bar.finaldx = me.get_snap_position(dx);
			me.update_bar_position(null, bar.owidth + bar.finaldx);
		}
		function onstop_right() {
			if(bar.finaldx) me.date_changed();
			me.set_action_completed();
		}

		function onmove_left(dx, dy) {
			bar.finaldx = me.get_snap_position(dx);
			me.update_bar_position(bar.ox + bar.finaldx, bar.owidth - bar.finaldx);
		}
		function onstop_left() {
			if(bar.finaldx) me.date_changed();
			me.set_action_completed();
		}
	},
	get_handles: function() {
		var me = this;
		return {
			left: me.handle_group.select('.handle.left'),
			right: me.handle_group.select('.handle.right')
		};
	},
	bind_drag: function() {
		var me = this;
		var bar = this.$bar;
		this.bar_group.drag(onmove, onstart, onstop);

		function onmove(dx, dy) {
			bar.finaldx = me.get_snap_position(dx);
			me.update_bar_position(bar.ox + bar.finaldx);
		}
		function onstop() {
			if(!bar.finaldx) return;
			me.date_changed();
			me.set_action_completed();
		}
		function onstart() {
			bar.ox = bar.getX();
			bar.finaldx = 0;
		}
	},
	bind_resize_progress: function() {
		var me = this;
		var bar = this.$bar;
		var bar_progress = this.$bar_progress;
		var handle = me.group.select('.handle.progress');
		handle && handle.drag(onmove, onstart, onstop);

		function onmove(dx, dy) {
			if(dx > bar_progress.max_dx) {
				dx = bar_progress.max_dx;
			}
			if(dx < bar_progress.min_dx) {
				dx = bar_progress.min_dx;
			}

			bar_progress.attr("width", bar_progress.owidth + dx);
			handle.transform("t"+dx+",0");
			bar_progress.finaldx = dx;
		}
		function onstop() {
			if(!bar_progress.finaldx) return;
			me.progress_changed();
			me.set_action_completed();
		}
		function onstart() {
			bar_progress.finaldx = 0;
			bar_progress.owidth = bar_progress.getWidth();
			bar_progress.min_dx = -bar_progress.getWidth();
			bar_progress.max_dx = bar.getWidth() - bar_progress.getWidth();
		}
	},
	view_is: function(modes) {
		var me = this;
		if (typeof modes === 'string') {
			return me.gantt.view_mode === modes;
		} else {
			for (var i = 0; i < modes.length; i++) {
				if(me.gantt.view_mode === modes[i]) return true;
			}
			return false;
		}
	},
	update_bar_position: function(x, width) {
		var bar = this.$bar;
		if(x) this.update_attr(bar, "x", x);
		if(width) this.update_attr(bar, "width", width);
		this.update_label_position();
		this.update_handle_position();
		this.update_progressbar_position();
		this.update_arrow_position();
		this.update_details_position();
	},
	click: function(callback) {
		var me = this;
		this.group.click(function() {
			if(me.action_completed) {
				// just finished a move action, wait for a few seconds
				return;
			}
			if(me.group.hasClass('active')) {
				callback(me.task);
			}
			me.unselect_all();
			me.group.toggleClass('active');
		});
	},
	date_changed: function() {
		this.events.on_date_change &&
		this.events.on_date_change(
			this.task,
			this.compute_start_date(),
			this.compute_end_date()
		);
	},
	progress_changed: function() {
		this.events.on_progress_change &&
		this.events.on_progress_change(
			this.task,
			this.compute_progress()
		);
	},
	set_action_completed: function() {
		var me = this;
		this.action_completed = true;
		setTimeout(function() { me.action_completed = false; }, 2000);
	},
	compute_date: function(x) {
		var shift = (x - this.compute_x())/this.gantt.unit_width;
		var date = this.task._start.clone().add(this.gantt.step*shift, 'hours');
		return date;
	},
	compute_start_date: function() {
		var bar = this.$bar,
			shift = (bar.getX() - this.compute_x()) / this.gantt.unit_width,
			new_start_date = this.task._start.clone().add(this.gantt.step*shift, 'hours');
		return new_start_date;
	},
	compute_end_date: function() {
		var bar = this.$bar,
			og_x = this.compute_x() + this.duration * this.gantt.unit_width,
			final_x = bar.getEndX(),
			shift = (final_x - og_x) / this.gantt.unit_width,
			new_end_date = this.task._end.clone().add(this.gantt.step*shift, 'hours');
		return new_end_date;
	},
	compute_progress: function() {
		return this.$bar_progress.getWidth() / this.$bar.getWidth() * 100;
	},
	compute_x: function() {
		var x = this.gantt.offset +
			(this.task._start.diff(this.gantt.start, 'hours')/this.gantt.step *
			 this.gantt.unit_width);
		if(this.view_is('Month')) {
			x = this.gantt.offset +
				this.task._start.diff(this.gantt.start, 'days') *
				this.gantt.unit_width/30;
		}
		return x;
	},
	compute_y: function() {
		return this.gantt.header_height + this.gantt.padding +
			this.task._index * (this.height + this.gantt.padding);
	},
	get_snap_position: function(dx) {
		var me = this;
		var odx = dx, rem, position;

		if (me.view_is('Week')) {
			rem = dx % (me.gantt.unit_width/7);
			position = odx - rem +
				((rem < me.gantt.unit_width/14) ? 0 : me.gantt.unit_width/7);
		} else if (me.view_is('Month')) {
			rem = dx % (me.gantt.unit_width/30);
			position = odx - rem +
				((rem < me.gantt.unit_width/60) ? 0 : me.gantt.unit_width/30);
		} else {
			rem = dx % me.gantt.unit_width;
			position =  odx - rem +
				((rem < me.gantt.unit_width/2) ? 0 : me.gantt.unit_width);
		}
		return position;
	},
	update_attr: function(element, attr, value) {
		value = +value;
		if(!isNaN(value)) {
			element.attr(attr, value);
		}
		return element;
	},
	update_progressbar_position: function() {
		this.$bar_progress.attr('x', this.$bar.getX());
		this.$bar_progress.attr('width', this.$bar.getWidth() * (this.task.progress/100));
	},
	update_label_position: function() {
		var bar = this.$bar,
		label = this.group.select('.bar-label');
		if(label.getBBox().width > bar.getWidth()){
			label.addClass('big').attr('x', bar.getX() + bar.getWidth() + 5);
		} else {
			label.removeClass('big').attr('x', bar.getX() + bar.getWidth()/2);
		}
	},
	update_handle_position: function() {
		var bar = this.$bar;
		this.handle_group.select(".handle.left").attr({
			"x": bar.getX() + 1,
		});
		this.handle_group.select(".handle.right").attr({
			"x": bar.getX() + bar.getWidth() - 9,
		});
	},
	update_arrow_position: function() {
		this.arrows.forEach(function(arrow) {
			arrow.update();
		});
	},
	update_details_position: function() {
		var details_box = this.popover_group.select('.details-wrapper');
		var pos = this.get_details_position();
		details_box && details_box.transform("t" + pos.x + "," + pos.y);
	},
	unselect_all: function() {
		this.canvas.selectAll('.bar-wrapper').forEach(function(el) {
			el.removeClass('active');
		});
	}
});

/*
	Class: Arrow
	from_task ---> to_task

	Opts:
		gantt (Gantt object)
		from_task (Bar object)
		to_task (Bar object)
*/

var Arrow = Class.extend({
	init: function (opts) {
		for(var key in opts) {
			if(opts.hasOwnProperty(key))
				this[key] = opts[key];
		}
		this.prepare();
		this.draw();
	},
	prepare: function() {
		var gantt = this.gantt,
		from_task = this.from_task,
		to_task = this.to_task;

		this.start_x =from_task.$bar.getX() + from_task.$bar.getWidth()/2;

		while(to_task.$bar.getX() < this.start_x + gantt.opts.padding &&
			this.start_x > from_task.$bar.getX() + gantt.opts.padding)
		{
			this.start_x -= 10;
		}

		this.start_y = gantt.opts.header_height + gantt.opts.bar.height +
			(gantt.opts.padding + gantt.opts.bar.height) * from_task.task._index +
			gantt.opts.padding;

		this.end_x = to_task.$bar.getX() - gantt.opts.padding/2;
		this.end_y = gantt.opts.header_height + gantt.opts.bar.height/2 +
			(gantt.opts.padding + gantt.opts.bar.height) * to_task.task._index +
			gantt.opts.padding;

		var from_is_below_to = (from_task.task._index > to_task.task._index);
		this.curve = gantt.opts.arrow.curve;
		this.clockwise = from_is_below_to ? 1 : 0;
		this.curve_y = from_is_below_to ? -this.curve : this.curve;
		this.offset = from_is_below_to ?
			this.end_y + gantt.opts.arrow.curve:
			this.end_y - gantt.opts.arrow.curve;

		this.path =
			Snap.format("M {start_x} {start_y} V {offset} " +
				"a {curve} {curve} 0 0 {clockwise} {curve} {curve_y} " +
				"L {end_x} {end_y} m -5 -5 l 5 5 l -5 5",
			{
				start_x: this.start_x,
				start_y: this.start_y,
				end_x: this.end_x,
				end_y: this.end_y,
				offset: this.offset,
				curve: this.curve,
				clockwise: this.clockwise,
				curve_y: this.curve_y
			});

		if(to_task.$bar.getX() < from_task.$bar.getX() + gantt.opts.padding) {
			this.path =
				Snap.format("M {start_x} {start_y} v {down_1} " +
				"a {curve} {curve} 0 0 1 -{curve} {curve} H {left} " +
				"a {curve} {curve} 0 0 {clockwise} -{curve} {curve_y} V {down_2} " +
				"a {curve} {curve} 0 0 {clockwise} {curve} {curve_y} " +
				"L {end_x} {end_y} m -5 -5 l 5 5 l -5 5",
			{
				start_x: this.start_x,
				start_y: this.start_y,
				end_x: this.end_x,
				end_y: this.end_y,
				down_1: this.gantt.opts.padding/2 - this.curve,
				down_2: to_task.$bar.getY() + to_task.$bar.get('height')/2 - this.curve_y,
				left: to_task.$bar.getX() - gantt.opts.padding,
				offset: this.offset,
				curve: this.curve,
				clockwise: this.clockwise,
				curve_y: this.curve_y
			});
		}
	},
	draw: function() {
		this.element = this.gantt.canvas.path(this.path)
			.attr("data-from", this.from_task.task.id)
			.attr("data-to", this.to_task.task.id);
	},
	update: function() {
		this.prepare();
		this.element.attr('d', this.path);
	}
});