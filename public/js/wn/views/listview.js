// Copyright 2013 Web Notes Technologies Pvt Ltd
// License: MIT. See license.txt

wn.views.get_listview = function(doctype, parent) {
	var meta = locals.DocType[doctype];
	
	if(wn.doclistviews[doctype]) {
		var listview = new wn.doclistviews[doctype](parent);
	} else {
		var listview = new wn.views.ListView(parent, doctype);
	}
	return listview;
}

wn.provide("wn.listview_settings");
wn.views.ListView = Class.extend({
	init: function(doclistview, doctype) {
		this.doclistview = doclistview;
		this.doctype = doctype;
		this.settings = wn.listview_settings[this.doctype] || {};		
		this.set_fields();
		this.set_columns();
		if(this.settings.group_by) 
			this.group_by = this.settings.group_by;
	},
	set_fields: function() {
		var me = this;
		var t = "`tab"+this.doctype+"`.";
		this.fields = [t + 'name', t + 'owner', t + 'docstatus', 
			t + '_user_tags', t + 'modified', t + 'modified_by'];
		this.stats = ['_user_tags'];
		
		
		$.each(wn.model.get("DocField", {"parent":this.doctype, "in_list_view":1}), function(i,d) {
			if(wn.perm.has_perm(me.doctype, d.permlevel, READ)) {
				if(d.fieldtype=="Image" && d.options) {
					me.fields.push(t + "`" + d.options + "`");
				} else {
					me.fields.push(t + "`" + d.fieldname + "`");
				}

				if(d.fieldtype=="Select") {
					me.stats.push(d.fieldname);
				}

				// currency field for symbol (multi-currency)
				if(d.fieldtype=="Currency" && d.options) {
					if(d.options.indexOf(":")!=-1) {
						me.fields.push(t + "`" + d.options.split(":")[1] + "`");
					} else {
						me.fields.push(t + "`" + d.options + "`");
					};
				}
			}
		});

		// additional fields
		if(this.settings.add_fields) {
			$.each(this.settings.add_fields, function(i, d) {
				if(me.fields.indexOf(d)==-1)
					me.fields.push(d);
			});
		}
	},
	set_columns: function() {
		this.columns = [];
		var me = this;
		if(wn.model.can_delete(this.doctype) || this.settings.selectable) {
			this.columns.push({colspan: 0.5, content:'check'})
		}
		this.columns.push({colspan: 1, content:'avatar'});
		if(wn.model.is_submittable(this.doctype)) {
			this.columns.push({colspan: 0.5, content:'docstatus'});
		}
		this.columns.push({colspan: 2, content:'name'});

		// overridden
		var overridden = $.map(this.settings.add_columns || [], function(d) { 
			return d.content;
		});
		
		$.each(wn.model.get("DocField", {"parent":this.doctype, "in_list_view":1}), 
			function(i,d) {
				if(in_list(overridden, d.fieldname)) {
					return;
				}
				// field width
				var colspan = "2";
				if(in_list(["Int", "Percent"], d.fieldtype)) {
					colspan = "1";
				} else if(d.fieldtype=="Check" || d.fieldname=="file_list") {
					colspan = "1";
				} else if(d.fieldname=="subject") { // subjects are longer
					colspan = "3";
				}
				me.columns.push({colspan: colspan, content: d.fieldname, 
					type:d.fieldtype, df:d, title:wn._(d.label) });
		});

		// additional columns
		if(this.settings.add_columns) {
			$.each(this.settings.add_columns, function(i, d) {
				me.columns.push(d);
			});
		}

		// tags
		this.columns.push({colspan: 2, content:'tags', css: {'color':'#aaa'}}),

		this.columns.push({colspan: 2, content:'modified', 
			css: {'text-align': 'right', 'color':'#222'}});

		
	},
	render: function(row, data) {
		this.prepare_data(data);
		var body = $("<div class='row doclist-row'></div>")
			.appendTo(row).css({"padding": "5px 0px", 
				"margin-bottom": "7px", 
				"border-bottom": "1px solid #f2f2f2"
			}),
			colspans = 0,
			me = this;
			
		// make table
		$.each(this.columns, function(i, v) {
			var colspan = v.colspan || 2;
			colspans = colspans + flt(colspan)
			
			if(colspans <= 8) {
				var col = me.make_column(body, flt(colspan) > 1 ? flt(colspan) * 2 : colspan)
					.addClass("visible-sm");
				me.render_column(data, col, v);
			}
			
			if(colspans <= 12) {
				var col = me.make_column(body, colspan)
					.addClass("hidden-sm");
				me.render_column(data, col, v);
			}
		});
	},
	make_column: function(body, colspan) {
		colspan = colspan==0.5 ? "50" : colspan;
		var col = $("<div>")
			.appendTo(body)
			.addClass("col col-lg-" + colspan)
			.css({
				"white-space": "nowrap",
				"text-overflow": "ellipsis",
				"max-height": "30px",
				"padding-right": "0px"
			})
		return col;
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
		else if(opts.content=='name') {
			$("<a>")
				.attr("href", "#Form/" + data.doctype + "/" + data.name)
				.html(data.name)
				.appendTo(parent.css({"overflow":"hidden"}));
		} 
		else if(opts.content=='avatar' || opts.content=='avatar_modified') {
			$(parent).append(wn.avatar(data.owner, false, wn._("Modified by")+": " 
				+ wn.user_info(data.modified_by).fullname))
				.css({"margin-top": "-5px"});
		}
		else if(opts.content=='check') {
			$('<input class="list-delete" type="checkbox">')
				.data('name', data.name)
				.data('data', data)
				.appendTo(parent)
		}
		else if(opts.content=='docstatus') {
			$(parent).append(repl('<span class="docstatus"> \
				<i class="%(docstatus_icon)s" style="font-size: 120%;" \
				title="%(docstatus_title)s"></i></span>', data));			
		}
		else if(opts.content=='tags') {
			this.add_user_tags(parent, data);
		}
		else if(opts.content=='modified') {
			$("<span>")
				.html(data.when)
				.appendTo(parent)
				.attr("title", wn._("Last Modified On"))
				.css({"color":"#888"})
		}
		else if(opts.type=='bar-graph' || opts.type=="percent") {
			this.render_bar_graph(parent, data, opts.content, opts.label);
		}
		else if(opts.template) {
			$(parent).append(repl(opts.template, data));
		} 
		else if(opts.type=="date" && data[opts.content]) {
			$("<span>")
				.html(wn.datetime.str_to_user(data[opts.content]))
				.css({"color":"#888"})
				.appendTo(parent);
		}
		else if(opts.type=="image") {
			data[opts.content] = data[opts.df.options];
			if(data[opts.content])
				$("<img>")
					.attr("src", wn.utils.get_file_link(data[opts.content]))
					.css({
						"max-width": "100px",
						"max-height": "30px"
					})
					.appendTo(parent);
		}
		else if(opts.type=="select" && data[opts.content]) {
			
			var label_class = "";

			var style = wn.utils.guess_style(data[opts.content]);
			if(style) label_class = "label-" + style;
			
			$("<span class='label'>" 
				+ data[opts.content] + "</span>")
				.css({"cursor":"pointer"})
				.addClass(label_class)
				.attr("data-fieldname", opts.content)
				.click(function() {
					me.doclistview.set_filter($(this).attr("data-fieldname"), 
						$(this).text());
				})
				.appendTo(parent.css({"overflow":"hidden"}));
		}
		else if(data[opts.content]) {
			$("<span>")
				.html(wn.format(data[opts.content], opts.df, null, data))
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
					+ (data[opts.content] || "Not Set"))
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
			data.docstatus_icon = '';
			data.docstatus_title = wn._('Editable');
		} else if(data.docstatus==1) {
			data.docstatus_icon = 'icon-lock';			
			data.docstatus_title = wn._('Submitted');
		} else if(data.docstatus==2) {
			data.docstatus_icon = 'icon-remove';			
			data.docstatus_title = wn._('Cancelled');
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
			data.when = wn._('Yesterday')
		}
		if(diff == 2) {
			data.when = wn._('2 days ago')
		}
	},
	
	add_user_tags: function(parent, data) {
		var me = this;
		if(data._user_tags) {
			$.each(data._user_tags.split(','), function(i, t) {
				if(t) {
					$('<span class="label" style="cursor: pointer;">' 
						+ strip(t) + '</span>')
						.click(function() {
							me.doclistview.set_filter('_user_tags', $(this).text())
						})
						.appendTo(parent);
				}
			});
		}		
	},
	render_bar_graph: function(parent, data, field, label) {
		var args = {
			percent: data[field],
			fully_delivered: (data[field] > 99 ? 'bar-complete' : ''),
			label: label
		}
		$(parent).append(repl('<span class="bar-outer" style="width: 30px; float: right"> \
			<span class="bar-inner %(fully_delivered)s" title="%(percent)s% %(label)s" \
				style="width: %(percent)s%;"></span>\
		</span>', args));
	},
	render_icon: function(parent, icon_class, label) {
		var icon_html = "<i class='%(icon_class)s' title='%(label)s'></i>";
		$(parent).append(repl(icon_html, {icon_class: icon_class, label: label || ''}));
	}
});

// embeddable
wn.provide('wn.views.RecordListView');
wn.views.RecordListView = wn.views.DocListView.extend({
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