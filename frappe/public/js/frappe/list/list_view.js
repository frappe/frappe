// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.views.list_view');
frappe.provide('frappe.views.list_renderers');

cur_list = null;
frappe.views.ListFactory = frappe.views.Factory.extend({
	make: function (route) {
		var me = this;
		var doctype = route[1];

		frappe.model.with_doctype(doctype, function () {
			if (locals['DocType'][doctype].issingle) {
				frappe.set_re_route('Form', doctype);
			} else {
				if (!frappe.views.list_view[doctype]) {
					frappe.views.list_view[doctype] = new frappe.views.ListView({
						doctype: doctype,
						parent: me.make_page(true, 'List/' + doctype)
					});
				} else {
					frappe.container.change_to(frappe.views.list_view[doctype].page_name);
				}
				me.set_cur_list();
			}
		});
	},
	show: function () {
		if(this.re_route_to_view()) {
			return;
		}
		this.set_module_breadcrumb();
		this._super();
		this.set_cur_list();
		cur_list && cur_list.refresh();
	},
	re_route_to_view: function() {
		var route = frappe.get_route();
		var doctype = route[1];
		var last_route = frappe.route_history.slice(-2)[0];
		if (route[0] === 'List' && route.length === 2 && frappe.views.list_view[doctype]) {
			if(last_route && last_route[0]==='List' && last_route[1]===doctype) {
				// last route same as this route, so going back.
				// this happens because #List/Item will redirect to #List/Item/List
				// while coming from back button, the last 2 routes will be same, so
				// we know user is coming in the reverse direction (via back button)

				// example:
				// Step 1: #List/Item redirects to #List/Item/List
				// Step 2: User hits "back" comes back to #List/Item
				// Step 3: Now we cannot send the user back to #List/Item/List so go back one more step
				window.history.go(-1);
			} else {
				frappe.views.list_view[doctype].load_last_view();
			}
			return true;
		}
	},
	set_module_breadcrumb: function () {
		if (frappe.route_history.length > 1) {
			var prev_route = frappe.route_history[frappe.route_history.length - 2];
			if (prev_route[0] === 'modules') {
				var doctype = frappe.get_route()[1],
					module = prev_route[1];
				if (frappe.module_links[module] && frappe.module_links[module].includes(doctype)) {
					// save the last page from the breadcrumb was accessed
					frappe.breadcrumbs.set_doctype_module(doctype, module);
				}
			}
		}
	},
	set_cur_list: function () {
		var route = frappe.get_route();
		cur_list = frappe.container.page && frappe.container.page.list_view;
		if (cur_list && cur_list.doctype !== route[1]) {
			// changing...
			cur_list = null;
		}
	}
});

$(document).on('save', function (event, doc) {
	frappe.views.set_list_as_dirty(doc.doctype);
});

frappe.views.set_list_as_dirty = function (doctype) {
	if (frappe.views.trees[doctype]) {
		frappe.views.trees[doctype].tree.refresh();
	}

	var route = frappe.get_route();
	var current_view = route[2] || 'List';

	var list_renderer = frappe.views.list_renderers[doctype];
	if (list_renderer
		&& list_renderer[current_view]
		&& list_renderer[current_view].no_realtime) {
		return;
	}

	var list_page = 'List/' + doctype;
	if (frappe.pages[list_page]) {
		if (frappe.pages[list_page].list_view) {
			if (frappe.pages[list_page].list_view.dirty) {
				// already refreshing...
				return;
			}
			frappe.pages[list_page].list_view.dirty = true;
		}
	}
	if (route[0] === 'List' && route[1] === doctype) {
		setTimeout(function () {
			frappe.pages[list_page].list_view.refresh();
		}, 100);
	}
}

frappe.views.view_modes = ['List', 'Gantt', 'Kanban', 'Calendar', 'Image', 'Inbox'];

