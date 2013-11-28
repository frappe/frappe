// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

wn.views.get_listview = function(doctype, parent) {	
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
		this.fields = [t + 'name', t + 'owner', t + 'docstatus', 
			t + '_user_tags', t + '_comments', t + 'modified', t + 'modified_by'];
		this.stats = ['_user_tags'];
		
		// add workflow field (as priority)
		this.workflow_state_fieldname = wn.workflow.get_state_fieldname(this.doctype);
		if(this.workflow_state_fieldname) {
			this.fields.push(t + this.workflow_state_fieldname);
			this.stats.push(this.workflow_state_fieldname);
		}
		
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
		
		$.each(wn.model.get("DocField", {"parent":this.doctype, "in_list_view":1}), 
			function(i,d) {
				if(in_list(overridden, d.fieldname)) {
					return;
				}
				// field width
				var colspan = "3";
				if(in_list(["Int", "Percent", "Select"], d.fieldtype)) {
					colspan = "2";
				} else if(d.fieldtype=="Check") {
					colspan = "1";
				} else if(in_list(["name", "subject", "title"], d.fieldname)) { // subjects are longer
					colspan = "4";
				} else if(d.fieldtype=="Text Editor" || d.fieldtype=="Text") {
					colspan = "4";
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

		// expand "name" if there are few columns
		var total_colspan = 0;
		$.each(this.columns, function(i, c) { total_colspan += cint(c.colspan); });
		if(total_colspan < 8) {
			$.each(this.columns, 
				function(i, c) { if(c.content==="name") { c.colspan = 4; return false; } });
		}
	},
	render: function(row, data) {
		this.prepare_data(data);
		//$(row).removeClass("list-row");
		
		
		// maintain id_list to avoid duplication incase
		// of filtering by child table
		if(in_list(this.id_list, data.name))
			return;
		else 
			this.id_list.push(data.name);
		
		
		var body = $('<div class="doclist-row row">\
			<div class="list-row-id-area col-sm-3" style="white-space: nowrap;\
				text-overflow: ellipsis; max-height: 30px"></div>\
			<div class="list-row-content-area col-sm-9"></div>\
		</div>').appendTo($(row).css({"position":"relative"})),
			colspans = 0,
			me = this;
		
		me.render_avatar_and_id(data, body.find(".list-row-id-area"))
		
		// make table
		$.each(this.columns, function(i, v) {
			var colspan = v.colspan || 3;
			colspans = colspans + flt(colspan)
						
			if(colspans <= 12) {
				var col = me.make_column(body.find(".list-row-content-area"), colspan);
				me.render_column(data, col, v);
			}
		});
		
		var comments = data._comments ? JSON.parse(data._comments) : [];
		var tags = $.map((data._user_tags || "").split(","), function(v) { return v ? v : null; });
		
		var timestamp_and_comment = 
			$('<div class="list-timestamp">')
				.appendTo(row)
				.html(""
					+ (tags.length ? (
							'<span style="margin-right: 10px;" class="list-tag-preview">' + tags.join(", ") + '</span>'
						): "")
					+ (comments.length ? 
						('<a style="margin-right: 10px;" href="#Form/'+
							this.doctype + '/' + data.name 
							+'" title="'+
							comments[comments.length-1].comment
							+'"><i class="icon-comments"></i> ' 
							+ comments.length + " " + (
								comments.length===1 ? wn._("comment") : wn._("comments")) + '</a>')
						: "")
					+ comment_when(data.modified));
		
		// row #2
		var row2 = $('<div class="row tag-row" style="margin-bottom: 5px;">\
			<div class="col-xs-12">\
				<div class="col-xs-3"></div>\
				<div class="col-xs-7">\
					<div class="list-tag xs-hidden"></div>\
					<div class="list-last-modified text-muted xs-visible"></div>\
				</div>\
			</div>\
		</div>').appendTo(row);
		
		// modified
		body.find(".list-last-modified").html(wn._("Last updated by") + ": " + wn.user_info(data.modified_by).fullname);		
		
		if(!me.doclistview.tags_shown) {
			row2.addClass("hide");
		}
		
		// add tags
		var tag_editor = new wn.ui.TagEditor({
			parent: row2.find(".list-tag"),
			frm: {
				doctype: this.doctype,
				docname: data.name
			},
			user_tags: data._user_tags
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
			.css({
				"white-space": "nowrap",
				"text-overflow": "ellipsis",
				"height": "30px",
				"padding-top":"3px"
			})
		return col;
	},
	render_avatar_and_id: function(data, parent) {
		if((wn.model.can_delete(this.doctype) || this.settings.selectable) && !this.no_delete) {
			$('<input class="list-delete" type="checkbox">')
				.data('name', data.name)
				.data('data', data)
				.css({"margin-right": "5px"})
				.appendTo(parent)
		}
		
		var $avatar = $(wn.avatar(data.modified_by, false, wn._("Modified by")+": " 
			+ wn.user_info(data.modified_by).fullname))
				.appendTo(parent)
				.css({"max-width": "100%"})


		if(wn.model.is_submittable(this.doctype)) {
			$(parent).append(repl('<span class="docstatus" style="margin-right: 3px;"> \
				<i class="%(docstatus_icon)s" \
				title="%(docstatus_title)s"></i></span>', data));			
		}

		$("<a>")
			.attr("href", "#Form/" + data.doctype + "/" + encodeURIComponent(data.name))
			.html(data.name)
			.appendTo(parent.css({"overflow":"hidden"}));
		
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
						"max-width": "100%",
						"max-height": "30px"
					})
					.appendTo(parent);
		}
		else if(opts.type=="select" && data[opts.content]) {
			
			var label_class = "label-default";

			var style = wn.utils.guess_style(data[opts.content]);
			if(style) label_class = "label-" + style;
			
			$("<span>" 
				+ data[opts.content] + "</span>")
				.css({"cursor":"pointer"})
				.addClass("label")
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
			data.docstatus_icon = 'icon-check-empty';
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
	
	render_bar_graph: function(parent, data, field, label) {
		var args = {
			percent: data[field],
			label: label
		}
		$(parent).append(repl('<span class="progress" style="width: 100%; float: left; margin: 5px 0px;"> \
			<span class="progress-bar" title="%(percent)s% %(label)s" \
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