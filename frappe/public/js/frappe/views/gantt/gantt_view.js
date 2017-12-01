frappe.provide('frappe.views');

frappe.views.GanttView = frappe.views.ListRenderer.extend({
	name: 'Gantt',
	prepare: function(values) {
		this.items = values;
		this.prepare_tasks();
		this.prepare_dom();
	},

	render_view: function(values) {
		var me = this;
		this.prepare(values);
		this.render_gantt();
	},

	set_defaults: function() {
		this._super();
		this.no_realtime = true;
		this.page_title = this.page_title + ' ' + __('Gantt');
	},

	init_settings: function() {
		this._super();
		this.field_map = frappe.views.calendar[this.doctype].field_map;
		this.order_by = this.order_by || this.field_map.start + ' asc';
	},

	prepare_dom: function() {
		this.wrapper.css('overflow', 'auto')
			.append('<svg class="gantt-container" width="20" height="20"></svg>')
	},

	render_gantt: function(tasks) {
		var me = this;
		this.gantt_view_mode = this.user_settings.gantt_view_mode || 'Day';
		var field_map = frappe.views.calendar[this.doctype].field_map;

		this.gantt = new Gantt(".gantt-container", this.tasks, {
			view_mode: this.gantt_view_mode,
			date_format: "YYYY-MM-DD",
			on_click: function (task) {
				frappe.set_route('Form', task.doctype, task.id);
			},
			on_date_change: function(task, start, end) {
				if(!me.can_write()) return;
				me.update_gantt_task(task, start, end);
			},
			on_progress_change: function(task, progress) {
				if(!me.can_write()) return;
				var progress_fieldname = 'progress';

				if($.isFunction(field_map.progress)) {
					progress_fieldname = null;
				} else if(field_map.progress) {
					progress_fieldname = field_map.progress;
				}

				if(progress_fieldname) {
					frappe.db.set_value(task.doctype, task.id,
						progress_fieldname, parseInt(progress));
				}
			},
			on_view_change: function(mode) {
				// save view mode
				frappe.model.user_settings.save(me.doctype, 'Gantt', {
					gantt_view_mode: mode
				});
			},
			custom_popup_html: function(task) {
				var item = me.get_item(task.id);

				var html =
					`<h5>${task.name}</h5>
					<p>${task._start.format('MMM D')} - ${task._end.format('MMM D')}</p>`;

				// custom html in doctype settings
				var custom = me.settings.gantt_custom_popup_html;
				if(custom && $.isFunction(custom)) {
					var ganttobj = task;
					html = custom(ganttobj, item);
				}
				return '<div class="details-container">' + html + '</div>';
			}
		});
		this.render_dropdown();
		this.set_colors();
	},

	render_dropdown: function() {
		var me = this;
		var view_modes = this.gantt.config.view_modes || [];
		var dropdown = "<div class='dropdown pull-right'>" +
			"<a class='text-muted dropdown-toggle' data-toggle='dropdown'>" +
			"<span class='dropdown-text'>"+__(this.gantt_view_mode)+"</span><i class='caret'></i></a>" +
			"<ul class='dropdown-menu'></ul>" +
			"</div>";

		// view modes (for translation) __("Day"), __("Week"), __("Month"),
		//__("Half Day"), __("Quarter Day")

		var dropdown_list = "";
		view_modes.forEach(function(view_mode) {
			dropdown_list += "<li>" +
				"<a class='option' data-value='" + view_mode + "'>" +
				__(view_mode) + "</a></li>";
		});
		var $dropdown = $(dropdown)
		$dropdown.find(".dropdown-menu").append(dropdown_list);
		me.list_view.$page
			.find(`[data-list-renderer='Gantt'] > .list-row-right`)
			.css("margin-right", "15px").html($dropdown)
		$dropdown.on("click", ".option", function() {
			var mode = $(this).data('value');
			me.gantt.change_view_mode(mode);
			$dropdown.find(".dropdown-text").text(mode);
		});
	},

	set_colors: function() {
		const classes = this.tasks
			.map(t => t.custom_class)
			.filter(c => c && c.startsWith('color-'));

		let style = classes.map(c => {
			const class_name = c.replace('#', '');
			const bar_color = '#' + c.substr(6);
			const progress_color = frappe.ui.color.get_contrast_color(bar_color);
			return `
				.gantt .bar-wrapper.${class_name} .bar {
					fill: ${bar_color};
				}
				.gantt .bar-wrapper.${class_name} .bar-progress {
					fill: ${progress_color};
				}
			`;
		}).join("");

		style = `<style>${style}</style>`;

		this.wrapper.prepend(style);
	},

	prepare_tasks: function() {
		var me = this;
		var meta = frappe.get_meta(this.doctype);
		var field_map = frappe.views.calendar[this.doctype].field_map;
		this.tasks = this.items.map(function(item) {
			// set progress
			var progress = 0;
			if(field_map.progress && $.isFunction(field_map.progress)) {
				progress = field_map.progress(item);
			} else if(field_map.progress) {
				progress = item[field_map.progress]
			}

			// title
			if(meta.title_field) {
				var label = $.format("{0} ({1})", [item[meta.title_field], item.name]);
			} else {
				var label = item[field_map.title];
			}

			var r = {
				start: item[field_map.start],
				end: item[field_map.end],
				name: label,
				id: item[field_map.id || 'name'],
				doctype: me.doctype,
				progress: progress,
				dependencies: item.depends_on_tasks || ""
			};

			if(item.color && frappe.ui.color.validate_hex(item.color)) {
				r['custom_class'] = 'color-' + item.color.substr(1);
			}

			if(item.is_milestone) {
				r['custom_class'] = 'bar-milestone';
			}

			return r;
		});
	},
	get_item: function(name) {
		return this.items.find(function(item) {
			return item.name === name;
		});
	},
	update_gantt_task: function(task, start, end) {
		var me = this;
		if(me.gantt.updating_task) {
			setTimeout(me.update_gantt_task.bind(me, task, start, end), 200)
			return;
		}
		me.gantt.updating_task = true;

		var field_map = frappe.views.calendar[this.doctype].field_map;
		frappe.call({
			method: 'frappe.desk.gantt.update_task',
			args: {
				args: {
					doctype: task.doctype,
					name: task.id,
					start: start.format('YYYY-MM-DD'),
					end: end.format('YYYY-MM-DD')
				},
				field_map: field_map
			},
			callback: function() {
				me.gantt.updating_task = false;
				frappe.show_alert({message:__("Saved"), indicator: 'green'}, 1);
			}
		});
	},
	get_header_html: function() {
		return frappe.render_template('list_item_row_head', { main: '', list: this });
	},
	refresh: function(values) {
		this.prepare(values);
		this.render();
	},
	can_write: function() {
		if(frappe.model.can_write(this.doctype)) {
			return true;
		} else {
			// reset gantt state
			this.gantt.change_view_mode(this.gantt_view_mode);
			frappe.show_alert({message: __("Not permitted"), indicator: 'red'}, 1);
			return false;
		}
	},
	set_columns: function() {},
	required_libs: [
		"assets/frappe/js/lib/snap.svg-min.js",
		"assets/frappe/js/lib/frappe-gantt/frappe-gantt.js"
	]
});