frappe.views.ListView = frappe.ui.BaseList.extend({
	init: function (opts) {
		$.extend(this, opts);

		if (!frappe.boot.user.all_read.includes(this.doctype)) {
			frappe.show_not_permitted(frappe.get_route_str());
			return;
		}

		this.is_list_view = true;
		this.page_name = 'List/' + this.doctype;
		this.dirty = true;
		this.tags_shown = false;

		this.page_title = __(this.doctype);
		this.page_title =
			(this.page_title.toLowerCase().substr(-4) == 'list') && __(this.page_title)
			|| __(this.page_title) + ' ' + __('List');

		this.make_page();
		this.setup();

		// refresh on init
		this.refresh();
	},

	make_page: function () {
		this.parent.list_view = this;
		this.page = this.parent.page;

		this.$page = $(this.parent).css({ 'min-height': '400px' });

		$(`<div class='frappe-list-area'></div>`)
			.appendTo(this.page.main);

		this.page.main.addClass('listview-main-section');
		var module = locals.DocType[this.doctype].module;

		frappe.breadcrumbs.add(module, this.doctype);
	},

	setup: function () {
		this.can_delete = frappe.model.can_delete(this.doctype);
		this.meta = frappe.get_meta(this.doctype);
		this.wrapper = this.$page.find('.frappe-list-area').empty();
		this.allow_delete = true;

		this.load_last_view();
		this.setup_view_variables();

		this.setup_list_renderer();
		this.init_base_list(false);
		this.list_renderer.set_wrapper();
		this.list_renderer_onload();

		this.show_match_help();
		this.init_menu();
		this.init_sort_selector();
		this.init_filters();
		this.set_title();
		this.init_headers();
	},

	refresh_surroundings: function() {
		this.init_sort_selector();
		this.init_filters();
		this.set_title();
		this.init_headers();
		this.no_result_message = this.list_renderer.make_no_result()
	},

	setup_list_renderer: function () {
		frappe.provide('frappe.views.list_renderers.' + this.doctype);

		var list_renderer = frappe.views.list_renderers[this.doctype][this.current_view];
		if (list_renderer) {
			this.list_renderer = list_renderer;
			this.list_renderer.init_settings();
			return;
		}

		var opts = {
			doctype: this.doctype,
			list_view: this
		}

		if (this.current_view === 'List') {
			this.list_renderer = new frappe.views.ListRenderer(opts);
		} else if (this.current_view === 'Gantt') {
			this.list_renderer = new frappe.views.GanttView(opts);
		} else if (this.current_view === 'Calendar') {
			this.list_renderer = new frappe.views.CalendarView(opts);
		} else if (this.current_view === 'Image') {
			this.list_renderer = new frappe.views.ImageView(opts);
		} else if (this.current_view === 'Kanban') {
			this.list_renderer = new frappe.views.KanbanView(opts);
		} else if (this.current_view === 'Inbox') {
			this.list_renderer = new frappe.views.InboxView(opts)
		}
	},

	render_view: function (values) {
		this.list_renderer.render_view(values);
	},

	set_title: function () {
		if (this.list_renderer.page_title) {
			this.page.set_title(this.list_renderer.page_title);
		} else {
			this.page.set_title(this.page_title);
		}
	},

	load_last_view: function () {
		var us = frappe.get_user_settings(this.doctype);
		var route = ['List', this.doctype];

		if (us.last_view && frappe.views.view_modes.includes(us.last_view)) {
			route.push(us.last_view);

			if (us.last_view === 'Kanban') {
				route.push(us['Kanban'].last_kanban_board);
			}

			if (us.last_view === 'Inbox') {
				route.push(us['Inbox'].last_email_account)
			}
		} else {
			route.push('List');
		}

		frappe.set_route(route);
	},

	init_headers: function () {
		this.page.main.find('.list-headers > .list-item--head').hide();
		this.list_header = this.page.main.find('.list-headers > '
				+ '.list-item--head[data-list-renderer="'
				+ this.list_renderer.name +'"]');

		if(this.list_header.length > 0) {
			this.list_header.show();
			return;
		}


		var html = this.list_renderer.get_header_html();
		if(!html) {
			this.list_header = $();
			return;
		}

		this.list_header = $(html).appendTo(this.page.main.find('.list-headers'));

		this.setup_like();
		this.setup_select_all();
		this.setup_delete();
	},

	list_renderer_onload: function () {
		if (this.list_renderer.settings.onload) {
			this.list_renderer.settings.onload(this);
		}
	},

	set_sidebar_height: function () {
		var h_main = this.page.sidebar.height();
		var h_side = this.$page.find('.layout-side-section').height();
		if (h_side > h_main)
			this.$page.find('.layout-main-section').css({ 'min-height': h_side });
	},

	init_filters: function () {
		this.make_standard_filters();
		this.filter_list = new frappe.ui.FilterList({
			base_list: this,
			parent: this.wrapper.find('.list-filters').show(),
			doctype: this.doctype,
			default_filters: []
		});
		this.set_filters(this.list_renderer.filters);
	},

	set_filters: function (filters) {
		var me = this;
		$.each(filters, function (i, f) {
			var hidden = false
			if (f.length === 3) {
				f = [me.doctype, f[0], f[1], f[2]]
			} else if (f.length === 5) {
				hidden = f.pop(4) || false
			}
			me.filter_list.add_filter(f[0], f[1], f[2], f[3], hidden);
		});
	},

	init_sort_selector: function () {
		var me = this;
		var order_by = this.list_renderer.order_by;

		this.sort_selector = new frappe.ui.SortSelector({
			parent: this.wrapper.find('.list-filters'),
			doctype: this.doctype,
			args: order_by,
			change: function () { me.run(); }
		});
	},

	show_match_help: function () {
		var me = this;
		var match_rules_list = frappe.perm.get_match_rules(this.doctype);
		var perm = frappe.perm.get_perm(this.doctype);

		if (match_rules_list.length) {
			this.footnote_area =
				frappe.utils.set_footnote(this.footnote_area, this.$page.find('.layout-main-section'),
					frappe.render_template('list_permission_footer', {
						condition_list: match_rules_list
					}));
			$(this.footnote_area).css({ 'margin-top': '0px' });
		}
	},

	setup_view_variables: function () {
		var route = frappe.get_route();
		this.last_view = this.current_view || '';
		this.current_view = route[2] || 'List';
	},

	init_base_list: function (auto_run) {
		var me = this;
		// init list
		this.make({
			method: 'frappe.desk.reportview.get',
			save_user_settings: true,
			get_args: this.get_args,
			parent: this.wrapper,
			freeze: true,
			start: 0,
			page_length: this.list_renderer.page_length,
			show_filters: false,
			new_doctype: this.doctype,
			no_result_message: this.list_renderer.make_no_result(),
			show_no_result: function() {
				return me.list_renderer.show_no_result;
			}
		});

		this.setup_make_new_doc();

		if (auto_run !== false && auto_run !== 0)
			this.refresh();
	},

	setup_make_new_doc: function () {
		var me = this;
		// make_new_doc can be overridden so that default values can be prefilled
		// for example - communication list in customer
		if (this.list_renderer.settings.list_view_doc) {
			this.list_renderer.settings.list_view_doc(this);
		} else {
			var doctype = this.list_renderer.no_result_doctype? this.list_renderer.no_result_doctype: this.doctype
			$(this.wrapper).on('click', `button[list_view_doc='${doctype}']`, function () {
				if (me.list_renderer.make_new_doc)
					me.list_renderer.make_new_doc()
				else
					me.make_new_doc.apply(me, [me.doctype]);
			});
		}
	},

	refresh: function (dirty) {
		var me = this;

		if (dirty !== undefined) this.dirty = dirty;

		this.refresh_sidebar();
		this.setup_view_variables();

		if (this.list_renderer.should_refresh()) {
			this.setup_list_renderer();
			this.refresh_surroundings();
			this.dirty = true;
		}

		if (this.list_renderer.settings.refresh) {
			this.list_renderer.settings.refresh(this);
		}

		this.set_filters_before_run();
		this.execute_run();
	},

	execute_run: function () {
		if (this.dirty) {
			this.run();
		} else {
			if (new Date() - (this.last_updated_on || 0) > 30000) {
				// older than 5 mins, refresh
				this.run();
			}
		}
	},

	save_user_settings_locally: function (args) {

		frappe.provide('frappe.model.user_settings.' + this.doctype + '.' + this.list_renderer.name);
		var user_settings_common = frappe.model.user_settings[this.doctype];
		var user_settings = frappe.model.user_settings[this.doctype][this.list_renderer.name];

		if (!user_settings) return;

		var different = false;
		if (!frappe.utils.arrays_equal(args.filters, user_settings.filters)) {
			// settings are dirty if filters change
			user_settings.filters = args.filters;
			different = true;
		}

		if (user_settings.order_by !== args.order_by) {
			user_settings.order_by = args.order_by;
			different = true;
		}

		// never save page_length in user_settings
		// if (user_settings.page_length !== args.page_length) {
		// 	user_settings.page_length = args.page_length || 20
		// 	different = true;
		// }

		// save fields in list settings
		if (args.save_user_settings_fields) {
			user_settings.fields = args.fields;
		}

		// save last view
		if (user_settings_common.last_view !== this.current_view
			&& frappe.views.view_modes.includes(this.current_view)) {
			user_settings_common.last_view = this.current_view;
			different = true;
		}

		if (different) {
			user_settings_common.updated_on = moment().toString();
		}
	},

	set_filters_before_run: function () {
		// set filters from frappe.route_options
		// before switching pages, frappe.route_options can have pre-set filters
		// for the list view
		var me = this;

		if (frappe.route_options) {
			this.set_filters_from_route_options();
			this.dirty = true;
		}
	},

	run: function (more) {
		// set filter from route
		var me = this;

		if (this.fresh && !more) {
			return;
		}

		if (this.list_renderer.settings.before_run) {
			this.list_renderer.settings.before_run(this);
		}

		if (!this.list_renderer.settings.use_route) {
			var route = frappe.get_route();
			if (route[2] && !frappe.views.view_modes.includes(route[2])) {
				$.each(frappe.utils.get_args_dict_from_url(route[2]), function (key, val) {
					me.set_filter(key, val, true);
				});
			}
		}

		if(this.list_header) {
			this.list_header.find('.list-liked-by-me')
				.toggleClass('text-extra-muted not-liked', !this.is_star_filtered());
		}

		this.last_updated_on = new Date();
		this.dirty = false;
		// set a fresh so that multiple refreshes do not happen
		// at the same time. This is true when deleting.
		// AJAX response will try to refresh and list_update notification
		// via async will also try to update.
		// It is not possible to guess which will reach first
		// (most probably async will) but this is a forced way
		// to prevent instant refreshes on mutilple triggers
		// in a loosly coupled way.
		this.fresh = true;
		setTimeout(function () {
			me.fresh = false;
		}, 1000);

		this._super(more);

		if (this.list_renderer.settings.post_render) {
			this.list_renderer.settings.post_render(this);
		}

		this.wrapper.on('render-complete', function() {
			me.list_renderer.after_refresh();
		})
	},

	get_args: function () {
		var args = {
			doctype: this.doctype,
			fields: this.list_renderer.fields,
			filters: this.get_filters_args(),
			order_by: this.get_order_by_args(),
			with_comment_count: true
		}
		return args;
	},
	get_filters_args: function() {
		var filters = [];
		if(this.filter_list) {
			// get filters from filter_list
			filters = this.filter_list.get_filters();
		} else {
			filters = this.list_renderer.filters;
		}
		// remove duplicates
		var uniq = filters.uniqBy(JSON.stringify);
		return uniq;
	},
	get_order_by_args: function() {
		var order_by = '';
		if(this.sort_selector) {
			// get order_by from sort_selector
			order_by = $.format('`tab{0}`.`{1}` {2}',
				[this.doctype, this.sort_selector.sort_by,  this.sort_selector.sort_order]);
		} else {
			order_by = this.list_renderer.order_by;
		}
		return order_by;
	},
	assigned_to_me: function () {
		this.filter_list.add_filter(this.doctype, '_assign', 'like', '%' + frappe.session.user + '%');
		this.run();
	},
	liked_by_me: function () {
		this.filter_list.add_filter(this.doctype, '_liked_by', 'like', '%' + frappe.session.user + '%');
		this.run();
	},
	remove_liked_by_me: function () {
		this.filter_list.get_filter('_liked_by').remove();
	},
	is_star_filtered: function () {
		return this.filter_list.filter_exists(this.doctype, '_liked_by', 'like', '%' + frappe.session.user + '%');
	},
	init_menu: function () {
		var me = this;
		this.$page.on('click', '.list-tag-preview', function () { me.toggle_tags(); });

		// Refresh button for large screens
		this.page.set_secondary_action(__('Refresh'), function () {
			me.refresh(true);
		}, 'octicon octicon-sync')
			.addClass('hidden-xs');

		// Refresh button as menu item in small screens
		this.page.add_menu_item(__('Refresh'), function () {
			me.refresh(true);
		}, 'octicon octicon-sync')
			.addClass('visible-xs');

		if (frappe.model.can_import(this.doctype)) {
			this.page.add_menu_item(__('Import'), function () {
				frappe.set_route('data-import-tool', {
					doctype: me.doctype
				});
			}, true);
		}
		if (frappe.model.can_set_user_permissions(this.doctype)) {
			this.page.add_menu_item(__('User Permissions'), function () {
				frappe.set_route('List', 'User Permission', {
					allow: me.doctype
				});
			}, true);
		}
		if (frappe.user_roles.includes('System Manager')) {
			this.page.add_menu_item(__('Role Permissions Manager'), function () {
				frappe.set_route('permission-manager', {
					doctype: me.doctype
				});
			}, true);
			this.page.add_menu_item(__('Customize'), function () {
				frappe.set_route('Form', 'Customize Form', {
					doc_type: me.doctype
				})
			}, true);
		}

		this.make_bulk_assignment();
		if(frappe.model.can_print(this.doctype)) {
			this.make_bulk_printing();
		}

		// add to desktop
		this.page.add_menu_item(__('Add to Desktop'), function () {
			frappe.add_to_desktop(me.doctype, me.doctype);
		}, true);

		if (frappe.user_roles.includes('System Manager') && frappe.boot.developer_mode === 1) {
			// edit doctype
			this.page.add_menu_item(__('Edit DocType'), function () {
				frappe.set_route('Form', 'DocType', me.doctype);
			}, true);
		}

	},
	make_bulk_assignment: function () {

		var me = this;

		//bulk assignment
		me.page.add_menu_item(__('Assign To'), function () {

			var docnames = me.get_checked_items().map(function (doc) {
				return doc.name;
			});

			if (docnames.length >= 1) {
				me.dialog = new frappe.ui.form.AssignToDialog({
					obj: me,
					method: 'frappe.desk.form.assign_to.add_multiple',
					doctype: me.doctype,
					docname: docnames,
					bulk_assign: true,
					re_assign: true,
					callback: function () {
						me.refresh(true);
					}
				});
				me.dialog.clear();
				me.dialog.show();
			}
			else {
				frappe.msgprint(__('Select records for assignment'))
			}
		}, true);

	},
	make_bulk_printing: function () {
		var me = this;
		var print_settings = frappe.model.get_doc(':Print Settings', 'Print Settings')
		var allow_print_for_draft = cint(print_settings.allow_print_for_draft)
		var is_submittable = frappe.model.is_submittable(me.doctype)
		var allow_print_for_cancelled = cint(print_settings.allow_print_for_cancelled)

		//bulk priting
		me.page.add_menu_item(__('Print'), function () {
			var items = me.get_checked_items();

			var valid_docs =
				items.filter(function (doc) {
					return !is_submittable || doc.docstatus === 1 ||
						(allow_print_for_cancelled && doc.docstatus == 2) ||
						(allow_print_for_draft && doc.docstatus == 0) ||
						frappe.user_roles.includes('Administrator')
				}).map(function (doc) {
					return doc.name
				});

			var invalid_docs = items.filter(function (doc) {
				return !valid_docs.includes(doc.name);
			});

			if (invalid_docs.length >= 1) {
				frappe.msgprint(__('You selected Draft or Cancelled documents'))
				return;
			}

			if (valid_docs.length >= 1) {

				var dialog = new frappe.ui.Dialog({
					title: 'Print Documents',
					fields: [
						{ 'fieldtype': 'Check', 'label': __('With Letterhead'), 'fieldname': 'with_letterhead' },
						{ 'fieldtype': 'Select', 'label': __('Print Format'), 'fieldname': 'print_sel' },
					]
				});

				dialog.set_primary_action(__('Print'), function () {
					var args = dialog.get_values();
					if (!args) return;
					var default_print_format = locals.DocType[me.doctype].default_print_format;
					var with_letterhead = args.with_letterhead ? 1 : 0;
					var print_format = args.print_sel ? args.print_sel : default_print_format;

					var json_string = JSON.stringify(valid_docs);
					var w = window.open('/api/method/frappe.utils.print_format.download_multi_pdf?'
						+ 'doctype=' + encodeURIComponent(me.doctype)
						+ '&name=' + encodeURIComponent(json_string)
						+ '&format=' + encodeURIComponent(print_format)
						+ '&no_letterhead=' + (with_letterhead ? '0' : '1'));
					if (!w) {
						frappe.msgprint(__('Please enable pop-ups')); return;
					}
				});

				var print_formats = frappe.meta.get_print_formats(me.doctype);
				dialog.fields_dict.print_sel.$input.empty().add_options(print_formats);

				dialog.show();
			}
			else {
				frappe.msgprint(__('Select atleast 1 record for printing'))
			}
		}, true);
	},

	setup_like: function () {
		var me = this;
		this.$page.find('.result-list').on('click', '.like-action', frappe.ui.click_toggle_like);
		this.list_header.find('.list-liked-by-me').on('click', function () {
			if (me.is_star_filtered()) {
				me.remove_liked_by_me();
			} else {
				me.liked_by_me();
			}
		});

		if (!frappe.dom.is_touchscreen()) {
			frappe.ui.setup_like_popover(this.$page.find('.result-list'), '.liked-by');
		}
	},

	setup_select_all: function () {
		var me = this;

		if (this.can_delete || this.list_renderer.settings.selectable) {
			this.list_header.find('.list-select-all').on('click', function () {
				me.$page.find('.list-row-checkbox').prop('checked', $(this).prop('checked'));
			});

			this.$page.on('click', '.list-row-checkbox', function (event) {
				// multi-select using shift key
				var $this = $(this);
				if (event.shiftKey && $this.prop('checked')) {
					var $end_row = $this.parents('.list-item-container');
					var $start_row = $end_row.prevAll('.list-item-container')
						.find('.list-row-checkbox:checked').last().parents('.list-item-container');
					if ($start_row) {
						$start_row.nextUntil($end_row).find('.list-row-checkbox').prop('checked', true);
					}
				}
			});
		}
	},

	setup_delete: function () {
		var me = this;
		if (!this.can_delete) {
			return;
		}
		this.$page.on('change', '.list-row-checkbox, .list-select-all', function() {
			me.toggle_delete();
		});
		// after delete, hide delete button
		this.wrapper.on('render-complete', function () {
			me.toggle_delete();
		});
	},

	toggle_delete: function () {
		var me = this;
		var checked_items = this.get_checked_items();
		var checked_items_status = this.$page.find('.checked-items-status');

		if (checked_items.length > 0) {
			this.page.set_primary_action(__('Delete'), function () {
				me.delete_items()
			}, 'octicon octicon-trashcan')
				.addClass('btn-danger');

			checked_items_status.text(
				checked_items.length == 1
					? __('1 item selected')
					: __('{0} items selected', [checked_items.length])
			)
			checked_items_status.removeClass('hide');
		} else {
			this.page.btn_primary.removeClass('btn-danger');
			this.set_primary_action();
			checked_items_status.addClass('hide');
		}
	},

	toggle_tags: function () {
		if (this.tags_shown) {
			$('.tag-row').addClass('hide');
			this.tags_shown = false;
		} else {
			$('.tag-row').removeClass('hide');
			this.tags_shown = true;
		}
	},

	get_checked_items: function () {
		var names = this.$page.find('.list-row-checkbox:checked').map(function (i, item) {
			return cstr($(item).data().name);
		}).toArray();

		return this.data.filter(function (doc) {
			return names.includes(doc.name);
		});
	},

	set_primary_action: function () {
		if (this.list_renderer.settings.set_primary_action) {
			this.list_renderer.settings.set_primary_action(this);
		} else {
			this._super();
		}
	},

	delete_items: function () {
		var me = this;
		var to_delete = this.get_checked_items();
		if (!to_delete.length)
			return;

		var docnames = to_delete.map(function (doc) {
			return doc.name;
		});

		frappe.confirm(__('Delete {0} items permanently?', [to_delete.length]),
			function () {
				return frappe.call({
					method: 'frappe.desk.reportview.delete_items',
					freeze: true,
					args: {
						items: docnames,
						doctype: me.doctype
					},
					callback: function () {
						me.$page.find('.list-select-all').prop('checked', false);
						frappe.utils.play_sound('delete');
						me.refresh(true);
					}
				})
			}
		);
	},
	refresh_sidebar: function () {
		//TODO: refresh if already exist
		this.list_sidebar = new frappe.views.ListSidebar({
			doctype: this.doctype,
			stats: this.list_renderer.stats,
			parent: this.$page.find('.layout-side-section'),
			set_filter: this.set_filter.bind(this),
			default_filters: this.list_renderer.filters,
			page: this.page,
			list_view: this
		})
	}
});
