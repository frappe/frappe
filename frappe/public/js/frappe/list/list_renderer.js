// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.views');

// Renders customized list
// usually based on `in_list_view` property

frappe.views.ListRenderer = Class.extend({
	name: 'List',
	init: function (opts) {
		$.extend(this, opts);
		this.meta = frappe.get_meta(this.doctype);

		this.init_settings();
		this.set_defaults();
		this.set_fields();
		this.set_columns();
		this.setup_cache();
	},
	set_defaults: function () {
		var me = this;
		this.page_title = __(this.doctype);

		this.set_wrapper();
		this.setup_filterable();
		this.prepare_render_view();

		// flag to enable/disable realtime updates in list_view
		this.no_realtime = false;

		// set false to render view even if no results
		// e.g Calendar
		this.show_no_result = true;

		// hide sort selector
		this.hide_sort_selector = false;

		// default settings
		this.order_by = this.order_by || 'modified desc';
		this.filters = this.filters || [];
		this.or_filters = this.or_filters || [];
		this.page_length = this.page_length || 20;
	},
	setup_cache: function () {
		frappe.provide('frappe.views.list_renderers.' + this.doctype);
		frappe.views.list_renderers[this.doctype][this.list_view.current_view] = this;
	},
	init_settings: function () {
		this.settings = frappe.listview_settings[this.doctype] || {};
		if(!("selectable" in this.settings)) {
			this.settings.selectable = true;
		}
		this.init_user_settings();

		this.order_by = this.user_settings.order_by || this.settings.order_by;
		this.filters = this.user_settings.filters || this.settings.filters;
		this.page_length = this.settings.page_length;

		// default filter for submittable doctype
		if(frappe.model.is_submittable(this.doctype) && (!this.filters || !this.filters.length)) {
			this.filters = [[this.doctype, "docstatus", "!=", 2]];
		}
	},
	init_user_settings: function () {
		frappe.provide('frappe.model.user_settings.' + this.doctype + '.' + this.name);
		this.user_settings = frappe.get_user_settings(this.doctype)[this.name];
	},
	after_refresh: function() {
		// called after refresh in list_view
	},
	before_refresh: function() {
		// called before refresh in list_view
	},
	should_refresh: function() {
		return this.list_view.current_view !== this.list_view.last_view;
	},
	load_last_view: function() {
		// this function should handle loading the last view of your list_renderer,
		// If you have a last view (for e.g last kanban board in Kanban View),
		// load it using frappe.set_route and return true
		// else return false
		return false;
	},
	set_wrapper: function () {
		this.wrapper = this.list_view.wrapper && this.list_view.wrapper.find('.result-list');
	},
	set_fields: function () {
		var me = this;
		var tabDoctype = '`tab' + this.doctype + '`.';
		this.fields = [];
		this.stats = ['_user_tags'];

		var add_field = function (fieldname) {
			if (!fieldname.includes('`tab')) {
				fieldname = tabDoctype + '`' + fieldname + '`';
			}
			if (!me.fields.includes(fieldname))
				me.fields.push(fieldname);
		}

		var defaults = [
			'name',
			'owner',
			'docstatus',
			'_user_tags',
			'_comments',
			'modified',
			'modified_by',
			'_assign',
			'_liked_by',
			'_seen'
		];
		defaults.map(add_field);

		// add title field
		if (this.meta.title_field) {
			this.title_field = this.meta.title_field;
			add_field(this.meta.title_field);
		}

		if (this.meta.image_field) {
			add_field(this.meta.image_field);
		}

		// enabled / disabled
		if (frappe.meta.has_field(this.doctype, 'enabled')) { add_field('enabled'); }
		if (frappe.meta.has_field(this.doctype, 'disabled')) { add_field('disabled'); }

		// add workflow field (as priority)
		this.workflow_state_fieldname = frappe.workflow.get_state_fieldname(this.doctype);
		if (this.workflow_state_fieldname) {
			if (!frappe.workflow.workflows[this.doctype]['override_status']) {
				add_field(this.workflow_state_fieldname);
			}
			this.stats.push(this.workflow_state_fieldname);
		}

		this.meta.fields.forEach(function (df, i) {
			if (df.in_list_view && frappe.perm.has_perm(me.doctype, df.permlevel, 'read')) {
				if (df.fieldtype == 'Image' && df.options) {
					add_field(df.options);
				} else {
					add_field(df.fieldname);
				}
				// currency field for symbol (multi-currency)
				if (df.fieldtype == 'Currency' && df.options) {
					if (df.options.includes(':')) {
						add_field(df.options.split(':')[1]);
					} else {
						add_field(df.options);
					}
				}
			}
		});

		// additional fields
		if (this.settings.add_fields) {
			this.settings.add_fields.forEach(add_field);
		}
		// kanban column fields
		if (me.meta.__kanban_column_fields) {
			me.meta.__kanban_column_fields.map(add_field);
		}
	},
	set_columns: function () {
		var me = this;
		this.columns = [];
		var name_column = {
			colspan: this.settings.colwidths && this.settings.colwidths.subject || 6,
			type: 'Subject',
			title: 'Name'
		};
		if (this.meta.title_field) {
			name_column.title = frappe.meta.get_docfield(this.doctype, this.meta.title_field).label;
		}
		this.columns.push(name_column);

		if (frappe.has_indicator(this.doctype)) {
			// indicator
			this.columns.push({
				colspan: this.settings.colwidths && this.settings.colwidths.indicator || 3,
				type: 'Indicator',
				title: 'Status'
			});
		}

		// total_colspans
		this.total_colspans = this.columns.reduce(function (total, curr) {
			return total + curr.colspan;
		}, 0);

		// overridden
		var overridden = (this.settings.add_columns || []).map(function (d) {
			return d.content;
		});

		// custom fields in list_view
		var docfields_in_list_view =
			frappe.get_children('DocType', this.doctype, 'fields', { 'in_list_view': 1 })
				.sort(function (a, b) {
					return a.idx - b.idx
				});

		docfields_in_list_view.forEach(function (d) {
			if (overridden.includes(d.fieldname) || d.fieldname === me.title_field) {
				return;
			}
			if (me.total_colspans < 12) {
				me.add_column(d);
			}
		});

		// additional columns
		if (this.settings.add_columns) {
			this.settings.add_columns.forEach(function (d) {
				if (me.total_colspans < 12) {
					if (typeof d === 'string') {
						me.add_column(frappe.meta.get_docfield(me.doctype, d));
					} else {
						me.columns.push(d);
						me.total_colspans += parseInt(d.colspan);
					}
				}
			});
		}


		// distribute remaining columns
		var empty_cols = flt(12 - this.total_colspans);
		while (empty_cols > 0) {
			this.columns = this.columns.map(function (col) {
				if (empty_cols > 0) {
					col.colspan = cint(col.colspan) + 1;
					empty_cols = empty_cols - 1;
				}
				return col;
			});
		}

		// Remove duplicates
		this.columns = this.columns.uniqBy(col => col.title);

		// Remove TextEditor field columns
		this.columns = this.columns.filter(col => col.fieldtype !== 'Text Editor');

		// Remove color field
		this.columns = this.columns.filter(col => col.fieldtype !== 'Color');

		// Limit number of columns to 4
		this.columns = this.columns.slice(0, 4);
	},
	add_column: function (df) {
		// field width
		var colspan = 3;
		if (in_list(['Int', 'Percent'], df.fieldtype)) {
			colspan = 2;
		} else if (in_list(['Check', 'Image'], df.fieldtype)) {
			colspan = 1;
		} else if (in_list(['name', 'subject', 'title'], df.fieldname)) {
			// subjects are longer
			colspan = 4;
		} else if (df.fieldtype == 'Text Editor' || df.fieldtype == 'Text') {
			colspan = 4;
		}

		if (df.columns && df.columns > 0) {
			colspan = df.columns;
		} else if (this.settings.column_colspan && this.settings.column_colspan[df.fieldname]) {
			colspan = this.settings.column_colspan[df.fieldname];
		} else {
			colspan = 2;
		}
		this.total_colspans += parseInt(colspan);
		var col = {
			colspan: colspan,
			content: df.fieldname,
			type: df.fieldtype,
			df: df,
			fieldtype: df.fieldtype,
			fieldname: df.fieldname,
			title: __(df.label)
		};
		if (this.settings.column_render && this.settings.column_render[df.fieldname]) {
			col.render = this.settings.column_render[df.fieldname];
		}
		this.columns.push(col);
	},

	setup_filterable: function () {
		var me = this;

		this.list_view.wrapper &&
		this.list_view.wrapper.on('click', '.result-list .filterable', function (e) {
			e.stopPropagation();
			var filters = $(this).attr('data-filter').split('|');
			var added = false;

			filters.forEach(function (f) {
				f = f.split(',');
				if (f[2] === 'Today') {
					f[2] = frappe.datetime.get_today();
				} else if (f[2] == 'User') {
					f[2] = frappe.session.user;
				}
				var new_filter = me.list_view.filter_list
					.add_filter(me.doctype, f[0], f[1], f.slice(2).join(','));

				if (new_filter) {
					// set it to true if atleast 1 filter is added
					added = true;
				}
			});
			if (added) {
				me.list_view.refresh(true);
			}
		});

		this.list_view.wrapper &&
		this.list_view.wrapper.on('click', '.list-item', function (e) {
			// don't open in case of checkbox, like, filterable
			if ($(e.target).hasClass('filterable')
				|| $(e.target).hasClass('octicon-heart')
				|| $(e.target).is(':checkbox')) {
				return;
			}

			var link = $(this).parent().find('a.list-id').get(0);
			if ( link && link.href )
				window.location.href = link.href;
			return false;
		});
	},

	render_view: function (values) {
		var me = this;
		var $list_items = me.wrapper.find('.list-items');

		if($list_items.length === 0) {
			$list_items = $(`
				<div class="list-items">
				</div>
			`);
			me.wrapper.append($list_items);
		}

		values.map(value => {
			const $item = $(this.get_item_html(value));
			const $item_container = $('<div class="list-item-container">').append($item);

			$list_items.append($item_container);

			if (this.settings.post_render_item) {
				this.settings.post_render_item(this, $item_container, value);
			}

			this.render_tags($item_container, value);
		});

		this.render_count();
	},

	render_count: function() {
		const $header_right = this.list_view.list_header.find('.list-item__content--activity');
		const current_count = this.list_view.data.length;

		frappe.call({
			method: 'frappe.desk.reportview.get',
			args: {
				doctype: this.doctype,
				filters: this.list_view.get_filters_args(),
				fields: ['count(`tab' + this.doctype + '`.name) as total_count']
			}
		}).then(r => {
			const count = r.message.values[0][0] || current_count;
			const str = __('{0} of {1}', [current_count, count]);
			const $html = $(`<span>${str}</span>`);

			$html.css({
				marginRight: '10px'
			})
			$header_right.addClass('text-muted');
			$header_right.html($html);
		})
	},

	// returns html for a data item,
	// usually based on a template
	get_item_html: function (data) {
		var main = this.columns.map(column =>
			frappe.render_template('list_item_main', {
				data: data,
				col: column,
				value: data[column.fieldname],
				formatters: this.settings.formatters,
				subject: this.get_subject_html(data, true),
				indicator: this.get_indicator_html(data),
			})
		).join("");

		return frappe.render_template('list_item_row', {
			data: data,
			main: main,
			settings: this.settings,
			meta: this.meta,
			indicator_dot: this.get_indicator_dot(data),
		})
	},

	get_header_html: function () {
		var main = this.columns.map(column =>
			frappe.render_template('list_item_main_head', {
				col: column,
				_checkbox: ((frappe.model.can_delete(this.doctype) || this.settings.selectable)
					&& !this.no_delete)
			})
		).join("");

		return frappe.render_template('list_item_row_head', { main: main, list: this });
	},

	render_tags: function (element, data) {
		var me = this;
		var tag_row = $(`<div class='tag-row'>
			<div class='list-tag hidden-xs'></div>
			<div class='clearfix'></div>
		</div>`).appendTo(element);

		if (!me.list_view.tags_shown) {
			tag_row.addClass('hide');
		}

		// add tags
		var tag_editor = new frappe.ui.TagEditor({
			parent: tag_row.find('.list-tag'),
			frm: {
				doctype: this.doctype,
				docname: data.name
			},
			list_sidebar: me.list_view.list_sidebar,
			user_tags: data._user_tags,
			on_change: function (user_tags) {
				data._user_tags = user_tags;
			}
		});
		tag_editor.wrapper.on('click', '.tagit-label', function () {
			me.list_view.set_filter('_user_tags', $(this).text());
		});
	},

	get_subject_html: function (data, without_workflow) {
		data._without_workflow = without_workflow;
		return frappe.render_template('list_item_subject', data);
	},

	get_indicator_html: function (doc) {
		var indicator = frappe.get_indicator(doc, this.doctype);
		if (indicator) {
			return `<span class='indicator ${indicator[1]} filterable'
				data-filter='${indicator[2]}'>
				${__(indicator[0])}
			<span>`;
		}
		return '';
	},
	get_indicator_dot: function (doc) {
		var indicator = frappe.get_indicator(doc, this.doctype);
		if (!indicator) {
			return '';
		}
		return `<span class='indicator ${indicator[1]}' title='${__(indicator[0])}'></span>`;
	},
	prepare_data: function (data) {
		if (data.modified) {
			this.prepare_when(data, data.modified);
		}

		// nulls as strings
		for (var key in data) {
			if (data[key] == null) {
				data[key] = '';
			}
		}

		data.doctype = this.doctype;
		data._liked_by = JSON.parse(data._liked_by || '[]');
		data._checkbox = (frappe.model.can_delete(this.doctype) || this.settings.selectable) && !this.no_delete

		data._doctype_encoded = encodeURIComponent(data.doctype);
		data._name = data.name.replace(/'/g, '\'');
		data._name_encoded = encodeURIComponent(data.name);
		data._submittable = frappe.model.is_submittable(this.doctype);

		var title_field = this.meta.title_field || 'name';
		data._title = strip_html(data[title_field] || data.name);

		// check for duplicates
		// add suffix like (1), (2) etc
		if (data.name && this.values_map) {
			if (this.values_map[data.name]!==undefined) {
				if (this.values_map[data.name]===1) {
					// update first row!
					this.set_title_with_row_number(this.rows_map[data.name], 1);
				}
				this.values_map[data.name]++;
				this.set_title_with_row_number(data, this.values_map[data.name]);
			} else {
				this.values_map[data.name] = 1;
				this.rows_map[data.name] = data;
			}
		}

		data._full_title = data._title;

		data._workflow = null;
		if (this.workflow_state_fieldname) {
			data._workflow = {
				fieldname: this.workflow_state_fieldname,
				value: data[this.workflow_state_fieldname],
				style: frappe.utils.guess_style(data[this.workflow_state_fieldname])
			}
		}

		data._user = frappe.session.user;

		if(!data._user_tags) data._user_tags = "";

		data._tags = data._user_tags.split(',').filter(function (v) {
			// filter falsy values
			return v;
		});

		data.css_seen = '';
		if (data._seen) {
			var seen = JSON.parse(data._seen);
			if (seen && in_list(seen, data._user)) {
				data.css_seen = 'seen'
			}
		}

		// whether to hide likes/comments/assignees
		data._hide_activity = 0;

		data._assign_list = JSON.parse(data._assign || '[]');

		// prepare data in settings
		if (this.settings.prepare_data)
			this.settings.prepare_data(data);

		return data;
	},

	set_title_with_row_number: function (data, id) {
		data._title = data._title + ` (${__("Row")} ${id})`;
		data._full_title = data._title;
	},

	prepare_when: function (data, date_str) {
		if (!date_str) date_str = data.modified;
		// when
		data.when = (frappe.datetime.str_to_user(date_str)).split(' ')[0];
		var diff = frappe.datetime.get_diff(frappe.datetime.get_today(), date_str.split(' ')[0]);
		if (diff === 0) {
			data.when = comment_when(date_str);
		}
		if (diff === 1) {
			data.when = __('Yesterday')
		}
		if (diff === 2) {
			data.when = __('2 days ago')
		}
	},

	// for views which require 3rd party libs
	required_libs: null,

	prepare_render_view: function () {
		var me = this;
		this._render_view = this.render_view;

		var lib_exists = (typeof this.required_libs === 'string' && this.required_libs)
			|| ($.isArray(this.required_libs) && this.required_libs.length);

		this.render_view = function (values) {
			me.values_map = {};
			me.rows_map = {};
			// prepare data before rendering view
			values = values.map(me.prepare_data.bind(this));
			// remove duplicates
			// values = values.uniqBy(value => value.name);

			if (lib_exists) {
				me.load_lib(function () {
					me._render_view(values);
				});
			} else {
				me._render_view(values);
			}
		}.bind(this);
	},

	load_lib: function (callback) {
		frappe.require(this.required_libs, callback);
	},

	render_bar_graph: function (parent, data, field, label) {
		var args = {
			percent: data[field],
			label: __(label)
		}
		$(parent).append(`<span class='progress' style='width: 100 %; float: left; margin: 5px 0px;'> \
			<span class='progress- bar' title='${args.percent}% ${args.label}' \
				style='width: ${args.percent}%;'></span>\
		</span>`);
	},
	render_icon: function (parent, icon_class, label) {
		var icon_html = `<i class='${icon_class}' title='${__(label) || ''}'></i>`;
		$(parent).append(icon_html);
	},
	make_no_result: function () {
		var new_button = frappe.boot.user.can_create.includes(this.doctype)
			? (`<p><button class='btn btn-primary btn-sm'
				list_view_doc='${this.doctype}'>
					${__('Make a new {0}', [__(this.doctype)])}
				</button></p>`)
			: '';
		var no_result_message =
			`<div class='msg-box no-border'>
				<p>${__('No {0} found', [__(this.doctype)])}</p>
				${new_button}
			</div>`;

		return no_result_message;
	},
});
