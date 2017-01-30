// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.views.doclistview');
frappe.provide('frappe.listviews');

cur_list = null;
frappe.views.ListFactory = frappe.views.Factory.extend({
	make: function(route) {
		var me = this,
			doctype = route[1];

		frappe.model.with_doctype(doctype, function() {
			if(locals["DocType"][doctype].issingle) {
				frappe.set_re_route("Form", doctype);
			} else {
				if(!frappe.views.doclistview[doctype]) {
					frappe.views.doclistview[doctype] = new frappe.views.DocListView({
						doctype: doctype,
						parent: me.make_page(true, "List/" + doctype)
					});
				} else {
					frappe.container.change_to(frappe.views.doclistview[doctype].page_name);
				}
				me.set_cur_list();
			}
		});
	},
	show: function() {
		this.set_module_breadcrumb();
		this._super();
		this.set_cur_list();
		cur_list && cur_list.refresh();
	},
	set_module_breadcrumb: function() {
		if(frappe.route_history.length > 1) {
			var prev_route = frappe.route_history[frappe.route_history.length-2];
			if(prev_route[0]==="modules") {
				var doctype = frappe.get_route()[1],
					module = prev_route[1];
				if(frappe.module_links[module] && in_list(frappe.module_links[module], doctype)) {
					// save the last page from the breadcrumb was accessed
					frappe.breadcrumbs.set_doctype_module(doctype, module);
				}
			}
		}
	},
	set_cur_list: function() {
		var route = frappe.get_route();
		cur_list = frappe.container.page && frappe.container.page.doclistview;
		if(cur_list && cur_list.doctype!==route[1]) {
			// changing...
			cur_list = null;
		}
	}
});

$(document).on("save", function(event, doc) {
	frappe.views.set_list_as_dirty(doc.doctype);
});

frappe.views.set_list_as_dirty = function(doctype) {
	if(frappe.views.trees[doctype]) {
		frappe.views.trees[doctype].tree.refresh();
	}

	var route = frappe.get_route()[2];
	if(route && in_list(["Kanban", "Calendar", "Gantt"], route)) return;

	var list_page = "List/" + doctype;
	if(frappe.pages[list_page]) {
		if(frappe.pages[list_page].doclistview) {
			if(frappe.pages[list_page].doclistview.dirty) {
				// already refreshing...
				return;
			}
			frappe.pages[list_page].doclistview.dirty = true;
		}
	}
	var route = frappe.get_route();
	if(route[0]==="List" && route[1]===doctype) {
		setTimeout(function() {
			frappe.pages[list_page].doclistview.refresh();
		}, 100);
	}
}

