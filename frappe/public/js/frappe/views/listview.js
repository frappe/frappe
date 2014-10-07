// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.views.get_listview = function(doctype, parent) {
	if(frappe.doclistviews[doctype]) {
		var listview = new frappe.doclistviews[doctype](parent);
	} else {
		var listview = new frappe.views.ListView(parent, doctype);
	}
	return listview;
}

frappe.provide("frappe.listview_settings");
frappe.provide("frappe.listview_parent_route");

frappe.views.ListView = Class.extend({
	init: function(doclistview, doctype) {
		this.doclistview = doclistview;
		this.doctype = doctype;
		this.meta = frappe.get_doc("DocType", this.doctype);
		this.settings = frappe.listview_settings[this.doctype] || {};
		this.template = this.meta.__listview_template || null;
		this.set_fields();
		this.set_columns();
		this.id_list = [];
		if(this.settings.group_by)
			this.group_by = this.settings.group_by;

		var me = this;
		this.doclistview.onreset = function() {
			me.id_list = [];
		}
	},
	set_fields: function() {
		var me = this;
		var t = "`tab"+this.doctype+"`.";
		this.fields = [];
		this.stats = ['_user_tags'];

		var add_field = function(fieldname) {
			field = t + "`" + fieldname + "`"
			if(me.fields.indexOf(field)=== -1)
				me.fields.push(field);
		}

		$.each(['name', 'owner', 'docstatus', '_user_tags', '_comments', 'modified',
			'modified_by', '_assign'], function(i, fieldname) { add_field(fieldname); })

		// add title field
		if(this.meta.title_field) {
			this.title_field = this.meta.title_field;
			add_field(this.meta.title_field);
		}

		// add workflow field (as priority)
		this.workflow_state_fieldname = frappe.workflow.get_state_fieldname(this.doctype);
		if(this.workflow_state_fieldname) {
			add_field(this.workflow_state_fieldname);
			this.stats.push(this.workflow_state_fieldname);
		}

		$.each(this.meta.fields, function(i,d) {
			if(d.in_list_view && frappe.perm.has_perm(me.doctype, d.permlevel, "read")) {
				if(d.fieldtype=="Image" && d.options) {
					add_field(d.options);
				} else {
					add_field(d.fieldname);
				}

				if(d.fieldtype=="Select") {
					if(me.stats.indexOf(d.fieldname)===-1) me.stats.push(d.fieldname);
				}

				// currency field for symbol (multi-currency)
				if(d.fieldtype=="Currency" && d.options) {
					if(d.options.indexOf(":")!=-1) {
						add_field(d.options.split(":")[1]);
					} else {
						add_field(d.options);
					};
				}
			}
		});

		// additional fields
		if(this.settings.add_fields) {
			$.each(this.settings.add_fields, function(i, d) {
				if(d.indexOf("`tab")===-1) {
					d = "`tab" + me.doctype + "`." + d;
				}
				if(me.fields.indexOf(d)==-1)
					me.fields.push(d);
			});
		}
	},
	set_columns: function() {
		this.columns = [];
		this.total_colspans = 0;
		var me = this;
		if(this.workflow_state_fieldname) {
			this.columns.push({
				colspan: 3,
				content: this.workflow_state_fieldname,
				type:"select"
			});
		}

		// overridden
		var overridden = $.map(this.settings.add_columns || [], function(d) {
			return d.content;
		});
		var docfields_in_list_view = frappe.get_children("DocType", this.doctype, "fields",
			{"in_list_view":1}).sort(function(a, b) { return a.idx - b.idx })

		$.each(docfields_in_list_view, function(i,d) {
			if(in_list(overridden, d.fieldname) || d.fieldname === me.title_field) {
				return;
			}
			me.add_column(d);
		});

		// additional columns
		if(this.settings.add_columns) {
			$.each(this.settings.add_columns, function(i, d) {
				if(typeof d==="string") {
					me.add_column(frappe.meta.get_docfield(me.doctype, d));
				} else {
					me.columns.push(d);
					me.total_colspans += parseInt(d.colspan);
				}
			});
		}

		var empty_cols = flt(12 - this.total_colspans);
		this.shift_right = cint(empty_cols * 0.6667);
		if(this.shift_right < 0) {
			this.shift_right = 0;
		} else if (this.shift_right > 1) {
			// expand each column so that it fills up empty_cols
			$.each(this.columns, function(i, c) {
				c.colspan = cint(empty_cols / me.columns.length) + cint(c.colspan);
			})
		}

	},
	add_column: function(df) {
		// field width
		var colspan = "3";
		if(in_list(["Int", "Percent", "Select"], df.fieldtype)) {
			colspan = "2";
		} else if(df.fieldtype=="Check") {
			colspan = "1";
		} else if(in_list(["name", "subject", "title"], df.fieldname)) { // subjects are longer
			colspan = "4";
		} else if(df.fieldtype=="Text Editor" || df.fieldtype=="Text") {
			colspan = "4";
		}
		this.total_colspans += parseInt(colspan);
		this.columns.push({colspan: colspan, content: df.fieldname,
			type:df.fieldtype, df:df, title:__(df.label) });

	},
	render: function(row, data) {
		this.prepare_data(data);

		$(row).css({"position": "relative"});


		// maintain id_list to avoid duplication incase
		// of filtering by child table
		if(in_list(this.id_list, data.name)) {
			$(row).toggle(false);
			return;
		} else {
			this.id_list.push(data.name);
		}

		if(this.template) {
			this.render_template(row, data);
		} else {
			this.render_standard_columns(row, data);
		}

		this.render_timestamp_and_comments(row, data);
		this.render_tags(row, data);

	},

	render_template: function (row, data) {
		$(frappe.render(this.template, {
			doc: frappe.get_format_helper(data),
			list: this
		})).appendTo($('<div class="doclist-row"></div>').appendTo(row));
	},

	render_standard_columns: function(row, data) {
		var left_cols = 4 + this.shift_right,
			right_cols = 8 - this.shift_right,
			body = $('<div class="doclist-row row">\
				<div class="list-row-id-area col-sm-'+left_cols+'" style="white-space: nowrap;\
					text-overflow: ellipsis; max-height: 30px"></div>\
				<div class="list-row-content-area col-sm-'+right_cols+'"></div>\
			</div>').appendTo(row),
			colspans = 0,
			me = this;

		$(me.get_avatar_and_id(data, true)).appendTo(body.find(".list-row-id-area"));

		// make table
		$.each(this.columns, function(i, v) {
			var colspan = v.colspan || 3;
			colspans = colspans + flt(colspan)

			if(colspans <= 12) {
				var col = me.make_column(body.find(".list-row-content-area"),
					colspan);
				me.render_column(data, col, v);
			}
		});

	},

	render_timestamp_and_comments: function(row, data) {
		var comments = data._comments ? JSON.parse(data._comments) : [],
			tags = $.map((data._user_tags || "").split(","),
				function(v) { return v ? v : null; }),
			assign = data._assign ? JSON.parse(data._assign) : [],
			me = this;

		if(me.title_field && data[me.title_field]!==data.name) {
			$('<div class="list-doc-name">')
				.appendTo(row)
				.css({"left": me.title_offset_left})
				.html('<a href="#Form/'+ data.doctype+'/'+data.name +'">#' + data.name + "</a>");
		}

		$(row).find(".list-timestamp").remove();

		var timestamp_and_comment =
			$('<div class="list-timestamp">')
				.appendTo(row)
				.html(frappe.render(frappe.templates.list_info_template, {
					"tags": tags,
					"comments": comments,
					"assign": assign,
					"data": data,
					"doctype": this.doctype
				}));
	},

	render_tags: function(row, data) {
		var me = this;
		var row2 = $('<div class="row tag-row" style="margin-bottom: 5px;">\
			<div class="col-xs-12">\
				<div class="col-xs-3"></div>\
				<div class="col-xs-7">\
					<div class="list-tag xs-hidden"></div>\
				</div>\
			</div>\
		</div>').appendTo(row);

		if(!me.doclistview.tags_shown) {
			row2.addClass("hide");
		}

		// add tags
		var tag_editor = new frappe.ui.TagEditor({
			parent: row2.find(".list-tag"),
			frm: {
				doctype: this.doctype,
				docname: data.name
			},
			user_tags: data._user_tags,
			on_change: function(user_tags) {
				data._user_tags = user_tags;
				me.render_timestamp_and_comments(row, data);
			}
		});
		tag_editor.$w.on("click", ".tagit-label", function() {
			me.doclistview.set_filter("_user_tags",
				$(this).text());
		});
	},

	make_column: function(body, colspan) {
		var col = $("<div class='col'>")
			.appendTo(body)
			.addClass("col-sm-" + cint(colspan))
			.addClass("col-xs-" + (cint(colspan) + 2))
			.css({
				"white-space": "nowrap",
				"text-overflow": "ellipsis",
				"height": "30px",
				"padding-top":"3px"
			})
		return col;
	},
	get_avatar_and_id: function(data, without_workflow) {
		this.title_offset_left = 15;

		var html = "";

		// checkbox
		if((frappe.model.can_delete(this.doctype) || this.settings.selectable) && !this.no_delete) {
			html += '<input class="list-delete" type="checkbox"\
				 style="margin-right: 5px;">';

			this.title_offset_left += 13 + 5;
		}

		// avatar
		var user_for_avatar = data.user_for_avatar || data.modified_by;
		html += frappe.avatar(user_for_avatar, false, __("Modified by")+": "
			+ frappe.user_info(user_for_avatar).fullname)

		this.title_offset_left += 30 + 5;

		// docstatus lock
		if(frappe.model.is_submittable(this.doctype)) {
			html += repl('<span class="docstatus filterable" style="margin-right: 3px;"\
				data-filter="docstatus,=,%(docstatus)s"> \
				<i class="%(docstatus_icon)s icon-fixed-width" \
				title="%(docstatus_title)s"></i></span>', data);

				this.title_offset_left += 15 + 4;
		}

		// title
		var full_title = data[this.title_field || "name"], title = full_title;
		if(full_title.length > 40) {
			title = full_title.slice(0, 40) + "...";
		}
		html += repl('<a class="form-link list-id" style="margin-left: 5px; margin-right: 8px;" \
			href="#Form/%(doctype)s/%(name)s" title="%(full_title)s">%(title)s</a>', {
				doctype: data.doctype,
				name: encodeURIComponent(data.name),
				title: title,
				full_title: full_title,
			});

		this.title_offset_left += 5;

		if(!without_workflow && this.workflow_state_fieldname) {
			html+= repl('<span class="label label-%(style)s filterable" data-filter="%(fieldname)s,=,%(value)s">\
				%(value)s</span>', {
					fieldname: this.workflow_state_fieldname,
					value: data[this.workflow_state_fieldname],
					style: frappe.utils.guess_style(data[this.workflow_state_fieldname])
				});
		}

		return html;
	},

	render_column: function(data, parent, opts) {
		var me = this;
		if(opts.type) opts.type= opts.type.toLowerCase();

		// style
		if(opts.css) {
			$.each(opts.css, function(k, v) { $(parent).css(k, v)});
		}

		// multiple content
		if(opts.content.indexOf && opts.content.indexOf('+')!=-1) {
			$.map(opts.content.split('+'), function(v) {
				me.render_column(data, parent, {content:v, title: opts.title});
			});
			return;
		}

		// content
		if(typeof opts.content=='function') {
			opts.content(parent, data, me);
		}
		else if(opts.content=='check') {
		}
		else if(opts.type=='bar-graph' || opts.type=="percent") {
			this.render_bar_graph(parent, data, opts.content, opts.label);
		}
		else if(opts.template) {
			$(parent).append(repl(opts.template, data));
		}
		else if(opts.type=="date" && data[opts.content]) {
			$("<span>")
				.html(frappe.datetime.str_to_user(data[opts.content]))
				.css({"color":"#888"})
				.appendTo(parent);
		}
		else if(opts.type=="image") {
			data[opts.content] = data[opts.df.options];
			if(data[opts.content])
				$("<img>")
					.attr("src", frappe.utils.get_file_link(data[opts.content]))
					.css({
						"max-width": "100%",
						"max-height": "30px"
					})
					.appendTo(parent);
		}
		else if(opts.type=="select" && data[opts.content]) {

			var label_class = "label-default";

			var style = frappe.utils.guess_style(data[opts.content]);
			if(style) label_class = "label-" + style;

			$("<span>"
				+ data[opts.content] + "</span>")
				.css({"cursor":"pointer"})
				.addClass("label")
				.addClass("filterable")
				.addClass(label_class)
				.attr("data-filter", opts.df.fieldname + ",=," + data[opts.content])
				.appendTo(parent.css({"overflow":"hidden"}));
		}
		else if(opts.type=="link" && data[opts.content]) {
			$("<span>")
				.html(frappe.format(data[opts.content], opts.df, null, data))
				.appendTo(parent.css({"overflow":"hidden"}))
				.click(function() {
					me.doclistview.set_filter($(this).attr("data-fieldname"),
						$(this).attr("data-value"));
					return false;
				})
				.attr("data-fieldname", opts.content)
				.attr("data-value", data[opts.content])
				.find("a").removeAttr("href");

		}
		else if(data[opts.content]) {
			$("<span>")
				.html(frappe.format(data[opts.content], opts.df, null, data))
				.appendTo(parent.css({"overflow":"hidden"}))
		}

		// finally
		if(!$(parent).html()) {
			$("<span>-</span>").css({color:"#ccc"}).appendTo(parent);
		}

		// title
		if(!in_list(["avatar", "_user_tags", "check"], opts.content)) {
			if($(parent).attr("title")==undefined) {
				$(parent).attr("title", (opts.title || opts.content) + ": "
					+ (data[opts.content] || __("Not Set")))
			}
			$(parent).tooltip();
		}

	},
	show_hide_check_column: function() {
		if(!this.doclistview.can_delete) {
			this.columns = $.map(this.columns, function(v, i) { if(v.content!='check') return v });
		}
	},
	prepare_data: function(data) {

		if(data.modified)
			this.prepare_when(data, data.modified);

		// docstatus
		if(data.docstatus==0 || data.docstatus==null) {
			data.docstatus_icon = 'icon-edit text-danger';
			data.docstatus_title = __('Editable');
		} else if(data.docstatus==1) {
			data.docstatus_icon = 'icon-lock';
			data.docstatus_title = __('Submitted');
		} else if(data.docstatus==2) {
			data.docstatus_icon = 'icon-ban-circle';
			data.docstatus_title = __('Cancelled');
		}

		// nulls as strings
		for(key in data) {
			if(data[key]==null) {
				data[key]='';
			}
		}

		// prepare data in settings
		if(this.settings.prepare_data)
			this.settings.prepare_data(data);
	},

	prepare_when: function(data, date_str) {
		if (!date_str) date_str = data.modified;
		// when
		data.when = (dateutil.str_to_user(date_str)).split(' ')[0];
		var diff = dateutil.get_diff(dateutil.get_today(), date_str.split(' ')[0]);
		if(diff==0) {
			data.when = dateutil.comment_when(date_str);
		}
		if(diff == 1) {
			data.when = __('Yesterday')
		}
		if(diff == 2) {
			data.when = __('2 days ago')
		}
	},

	render_bar_graph: function(parent, data, field, label) {
		var args = {
			percent: data[field],
			label: __(label)
		}
		$(parent).append(repl('<span class="progress" style="width: 100%; float: left; margin: 5px 0px;"> \
			<span class="progress-bar" title="%(percent)s% %(label)s" \
				style="width: %(percent)s%;"></span>\
		</span>', args));
	},
	render_icon: function(parent, icon_class, label) {
		var icon_html = "<i class='%(icon_class)s' title='%(label)s'></i>";
		$(parent).append(repl(icon_html, {icon_class: icon_class, label: __(label) || ''}));
	}
});

// embeddable
frappe.provide('frappe.views.RecordListView');
frappe.views.RecordListView = frappe.views.DocListView.extend({
	init: function(doctype, wrapper, ListView) {
		this.doctype = doctype;
		this.wrapper = wrapper;
		this.listview = new ListView(this, doctype);
		this.listview.parent = this;
		this.setup();
	},

	setup: function() {
		var me = this;
		me.page_length = 10;
		$(me.wrapper).empty();
		me.init_list();
	},

	get_args: function() {
		var args = this._super();
		$.each((this.default_filters || []), function(i, f) {
		      args.filters.push(f);
		});
		args.docstatus = args.docstatus.concat((this.default_docstatus || []));
		return args;
	},
});
