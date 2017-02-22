frappe.provide('frappe.views');

frappe.views.GanttView = frappe.views.ListRenderer.extend({
	prepare: function(values) {
		this.items = values.map(this.prepare_data.bind(this));
		this.prepare_tasks();
		this.prepare_dom();
	},

	render_view: function(values, wrapper) {
		var me = this;
		this.load_lib(function() {
			me.prepare(values);
			me.render_gantt();
		});
	},

	prepare_meta: function() {
		this._super();
		this.no_realtime = true;
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
				// will be cached in __UserSettings table in db
				me.user_settings.gantt_view_mode = mode;
			},
			custom_popup_html: function(task) {
				var item = me.get_item(task.id);
				console.log(item, task)
				var list_item_subject = frappe.render_template('list_item_subject', item);
				var html = '<div class="heading">'+
					list_item_subject +'</div>';

				// custom html in {doctype}_list.js
				var custom = me.settings.gantt_custom_popup_html;
				if(custom) {
					html = custom(item, html);
				}

				return '<div class="details-container">'+ html +'</div>';
			}
		});
		this.render_dropdown();
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
		$dropdown.find(".dropdown-menu")
				.append(dropdown_list);
		me.list_view.$page.find(".list-row-right").css("margin-top", 0).html($dropdown)
		$dropdown.on("click", ".option", function() {
			var mode = $(this).data('value');
			me.gantt.change_view_mode(mode);
			$dropdown.find(".dropdown-text").text(mode);
		});
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

			return {
				start: item[field_map.start],
				end: item[field_map.end],
				name: label,
				id: item[field_map.id || 'name'],
				doctype: me.doctype,
				progress: progress,
				dependencies: item.depends_on_tasks || ""
			};
		});
	},
	get_item: function(name) {
		return this.items.find(function(item) {
			return item.name === name;
		});
	},
	load_lib: function(callback) {
		frappe.require([
				"assets/frappe/js/lib/snap.svg-min.js",
				"assets/frappe/js/lib/frappe-gantt/frappe-gantt.js"
			], callback);
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
				show_alert({message:__("Saved"), indicator: 'green'}, 1);
			}
		});
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
			show_alert({message: __("Not permitted"), indicator: 'red'}, 1);
			return false;
		}
	},
	set_columns: function() {}
})