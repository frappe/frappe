// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.views.get_listview = function(doctype, parent) {
	if(frappe.listviews[doctype]) {
		var listview = new frappe.listviews[doctype](parent);
	} else {
		var listview = new frappe.views.ListView(parent, doctype);
	}
	return listview;
}

// Renders customized list
// usually based on `in_list_view` property

frappe.views.ListView = Class.extend({
	init: function(doclistview, doctype) {
		this.doclistview = doclistview;
		this.doctype = doctype;
		this.meta = frappe.get_doc("DocType", this.doctype);
		this.settings = frappe.listview_settings[this.doctype] || {};
		if(this.meta.__listview_template) {
			this.template_name = doctype + "_listview";
			frappe.templates[this.template_name] = this.meta.__listview_template;
		}
		this.set_fields();
		this.set_columns();
		this.id_list = [];
		if(this.settings.group_by)
			this.group_by = this.settings.group_by;

		var me = this;
		this.doclistview.onreset = function() {
			me.id_list = [];
		}
		this.order_by = this.settings.order_by;
		this.group_by = this.settings.group_by;
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
			'modified_by', '_assign', '_liked_by', '_seen'],
		function(i, fieldname) { add_field(fieldname); })

		// add title field
		if(this.meta.title_field) {
			this.title_field = this.meta.title_field;
			add_field(this.meta.title_field);
		}

		// endabled / disabled
		if(frappe.meta.has_field(this.doctype, 'enabled')) { add_field('enabled'); };
		if(frappe.meta.has_field(this.doctype, 'disabled')) { add_field('disabled'); };

		// add workflow field (as priority)
		this.workflow_state_fieldname = frappe.workflow.get_state_fieldname(this.doctype);
		if(this.workflow_state_fieldname) {
			if (!frappe.workflow.workflows[this.doctype]["override_status"]) {
				add_field(this.workflow_state_fieldname);
			}
			this.stats.push(this.workflow_state_fieldname);
		}

		$.each(this.meta.fields, function(i,d) {
			if(d.in_list_view && frappe.perm.has_perm(me.doctype, d.permlevel, "read")) {
				if(d.fieldtype=="Image" && d.options) {
					add_field(d.options);
				} else {
					add_field(d.fieldname);
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
		var me = this;
		this.columns = [];
		var name_column = {
			colspan: this.settings.colwidths && this.settings.colwidths.subject || 6,
			type: "Subject",
			title: "Name"
		};
		if (this.meta.title_field) {
			name_column.title = frappe.meta.get_docfield(this.doctype, this.meta.title_field).label;
		}
		this.columns.push(name_column);
		this.total_colspans = this.columns[0].colspan;


		if(frappe.has_indicator(this.doctype)) {
			// indicator
			this.columns.push({
				colspan: this.settings.colwidths && this.settings.colwidths.indicator || 3,
				type: "Indicator",
				title: "Status"
			});
			this.total_colspans += this.columns[1].colspan;
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
			if(me.total_colspans < 12) {
				me.add_column(d);
			}
		});

		// additional columns
		if(this.settings.add_columns) {
			$.each(this.settings.add_columns, function(i, d) {
				if(me.total_colspans < 12) {
					if(typeof d==="string") {
						me.add_column(frappe.meta.get_docfield(me.doctype, d));
					} else {
						me.columns.push(d);
						me.total_colspans += parseInt(d.colspan);
					}
				}
			});
		}

		var empty_cols = flt(12 - this.total_colspans);
		while(empty_cols > 0) {
			for(var i=0, l=this.columns.length; i < l && empty_cols > 0; i++) {
				this.columns[i].colspan = cint(this.columns[i].colspan) + 1;
				empty_cols = empty_cols - 1;
			}
		}
	},
	add_column: function(df) {
		// field width
		var colspan = 3;
		if(in_list(["Int", "Percent"], df.fieldtype)) {
			colspan = 2;
		} else if(in_list(["Check", "Image"], df.fieldtype)) {
			colspan = 1;
		} else if(in_list(["name", "subject", "title"], df.fieldname)) { // subjects are longer
			colspan = 4;
		} else if(df.fieldtype=="Text Editor" || df.fieldtype=="Text") {
			colspan = 4;
		}
		if(df.columns && df.columns>0){
			colspan = df.columns;
		}
		else if(this.settings.column_colspan && this.settings.column_colspan[df.fieldname]) {
			colspan = this.settings.column_colspan[df.fieldname];
		}
		this.total_colspans += parseInt(colspan);
		var col = {
			colspan: colspan,
			content: df.fieldname,
			type: df.fieldtype,
			df:df,
			fieldtype: df.fieldtype,
			fieldname: df.fieldname,
			title:__(df.label)
		};
		if(this.settings.column_render && this.settings.column_render[df.fieldname]) {
			col.render = this.settings.column_render[df.fieldname];
		}
		this.columns.push(col);

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

		this['render_row_' + this.doclistview.current_view](row, data);

		if(this.settings.post_render_item) {
			this.settings.post_render_item(this, row, data);
		}

		this.render_tags(row, data);

	},
	render_row_List: function(row, data) {
		var main = frappe.render_template("list_item_main", {
			data: data,
			columns: this.columns,
			subject: this.get_avatar_and_id(data, true),
			list: this,
			right_column: this.settings.right_column
		});

		$(frappe.render_template("list_item_row", {
			data: data,
			main: main,
			list: this,
			right_column: this.settings.right_column
		})).appendTo(row);
	},
	render_row_Image: function(row, data) {
		this.allowed_type = [
			"Check", "Currency", "Data", "Date",
			"Datetime", "Float", "Int", "Link",
			"Percent", "Select", "Read Only", "Time"
		];
		var image_url = (data.image && window.cordova && data.image.indexOf('http')===-1) ?
			frappe.base_url + data.image : data.image;

		img_col = $(frappe.render_template("image_view_item_row", {
			data: data,
			list: this,
			columns: this.columns,
			allowed_type: this.allowed_type,
			item_image: image_url ? "url('" + image_url + "')" : null,
			color: frappe.get_palette(data.item_name),
			subject: this.get_avatar_and_id(data, true),
			right_column: this.settings.right_column
		}))
		.data("data", data)
		.appendTo($(row).find(".image-view-marker"));
	},
	render_tags: function(row, data) {
		var me = this;
		var row2 = $('<div class="tag-row">\
			<div class="list-tag xs-hidden"></div>\
			<div class="clearfix"></div>\
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
			list_sidebar: me.doclistview.list_sidebar,
			user_tags: data._user_tags,
			on_change: function(user_tags) {
				data._user_tags = user_tags;
				//me.render_timestamp_and_comments(row, data);
			}
		});
		tag_editor.wrapper.on("click", ".tagit-label", function() {
			me.doclistview.set_filter("_user_tags",
				$(this).text());
		});
	},

	get_avatar_and_id: function(data, without_workflow) {
		data._without_workflow = without_workflow;
		data.css_seen = '';

		if(data._seen) {
			var seen = JSON.parse(data._seen);
			if(seen && seen.indexOf(frappe.session.user) !== -1) {
				data.css_seen = 'seen'
			}
		}

		return frappe.render_template("list_item_subject", data);
	},

	get_indicator: function(doc) {
        var indicator = frappe.get_indicator(doc, this.doctype);
		if(indicator) {
	        return '<span class="indicator '+indicator[1]+' filterable" data-filter="'
				+indicator[2]+'">'+__(indicator[0])+'<span>';
		} else {
			return "";
		}
	},

	get_indicator_dot: function(doc) {
		var indicator = frappe.get_indicator(doc, this.doctype);
		if (!indicator) {
			return "";
		}
		return '<span class="indicator '+indicator[1]+'" title="'+__(indicator[0])+'"></span>';
	},

	prepare_data: function(data) {
		if(data.modified)
			this.prepare_when(data, data.modified);

		data._liked_by = data._liked_by ?
			JSON.parse(data._liked_by) : [];

		data._checkbox = (frappe.model.can_delete(this.doctype) || this.settings.selectable) && !this.no_delete

		data._doctype_encoded = encodeURIComponent(data.doctype);
		data._name = data.name.replace(/"/g, '\"');
		data._name_encoded = encodeURIComponent(data.name);
		data._submittable = frappe.model.is_submittable(this.doctype);

		data._title = strip_html(data[this.title_field || "name"] || data["name"]);
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
			data.when = comment_when(date_str);
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
