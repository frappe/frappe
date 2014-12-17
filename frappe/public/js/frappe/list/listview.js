// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.views.get_listview = function(doctype, parent) {
	if(frappe.listviews[doctype]) {
		var listview = new frappe.listviews[doctype](parent);
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
			'modified_by', '_assign', '_starred_by'],
		function(i, fieldname) { add_field(fieldname); })

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
		this.columns.push({
			colspan: colspan,
			content: df.fieldname,
			type: df.fieldtype,
			df:df,
			fieldtype: df.fieldtype,
			fieldname: df.fieldname,
			title:__(df.label)
		});

	},
	render: function(row, data) {
		this.prepare_data(data);

		// maintain id_list to avoid duplication incase
		// of filtering by child table
		if(in_list(this.id_list, data.name)) {
			$(row).toggle(false);
			return;
		} else {
			this.id_list.push(data.name);
		}


		if(this.template) {
			var main = frappe.render(this.template, {doc: frappe.get_format_helper(data), list: this });
		} else {
			var main = frappe.render(frappe.templates.list_item_standard, {
				data: data,
				columns: this.columns,
				subject: this.get_avatar_and_id(data, true),
				subject_cols: 4 + this.shift_right
			});
		}

		$(frappe.render(frappe.templates.list_item_row, {data: data, main: main})).appendTo(row);

		this.render_tags(row, data);

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
				//me.render_timestamp_and_comments(row, data);
			}
		});
		tag_editor.$w.on("click", ".tagit-label", function() {
			me.doclistview.set_filter("_user_tags",
				$(this).text());
		});
	},

	get_avatar_and_id: function(data, without_workflow) {
		data._without_workflow = without_workflow;
		return frappe.render(frappe.templates.list_item_subject, data);
	},

	prepare_data: function(data) {
		if(data.modified)
			this.prepare_when(data, data.modified);

		data._starred_by = data._starred_by ?
			JSON.parse(data._starred_by) : [];

		data._checkbox = (frappe.model.can_delete(this.doctype) || this.settings.selectable) && !this.no_delete

		data._doctype_encoded = encodeURIComponent(data.doctype);
		data._name = data.name.replace(/"/g, '\"');
		data._name_encoded = encodeURIComponent(data.name);
		data._submittable = frappe.model.is_submittable(this.doctype);

		data._title = data[this.title_field || "name"];
		data._full_title = data._title;

		if(data._title.length > 40) {
			data._title = data._title.slice(0, 40) + "...";
		}

		data._workflow = null;
		if(this.workflow_state_fieldname) {
			data._workflow = {
				fieldname: this.workflow_state_fieldname,
				value: data[this.workflow_state_fieldname],
				style: frappe.utils.guess_style(data[this.workflow_state_fieldname])
			}
		}
		data._user = user;

		data._comments_list = data._comments ? JSON.parse(data._comments) : [];
		data._tags = $.map((data._user_tags || "").split(","),
			function(v) { return v ? v : null; });
		data._assign_list = data._assign ? JSON.parse(data._assign) : [];

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
