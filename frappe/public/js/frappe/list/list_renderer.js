// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.views');

// Renders customized list
// usually based on `in_list_view` property

frappe.views.ListRenderer = Class.extend({
	init: function (opts) {
		$.extend(this, opts);

		this.prepare_meta();
		this.set_fields();
		this.set_columns();
		this.cache();
	},
	prepare_meta: function() {
		var me = this;
		this.meta = frappe.get_meta(this.doctype);
		this.settings = frappe.listview_settings[this.doctype] || {};
		this.id_list = [];
		this.order_by = this.settings.order_by;
		this.group_by = this.settings.group_by;
		this.set_wrapper();
		
		// flag to enable/disable realtime updates in list_view
		this.no_realtime = false;

		this.list_view.onreset = function () {
			me.id_list = [];
		}
	},
	cache: function() {
		frappe.provide('frappe.views.list_renderers')
		if(!frappe.views.list_renderers[this.doctype])
			frappe.views.list_renderers[this.doctype] = {}

		frappe.views.list_renderers[this.doctype][this.list_view.current_view] = this;
	},
	set_wrapper: function() {
		this.wrapper = this.list_view.wrapper.find('.result-list');
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

		// enabled / disabled
		if (frappe.meta.has_field(this.doctype, 'enabled')) { add_field('enabled'); };
		if (frappe.meta.has_field(this.doctype, 'disabled')) { add_field('disabled'); };

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
					};
				}
			}
		});

		// additional fields
		if (this.settings.add_fields) {
			this.settings.add_fields.forEach(add_field);
		}
		// kanban column fields
		if (me.meta.__kanban_column_fields)
			me.fields = me.fields.concat(me.meta.__kanban_column_fields);
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

	render_view: function(values) {
		var me = this;
		values.map(function(value) {
			var row = $('<div class="list-row">')
				.data("data", me.meta)
				.appendTo(me.wrapper).get(0);
			me.render_item(row, value);
		});
	},

	// renders data(doc) in element
	render_item: function (element, data) {
		this.prepare_data(data);

		// maintain id_list to avoid duplication incase
		// of filtering by child table
		if (this.id_list.includes(data.name)) {
			$(element).hide();
			return;
		} else {
			this.id_list.push(data.name);
		}

		$(element).append(this.get_item_html(data));

		// this['render_row_' + this.list_view.current_view](row, data);

		if (this.settings.post_render_item) {
			this.settings.post_render_item(this, element, data);
		}
	},

	// returns html for a data item,
	// usually based on a template
	get_item_html: function(data) {
		var main = frappe.render_template('list_item_main', {
			data: data,
			columns: this.columns,
			formatters: this.settings.formatters,
			subject: this.get_subject_html(data, true),
			indicator: this.get_indicator_html(data),
			right_column: this.settings.right_column
		});

		return frappe.render_template('list_item_row', {
			data: data,
			main: main,
			settings: this.settings,
			meta: this.meta,
			indicator_dot: this.get_indicator_dot(data),
			right_column: this.settings.right_column
		})
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
		if (data.modified)
			this.prepare_when(data, data.modified);

		// nulls as strings
		for (key in data) {
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

		var title_field = frappe.get_meta(this.doctype).title_field || 'name';
		data._title = strip_html(data[title_field]) || data.name;
		data._full_title = data._title;

		if (data._title.length > 35) {
			data._title = data._title.slice(0, 35) + '...';
		}

		data._workflow = null;
		if (this.workflow_state_fieldname) {
			data._workflow = {
				fieldname: this.workflow_state_fieldname,
				value: data[this.workflow_state_fieldname],
				style: frappe.utils.guess_style(data[this.workflow_state_fieldname])
			}
		}

		data._user = frappe.session.user;

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

		data._assign_list = JSON.parse(data._assign || '[]');

		// prepare data in settings
		if (this.settings.prepare_data)
			this.settings.prepare_data(data);

		return data;
	},

	prepare_when: function (data, date_str) {
		if (!date_str) date_str = data.modified;
		// when
		data.when = (dateutil.str_to_user(date_str)).split(' ')[0];
		var diff = dateutil.get_diff(dateutil.get_today(), date_str.split(' ')[0]);
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
	}
});
