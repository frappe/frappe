frappe.provide("frappe.views");

frappe.views.GanttView = class GanttView extends frappe.views.ListView {
	get view_name() {
		return "Gantt";
	}

	setup_defaults() {
		return super.setup_defaults().then(() => {
			this.page_title = this.page_title + " " + __("Gantt");
			this.calendar_settings = frappe.views.calendar[this.doctype] || {};

			if (typeof this.calendar_settings.gantt == "object") {
				Object.assign(this.calendar_settings, this.calendar_settings.gantt);
			}

			if (this.calendar_settings.order_by) {
				this.sort_by = this.calendar_settings.order_by;
				this.sort_order = "asc";
			} else {
				this.sort_by =
					this.view_user_settings.sort_by || this.calendar_settings.field_map.start;
				this.sort_order = this.view_user_settings.sort_order || "asc";
			}
		});
	}

	setup_view() {}

	prepare_data(data) {
		super.prepare_data(data);
		this.prepare_tasks();
	}

	prepare_tasks() {
		var me = this;
		var meta = this.meta;
		var field_map = this.calendar_settings.field_map;

		this.tasks = this.data.map(function (item) {
			// set progress
			var progress = 0;
			if (field_map.progress && $.isFunction(field_map.progress)) {
				progress = field_map.progress(item);
			} else if (field_map.progress) {
				progress = item[field_map.progress];
			}

			// title
			var label;
			if (meta.title_field) {
				label = item.progress
					? __("{0} ({1}) - {2}%", [item[meta.title_field], item.name, item.progress])
					: __("{0} ({1})", [item[meta.title_field], item.name]);
			} else {
				label = item[field_map.title];
			}

			var r = {
				start: item[field_map.start],
				end: item[field_map.end],
				name: label,
				id: item[field_map.id || "name"],
				doctype: me.doctype,
				progress: progress,
				dependencies: item.depends_on_tasks || "",
			};

			if (item.color && frappe.ui.color.validate_hex(item.color)) {
				r["custom_class"] = "color-" + item.color.substr(1);
			}

			if (item.is_milestone) {
				r["custom_class"] = "bar-milestone";
			}

			return r;
		});
	}

	render() {
		this.load_lib.then(() => {
			this.render_gantt();
		});
	}

	render_header() {}

	render_gantt() {
		const me = this;
		const gantt_view_mode = this.view_user_settings.gantt_view_mode || "Day";
		const field_map = this.calendar_settings.field_map;
		const date_format = "YYYY-MM-DD HH:mm";

		this.$result.empty();
		this.$result.addClass("gantt-modern");

		this.gantt = new Gantt(this.$result[0], this.tasks, {
			bar_height: 30,
			bar_corner_radius: 3,
			column_width: null,
			date_format: date_format,
			upper_header_height: 45,
			lower_header_height: 30,
			view_mode: gantt_view_mode,
			popup_on: 'hover',
			readonly: !me.can_write,
			scroll_to: 'start',
			today_button: true,
			view_mode_select: false,
			infinite_padding: false,
			padding: 18,
			container_height: 'auto',
			popup: (ctx) => {
				var item = me.get_item(ctx.task.id);
				
				ctx.set_title(ctx.task.name);
				
				const start_date = moment(ctx.task._start).format("MMM D");
				const end_date = moment(ctx.task._end).subtract(1, 'second').format("MMM D");
				ctx.set_subtitle(`${start_date} - ${end_date}`);
				
				var custom = me.settings.gantt_custom_popup_html;
				if (custom && $.isFunction(custom)) {
					var details = custom(ctx.task, item);
					ctx.set_details(details);
				} else {
					ctx.set_details(`Progress: ${Math.floor(ctx.task.progress)}%`);
				}
			},
			on_click: (task) => {
				frappe.set_route("Form", task.doctype, task.id);
			},
			on_date_change: (task, start, end) => {
				if (!me.can_write) return;
				frappe.db.set_value(task.doctype, task.id, {
					[field_map.start]: moment(start).format("YYYY-MM-DD"),
					[field_map.end]: moment(end).format("YYYY-MM-DD"),
				});
			},
			on_progress_change: (task, progress) => {
				if (!me.can_write) return;
				var progress_fieldname = "progress";

				if ($.isFunction(field_map.progress)) {
					progress_fieldname = null;
				} else if (field_map.progress) {
					progress_fieldname = field_map.progress;
				}

				if (progress_fieldname) {
					frappe.db.set_value(task.doctype, task.id, {
						[progress_fieldname]: parseInt(progress),
					});
				}
			},
			on_view_change: (mode) => {
				const mode_name = typeof mode === 'object' ? mode.name : mode;
				me.save_view_user_settings({
					gantt_view_mode: mode_name,
				});
			},
		});
		
		this.$result.css({
			'overflow': 'auto',
			'max-width': '100%',
			'position': 'relative'
		});
		
		this.setup_view_mode_buttons();
		this.set_colors();
		
		this.setup_scroll_handling();
	}

	setup_scroll_handling() {
		const $container = this.$result.find('.gantt-container');
		if ($container.length) {
			$container.css({
				'overflow-x': 'auto',
				'overflow-y': 'visible',
				'max-width': '100%'
			});
			
			let scrollTimeout;
			$container.on('scroll', () => {
				clearTimeout(scrollTimeout);
				scrollTimeout = setTimeout(() => {
					// Any additional scroll handling can go here
				}, 50);
			});
		}
	}

	setup_view_mode_buttons() {
		let $btn_group = this.$paging_area.find(".gantt-view-mode");
		if ($btn_group.length > 0) return;

		const view_modes = this.gantt.options.view_modes.map(vm => vm.name) || [];
		const active_class = (view_mode) => (this.gantt.options.view_mode === view_mode ? "btn-info" : "");
		const html = `<div class="btn-group gantt-view-mode">
				${view_modes
					.map(
						(value) => `<button type="button"
						class="btn btn-default btn-sm btn-view-mode ${active_class(value)}"
						data-value="${value}">
						${__(value)}
					</button>`
					)
					.join("")}
			</div>`;

		this.$paging_area.find(".level-left").append(html);

		const change_view_mode = (value) =>
			setTimeout(() => this.gantt.change_view_mode(value, false), 0);

		this.$paging_area.on("click", ".btn-view-mode", (e) => {
			const $btn = $(e.currentTarget);
			this.$paging_area.find(".btn-view-mode").removeClass("btn-info");
			$btn.addClass("btn-info");

			const value = $btn.data().value;
			change_view_mode(value);
		});
	}

	set_colors() {
		const classes = this.tasks
			.map((t) => t.custom_class)
			.filter((c) => c && c.startsWith("color-"));

		let style = classes
			.map((c) => {
				const class_name = c.replace("#", "");
				const bar_color = "#" + c.substr(6);
				const progress_color = frappe.ui.color.get_contrast_color(bar_color);
				return `
				.gantt .bar-wrapper.${class_name} .bar {
					fill: ${bar_color};
				}
				.gantt .bar-wrapper.${class_name} .bar-progress {
					fill: ${progress_color};
				}
			`;
			})
			.join("");

		style = `<style>${style}</style>`;
		this.$result.prepend(style);
	}

	get_item(name) {
		return this.data.find((item) => item.name === name);
	}

	get required_libs() {
		return [
			"assets/frappe/node_modules/frappe-gantt/dist/frappe-gantt.css",
			"assets/frappe/node_modules/frappe-gantt/dist/frappe-gantt.umd.js",
		];
	}
};