frappe.views.DocListView = frappe.ui.Listing.extend({
	init: function(opts) {
		$.extend(this, opts);

		if(!in_list(frappe.boot.user.all_read, this.doctype)) {
			frappe.show_not_permitted(frappe.get_route_str());
			return;
		};

		this.label = __(this.doctype);
		this.page_name = "List/" + this.doctype;
		this.dirty = true;
		this.tags_shown = false;
		this.label = (this.label.toLowerCase().substr(-4) == 'list') ?
			__(this.label) : (__(this.label) + ' ' + __('List'));
		this.make_page();
		this.setup();

		// refresh on init
		this.refresh();
	},

	make_page: function() {
		var me = this;
		this.parent.doclistview = this;
		this.page = this.parent.page;

		this.$page = $(this.parent).css({"min-height": "400px"});

		$('<div class="frappe-list-area"></div>')
			.appendTo(this.page.main);

		this.page.main.addClass("listview-main-section");
		var module = locals.DocType[this.doctype].module;

		this.page.set_title(__(this.doctype));
		frappe.breadcrumbs.add(module, this.doctype);
	},

	setup: function() {
		var me = this;
		this.can_delete = frappe.model.can_delete(this.doctype);
		this.meta = locals.DocType[this.doctype];
		this.$page.find('.frappe-list-area').empty(),
		this.init_list_settings();
		this.setup_view_variables();
		this.setup_listview();
		this.init_list(false);
		this.init_menu();
		this.show_match_help();
		this.init_listview();
		this.setup_filterable();
		this.init_filters();
		this.init_sort_selector();
		this.set_title();
		this.init_headers();
	},

	set_title: function() {
		if(this.current_view==='Kanban') {
			this.page.set_title(this.kanban_board);
		} else {
			this.page.set_title(__(this.doctype));
		}
	},

	init_headers: function() {
		this.page.main.find(".list-headers").empty();

		if (this.current_view === 'List') {
			this.header = "list_item_main_head";
		} else if (in_list(['Image', 'Kanban', 'Gantt'], this.current_view)) {
			this.header = "image_view_item_main_head";
		} else if (this.current_view === 'Calendar') {
			this.header = null;
			this.list_header = $();
			return;
		}

		var main = frappe.render_template(this.header, {
			columns: this.listview.columns,
			right_column: this.listview.settings.right_column,
			_checkbox: ((frappe.model.can_delete(this.doctype) || this.listview.settings.selectable)
				&& !this.listview.no_delete)
		});

		this.list_header = $(frappe.render_template("list_item_row_head", { main:main, list:this.listview }))
			.appendTo(this.page.main.find(".list-headers"));

		this.init_like();
		this.init_select_all();
	},

	init_listview: function() {
		if(this.listview.settings.onload) {
			this.listview.settings.onload(this);
		}
	},

	set_sidebar_height: function() {
		var h_main = this.page.sidebar.height();
		var h_side = this.$page.find(".layout-side-section").height();
		if(h_side > h_main)
			this.$page.find(".layout-main-section").css({"min-height": h_side});
	},

	setup_filterable: function() {
		var me = this;
		this.$page.on("click", ".filterable", function(e) {
			var filters = $(this).attr("data-filter").split("|");
			var added = false;
			$.each(filters, function(i, f) {
				f = f.split(",");
				if(f[2]==="Today") {
					f[2] = frappe.datetime.get_today();
				} else if(f[2]=="User") {
					f[2] = user;
				}
				var new_filter = me.filter_list.add_filter(me.doctype, f[0], f[1], f.slice(2).join(","));
				if (new_filter) {
					// set it to true if atleast 1 filter is added
					added = true;
				}
			});
			if(added) {
				me.refresh(true);
			}
		});
		this.$page.find(".result-list").on("click", ".list-row-left", function(e) {
			// don't open in case of checkbox, like, filterable
			if ((e.target.className || "").indexOf("filterable")!==-1
				|| (e.target.className || "").indexOf("octicon-heart")!==-1
				|| e.target.type==="checkbox") {
				return;
			}

			var link = $(this).parent().find("a.list-id").get(0);
			window.location.href = link.href;
			return false;
		});
	},

	init_filters: function() {
		if(this.current_view==="Kanban") {
			this.set_kanban_board_filters();
		} else if(this.list_settings.filters) {
			this.set_filters(this.list_settings.filters);
		} else if(this.listview.settings.filters) {
			this.set_filters(this.listview.settings.filters);
		}
	},

	set_filters: function(filters) {
		var me = this;
		$.each(filters, function(i, f) {
			if(f.length===3) {
				f = [me.doctype, f[0], f[1], f[2]]
			}
			me.filter_list.add_filter(f[0], f[1], f[2], f[3]);
		});
	},

	init_sort_selector: function() {
		var args = null;
		var me = this;
		if(this.listview.sort_selector) {
			args = this.listview.sort_selector;
		}

		if(this.list_settings.order_by) {
			// last saved settings
			var order_by = this.list_settings.order_by

			if(order_by.indexOf('`.`')!==-1) {
				// scrub table name (separted by dot), like `tabTime Log`.`modified` desc`
				order_by = order_by.split('.')[1];
			}

			parts = order_by.split(' ');
			if(parts.length===2) {
				var fieldname = strip(parts[0], '`');
				args = {
					sort_by: fieldname,
					sort_order: parts[1]
				}
			}
		}

		// Always sort based on start_date field for Gantt View
		if(frappe.get_route()[2] === 'Gantt') {
			var field_map = frappe.views.calendar[this.doctype].field_map;
			args = {
				sort_by: field_map.start,
				sort_order: 'asc'
			}
		}

		this.sort_selector = new frappe.ui.SortSelector({
			parent: this.wrapper.find('.list-filters'),
			doctype: this.doctype,
			args: args,
			change: function() {
				me.run();
			}
		});
	},

	show_match_help: function() {
		var me = this;
		var match_rules_list = frappe.perm.get_match_rules(this.doctype);
		var perm = frappe.perm.get_perm(this.doctype);

		if(match_rules_list.length) {
			frappe.utils.set_footnote(this, this.$page.find(".layout-main-section"),
				frappe.render_template("list_permission_footer", {condition_list: match_rules_list}));
			$(this.footnote_area).css({"margin-top":"0px"});
		}
	},
	setup_listview: function() {
		this.listview = frappe.views.get_listview(this.doctype, this);
		this.wrapper = this.$page.find('.frappe-list-area');
		this.page_length = this.list_settings.limit || 20;
		this.allow_delete = true;
	},

	setup_view_variables: function() {
		var route = frappe.get_route();
		this.last_view = this.current_view || ''; 
		this.current_view = route[2] || route[0];
		if(this.current_view==="Kanban") {
			this.last_kanban_board = this.kanban_board;
			this.kanban_board = route[3];
		}
	},

	init_list: function(auto_run) {
		var me = this;
		// init list
		this.make({
			method: 'frappe.desk.reportview.get',
			save_list_settings: true,
			get_args: this.get_args,
			parent: this.wrapper,
			freeze: true,
			start: 0,
			page_length: this.page_length,
			show_filters: true,
			show_grid: true,
			new_doctype: this.doctype,
			allow_delete: this.allow_delete,
			no_result_message: this.make_no_result(),
			custom_new_doc: me.listview.make_new_doc || undefined,
		});

		// make_new_doc can be overridden so that default values can be prefilled
		// for example - communication list in customer
		if(this.listview.settings.list_view_doc) {
			this.listview.settings.list_view_doc(this);
		}
		else{
			$(this.wrapper).on("click", 'button[list_view_doc="'+me.doctype+'"]', function(){
				(me.listview.make_new_doc || me.make_new_doc).apply(me, [me.doctype]);
			});
		}

		if((auto_run !== false) && (auto_run !== 0))
			this.refresh();
	},

	refresh: function(dirty) {
		var me = this;

		if(dirty!==undefined) this.dirty = dirty;
		this.refresh_sidebar();
		this.setup_view_variables();

		// if view has changed, re-render header
		if(this.current_view !== this.last_view) {
			this.set_title();
			this.init_headers();
			this.dirty = true;
		}

		// if kanban board changed, set filters
		if(this.current_view==="Kanban" &&
			this.kanban_board!==this.last_kanban_board) {
			this.set_title();
			this.init_headers();
			this.set_kanban_board_filters();
			return;
		}

		if(this.listview.settings.refresh) {
			this.listview.settings.refresh(this);
		}

		this.set_filters_before_run();
		this.execute_run();
	},

	execute_run: function() {
		if(this.dirty) {
			this.run();
			if (this.clean_dash != true) {
				this.filter_list.reload_stats();
			}
		} else {
			if(new Date() - (this.last_updated_on || 0) > 30000) {
				// older than 5 mins, refresh
				this.run();
			}
		}
	},

	set_filters_before_run: function() {
		// set filters from frappe.route_options
		// before switching pages, frappe.route_options can have pre-set filters
		// for the list view
		var me = this;

		if(frappe.route_options) {
			this.set_filters_from_route_options();
			this.dirty = true;
		} else if(this.list_settings && this.list_settings.filters
				&& this.list_settings.updated_on != this.list_settings_updated_on) {
			// update remembered list settings
			this.filter_list.clear_filters();
			this.list_settings.filters.forEach(function(f) {
				me.filter_list.add_filter(f[0], f[1], f[2], f[3]);
			});
			this.dirty = true;
		}
	},

	run: function(more) {
		// set filter from route
		var me = this;

		if(this.fresh && !more) {
			return;
		}

		if(this.listview.settings.before_run) {
			this.listview.settings.before_run(this);
		}

		if(!this.listview.settings.use_route) {
			var route = frappe.get_route();
			if(route[2] && !in_list(['Image', 'Gantt', 'Kanban', 'Calendar'], route[2])) {
				$.each(frappe.utils.get_args_dict_from_url(route[2]), function(key, val) {
					me.set_filter(key, val, true);
				});
			}
		}

		this.list_header.find(".list-liked-by-me")
			.toggleClass("text-extra-muted not-liked", !this.is_star_filtered());

		this.last_updated_on = new Date();
		this.dirty = false;
		this.clean_dash = false;
		// set a fresh so that multiple refreshes do not happen
		// at the same time. This is true when deleting.
		// AJAX response will try to refresh and list_update notification
		// via async will also try to update.
		// It is not possible to guess which will reach first
		// (most probably async will) but this is a forced way
		// to prevent instant refreshes on mutilple triggers
		// in a loosly coupled way.
		this.fresh = true;
		setTimeout(function() {
			me.fresh = false;
		}, 1000);

		this._super(more);

		if(this.listview.settings.post_render) {
			this.listview.settings.post_render(this);
		}

		this.list_settings_updated_on = this.list_settings.updated_on;
	},

	make_no_result: function() {
		var new_button = frappe.boot.user.can_create.indexOf(this.doctype)!=-1
			? ('<p><button class="btn btn-primary btn-sm" \
				list_view_doc="' + this.doctype + '">'+
				__('Make a new {0}', [__(this.doctype)]) + '</button></p>')
			: '';
		var no_result_message = '<div class="msg-box no-border">\
			<p>' + __("No {0} found", [__(this.doctype)])  + '</p>' + new_button + '</div>';

		return no_result_message;
	},

	render_rows: function(values) {
		this['render_rows_' + this.current_view](values);
	},

	render_rows_Image: function(values) {
		var cols = values.slice();
		while (cols.length) {
			row = this.add_row(cols[0]);
			$("<div class='row image-view-marker'></div>").appendTo(row);
			$(row).addClass('no-hover');
			this.render_image_view_row(row, cols.splice(0, 4));
		}

		this.render_image_gallery();
	},

	render_rows_List: function(values) {
		var m = Math.min(values.length, this.page_length);
		for(var i=0; i < m; i++) {
			this.render_row(this.add_row(values[i]), values[i], this, i);
		}
	},

	render_rows_Gantt: function(values) {
		var gantt_area = $('<svg width="20" height="20"></svg>')
			.appendTo(this.wrapper.find('.result-list').css("overflow", "scroll"));
		var id = frappe.dom.set_unique_id(gantt_area);

		var me = this;
		var field_map = frappe.views.calendar[this.doctype].field_map;
		var tasks = values.map(function(item) {
			return {
				start: item[field_map.start],
				end: item[field_map.end],
				name: item[field_map.title],
				id: item[field_map.id],
				doctype: me.doctype,
				progress: item.progress,
				dependencies: item.depends_on_tasks || ""
			};
		});
		var set_value = frappe.db.set_value;
		var show_success = function() {
			show_alert({message:__("Saved"), indicator:'green'}, 1);
		} 

		frappe.require([
				"assets/frappe/js/lib/snap.svg-min.js",
				"assets/frappe/js/lib/frappe-gantt/frappe-gantt.js"
			], function() {
				me.gantt = new Gantt("#"+id, tasks, {
					date_format: "YYYY-MM-DD",
					on_click: function (task) {
						frappe.set_route('Form', task.doctype, task.id);
					},
					on_date_change: function(task, start, end) {
						set_value(task.doctype, task.id, field_map.start, start.format('YYYY-MM-DD'))
						.then(function() {
							set_value(task.doctype, task.id, field_map.end, end.format('YYYY-MM-DD'))
						})
						.then(show_success);
					},
					on_progress_change: function(task, progress) {
						set_value(task.doctype, task.id, 'progress', parseInt(progress))
						.then(show_success);
					},
					on_view_change: function(mode) {
						me.list_settings.view_mode = mode;
					}
				});

			var view_modes = me.gantt.config.view_modes || [];
			var dropdown = "<div class='dropdown pull-right'>" +
				"<a class='text-muted dropdown-toggle' data-toggle='dropdown'>" +
				"<span class='dropdown-text'>"+__('Day')+"</span><i class='caret'></i></a>" +
				"<ul class='dropdown-menu'></ul>" +
				"</div>";

			// view modes (for translation) __("Day"), __("Week"), __("Month"),
			//__("Half Day"), __("Quarter Day")

			var dropdown_list = "";
			view_modes.forEach(function(view_mode) {
				dropdown_list += "<li>" +
					"<a class='option' data-value='"+view_mode+"'>" +
					__(view_mode) + "</a></li>";
			})
			var $dropdown = $(dropdown)
			$dropdown.find(".dropdown-menu")
				.append(dropdown_list);

			me.$page.find(".list-row-right").css("margin-top", 0).html($dropdown)

			$dropdown.on("click", ".option", function() {
				var mode = $(this).data('value');
				me.gantt.change_view_mode(mode)
				$dropdown.find(".dropdown-text").text(mode);
			})
		});
	},

	render_rows_Kanban: function(values) {
		var me = this;
		frappe.require(
			['assets/frappe/js/frappe/views/kanban/fluxify.min.js',
			'assets/frappe/js/frappe/views/kanban/kanban_view.js'],
			function() {
				me.kanban = new frappe.views.KanbanBoard({
					doctype: me.doctype,
					board_name: me.kanban_board,
					cards: values,
					wrapper: me.wrapper.find('.result-list'),
					cur_list: me
				});
		});
	},

	set_kanban_board_filters: function() {
		var me = this;
		frappe.db.get_value('Kanban Board',
			{name: this.kanban_board}, 'filters',
			function(res) {
				var filters = res.filters ? JSON.parse(res.filters) : [];

				me.filter_list.clear_filters();
				me.set_filters(filters);
				me.run();
			});
	},

	render_rows_Calendar: function(values) {

		var options = $.extend({
				doctype: this.doctype,
				parent: this.wrapper.find('.result-list'),
				page: this.page,
				filter_vals: this.filter_list.get_filters()
			},
			frappe.views.calendar[this.doctype]
		);
		frappe.require([
			'assets/frappe/js/lib/fullcalendar/fullcalendar.min.css',
			'assets/frappe/js/lib/fullcalendar/fullcalendar.min.js'
		], function() {
			frappe.views.calendars[this.doctype] = new frappe.views.Calendar(options);
		});
	},

	render_row: function(row, data) {
		data.doctype = this.doctype;
		this.listview.render(row, data, this);
	},

	render_image_view_row: function(row, data) {
		for (var i = 0; i < data.length; i++) {
			data[i].doctype = this.doctype;
			this.listview.render(row, data[i], this)
		}
	},

	get_args: function() {
		var args = {
			doctype: this.doctype,
			fields: this.listview.fields,
			filters: this.filter_list.get_filters(),
			order_by: this.listview.order_by || undefined,
			group_by: this.listview.group_by || undefined,
			with_comment_count: true
		}

		// apply default filters, if specified for a listing
		$.each((this.listview.default_filters || this.listview.settings.default_filters || []), function(i, f) {
			  args.filters.push(f);
		});

		args.order_by = '`tab' + this.doctype + '`.`' + this.sort_selector.sort_by + '` ' + this.sort_selector.sort_order;

		return args;
	},
	assigned_to_me: function() {
		this.filter_list.add_filter(this.doctype, "_assign", 'like', '%' + user + '%');
		this.run();
	},
	liked_by_me: function() {
		this.filter_list.add_filter(this.doctype, "_liked_by", 'like', '%' + user + '%');
		this.run();
	},
	remove_liked_by_me: function() {
		this.filter_list.get_filter("_liked_by").remove();
	},
	is_star_filtered: function() {
		return this.filter_list.filter_exists(this.doctype, "_liked_by", 'like', '%' + user + '%');
	},
	init_menu: function() {
		var me = this;
		this.$page.on("click", ".list-tag-preview", function() { me.toggle_tags(); });

		this.page.set_secondary_action(__("Refresh"), function() {
			me.dirty = true;
			me.refresh();
		}, "octicon octicon-sync");

		this.page.btn_secondary.addClass("hidden-xs");
		this.page.add_menu_item(__("Refresh"), function() {
			me.dirty = true;
			me.refresh();
		}, "octicon octicon-sync").addClass("visible-xs");

		if(frappe.model.can_import(this.doctype)) {
			this.page.add_menu_item(__("Import"), function() {
				frappe.set_route("data-import-tool", {
					doctype: me.doctype
				});
			}, true);
		}
		if(frappe.model.can_set_user_permissions(this.doctype)) {
			this.page.add_menu_item(__("User Permissions Manager"), function() {
					frappe.route_options = {
						doctype: me.doctype
					};
					frappe.set_route("user-permissions");
				}, true);
		}
		if(in_list(user_roles, "System Manager")) {
			this.page.add_menu_item(__("Role Permissions Manager"), function() {
				frappe.route_options = {
					doctype: me.doctype
				};
				frappe.set_route("permission-manager");
			}, true);
			this.page.add_menu_item(__("Customize"), function() {
				frappe.set_route("Form", "Customize Form", {
					doc_type: me.doctype
				})
			}, true);
		}

		this.make_bulk_assignment();
		this.make_bulk_printing();

		// add to desktop
		this.page.add_menu_item(__("Add to Desktop"), function() {
			frappe.add_to_desktop(me.doctype, me.doctype);
		}, true);

		if (in_list(user_roles, "System Manager") && frappe.boot.developer_mode===1) {
			// edit doctype
			this.page.add_menu_item(__("Edit DocType"), function() {
				frappe.set_route('Form', 'DocType', me.doctype);
			}, true);
		}

	},
	make_bulk_assignment: function() {

		var me = this;

		//bulk assignment
		me.page.add_menu_item(__("Assign To"), function(){

			docname = [];

			$.each(me.get_checked_items(), function(i, doc){
				docname.push(doc.name);
			})

			if(docname.length >= 1){
				me.dialog = new frappe.ui.form.AssignToDialog({
					obj: me,
					method: 'frappe.desk.form.assign_to.add_multiple',
					doctype: me.doctype,
					docname: docname,
					bulk_assign: true,
					re_assign: true,
					callback: function(){
						me.dirty = true;
						me.refresh();
					}
				});
				me.dialog.clear();
				me.dialog.show();
			}
			else{
				frappe.msgprint(__("Select records for assignment"))
			}
		}, true)

	},
	make_bulk_printing: function() {
		var me = this;
		var print_settings = frappe.model.get_doc(":Print Settings", "Print Settings")
		var allow_print_for_draft = cint(print_settings.allow_print_for_draft)
		var is_submittable = frappe.model.is_submittable(me.doctype)
		var allow_print_for_cancelled = cint(print_settings.allow_print_for_cancelled)

		//bulk priting
		me.page.add_menu_item(__("Print"), function(){
			var no_print = false
			docname = [];
			$.each(me.get_checked_items(), function(i, doc){
				if(!is_submittable || doc.docstatus == 1  ||
					(allow_print_for_cancelled && doc.docstatus == 2)||
					(allow_print_for_draft && doc.docstatus == 0)||
					in_list(user_roles, "Administrator"))

						docname.push(doc.name);
				else
					no_print = true
			})
			if(no_print == true){
				frappe.msgprint("You selected Draft or Cancelled documents")
			}
			if(docname.length >= 1){

				var dialog = new frappe.ui.Dialog({
					title: "Print Documents",
					fields: [
						{"fieldtype": "Check", "label": __("With Letterhead"), "fieldname": "with_letterhead"},
						{"fieldtype": "Select", "label": __("Print Format"), "fieldname": "print_sel"},
					]
				});

				dialog.set_primary_action(__('Print'), function() {
					args = dialog.get_values();
					if(!args) return;
					var default_print_format = locals.DocType[me.doctype].default_print_format;
					with_letterhead = args.with_letterhead ? 1 : 0;
					print_format = args.print_sel ? args.print_sel:default_print_format;

					var json_string = JSON.stringify(docname);
					var w = window.open("/api/method/frappe.utils.print_format.download_multi_pdf?"
						+"doctype="+encodeURIComponent(me.doctype)
						+"&name="+encodeURIComponent(json_string)
						+"&format="+encodeURIComponent(print_format)
						+"&no_letterhead="+(with_letterhead ? "0" : "1"));
					if(!w) {
						msgprint(__("Please enable pop-ups")); return;
					}

				})

				print_formats = frappe.meta.get_print_formats(me.doctype);
				dialog.fields_dict.print_sel.$input.empty().add_options(print_formats);

				dialog.show();
			}
			else{
				frappe.msgprint(__("Select records for assignment"))
			}
		}, true);
	},

	init_like: function() {
		var me = this;
		this.$page.find(".result-list").on("click", ".like-action", frappe.ui.click_toggle_like);
		this.list_header.find(".list-liked-by-me").on("click", function() {
			if (me.is_star_filtered()) {
				me.remove_liked_by_me();
			} else {
				me.liked_by_me();
			}
		});

		if (!frappe.dom.is_touchscreen()) {
			frappe.ui.setup_like_popover(this.$page.find(".result-list"), ".liked-by");
		}
	},

	init_select_all: function() {
		var me = this;

		if(this.can_delete || this.listview.settings.selectable) {
			this.list_header.find(".list-select-all").on("click", function() {
				me.$page.find('.list-delete').prop("checked", $(this).prop("checked"));
				me.toggle_delete();
			});

			this.$page.on("click", ".list-delete", function(event) {
				me.toggle_delete();

				// multi-select using shift key
				var $this = $(this);
				if (event.shiftKey && $this.prop("checked")) {
					var $end_row = $this.parents(".list-row");
					var $start_row = $end_row.prevAll(".list-row")
						.find(".list-delete:checked").last().parents(".list-row");
					if ($start_row) {
						$start_row.nextUntil($end_row).find(".list-delete").prop("checked", true);
					}
				}
			});

			// after delete, hide delete button
			this.wrapper.on("render-complete", function() {
				me.toggle_delete();
			});
		}
	},

	toggle_delete: function() {
		var me = this;
		var no_of_checked_items = this.$page.find(".list-delete:checked").length;
		if (no_of_checked_items) {
			this.page.set_primary_action(__("Delete"), function() { me.delete_items() },
				"octicon octicon-trashcan");
			this.page.btn_primary.addClass("btn-danger");
			this.page.checked_items_status.text(no_of_checked_items == 1
    				? __("1 item selected")
    				: __("{0} items selected", [no_of_checked_items]))
			this.page.checked_items_status.removeClass("hide");
		} else {
			this.page.btn_primary.removeClass("btn-danger");
			this.set_primary_action();
			this.page.checked_items_status.addClass("hide");
		}
	},

	toggle_tags: function() {
		if(this.tags_shown) {
			$(".tag-row").addClass("hide");
			this.tags_shown=false;
		} else {
			$(".tag-row").removeClass("hide");
			this.tags_shown=true;
		}
	},

	get_checked_items: function() {
		var me = this;
		return $.map(this.$page.find('.list-delete:checked'), function(e) {
			if(me.current_view==='List'){
				return $(e).parents(".list-row:first").data('data');
			}
			else{
				return $(e).parents(".image-view:first").data('data');
			}
		});
	},

	delete_items: function() {
		var me = this;
		var dl = this.get_checked_items();
		if(!dl.length)
			return;

		frappe.confirm(__('Delete permanently?'),
			function() {
				me.set_working(true);
				return frappe.call({
					method: 'frappe.desk.reportview.delete_items',
					freeze: true,
					args: {
						items: $.map(dl, function(d, i) { return d.name }),
						doctype: me.doctype
					},
					callback: function() {
						me.$page.find('.list-select-all').prop("checked", false);
						frappe.utils.play_sound("delete");
						me.set_working(false);
						me.dirty = true;
						me.refresh();
					}
				})
			}
		);
	},
	refresh_sidebar: function() {
		var me = this;
		me.list_sidebar = new frappe.views.ListSidebar({
			doctype: me.doctype,
			stats: me.listview.stats,
			parent: me.$page.find('.layout-side-section'),
			set_filter: function(fieldname, label, norun, noduplicates) {
				me.set_filter(fieldname, label, norun, noduplicates);
			},
			default_filters:me.listview.settings.default_filters,
			page: me.page,
			doclistview: me
		})
	}
});
