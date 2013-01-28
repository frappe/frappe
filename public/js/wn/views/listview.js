// Copyright 2013 Web Notes Technologies Pvt Ltd
// License: MIT. See license.txt

wn.views.get_listview = function(doctype, parent) {
	var meta = locals.DocType[doctype];
	if(meta.__listjs) {
		eval(meta.__listjs);
		var listview = new wn.doclistviews[doctype](parent);
	} else {
		var listview = new wn.views.ListView(parent);
	}
	return listview;
}

wn.views.ListView = Class.extend({
	columns: [],
	init: function(doclistview) {
		var me = this;
		this.doclistview = doclistview;
		this.doctype = doclistview.doctype;
		
		var t = "`tab"+this.doctype+"`.";
		this.fields = [t + 'name', t + 'owner', t + 'docstatus', 
			t + '_user_tags', t + 'modified', t + 'modified_by'];
		this.stats = ['_user_tags'];
			
		$.each(wn.model.get("DocField", {"parent":this.doctype, "in_list_view":1}), function(i,d) {
			me.fields.push(t + "`" + d.fieldname + "`");
			if(d.fieldtype=="Select") {
				me.stats.push(d.fieldname);
			}
		});
			
		if(!this.columns.length) {
			this.set_columns();
		}

	},
	set_columns: function() {
		var me = this;
		if(wn.model.can_delete(this.doctype)) {
			this.columns.push({width: '3%', content:'check'})
		}
		this.columns.push({width: '4%', content:'avatar'});
		if(wn.model.is_submittable(this.doctype)) {
			this.columns.push({width: '3%', content:'docstatus', 
				css: {"text-align": "center"}});
		}
		this.columns.push({width: '20%', content:'name'});

		$.each(wn.model.get("DocField", {"parent":this.doctype, "in_list_view":1}), function(i,d) {
			
			// field width
			var width = "15%";
			if(in_list(["Select", "Date", "Int"], d.fieldtype)) {
				width = "10%";
			} else if(d.fieldtype=="Check" || d.fieldname=="file_list") {
				width = "5%";
			} else if(d.fieldname=="subject") { // subjects are longer
				width = "20%";
			}
			me.columns.push({width:width, content: d.fieldname, 
				type:d.fieldtype, df:d, title:wn._(d.label) });
		});

		// tags
		this.columns.push({width: '15%', content:'tags', css: {'color':'#aaa'}}),

		this.columns.push({width: '15%', content:'modified', 
			css: {'text-align': 'right', 'color':'#222'}});

		
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
				.appendTo(parent);
		} 
		else if(opts.content=='avatar' || opts.content=='avatar_modified') {
			$(parent).append(wn.avatar(data.owner, false, wn._("Modified by")+": " 
				+ wn.user_info(data.modified_by).fullname));
		}
		else if(opts.content=='check') {
			$(parent).append('<input class="list-delete" type="checkbox">');
			$(parent).find('input').data('name', data.name);			
		}
		else if(opts.content=='docstatus') {
			$(parent).append(repl('<span class="docstatus"> \
				<i class="%(docstatus_icon)s" \
				title="%(docstatus_title)s"></i></span>', data));			
		}
		else if(opts.content=='enabled') {
			data.icon = cint(data.enabled) ? "icon-check" : "icon-check-empty";
			data.title = cint(data.enabled) ? wn._("Enabled") : wn._("Disabled");
			$(parent).append(repl('<span class="docstatus"> \
				<i class="%(icon)s" title="%(title)s"></i></span>', data));			
		}
		else if(opts.content=='disabled') {
			data.icon = cint(data.disabled) ? "icon-check-empty" : "icon-check"
			data.title = cint(data.disabled) ? wn._("Disabled") : wn._("Enabled");
			$(parent).append(repl('<span class="docstatus"> \
				<i class="%(icon)s"></i></span>', data));			
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
		else if(opts.content=="file_list") {
			if(data[opts.content]) {
				$("<i class='icon-paper-clip'>").appendTo(parent);
			}
		}
		else if(opts.type=='bar-graph') {
			this.render_bar_graph(parent, data, opts.content, opts.label);
		}
		else if(opts.type=='link' && (opts.df ? opts.df.options : opts.doctype)) {
			var doctype = (opts.df ? opts.df.options : opts.doctype);
			$(parent).append(repl('<a href="#Form/'+ doctype +'/'
				+data[opts.content]+'">'+data[opts.content]+'</a>', data));
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
		else if(opts.type=="select" && data[opts.content]) {
			
			var label_class = "";
			if(in_list(["Open", "Pending"], data[opts.content])) {
				label_class = "label-important";
			} else if(in_list(["Closed", "Finished", "Converted"], data[opts.content])) {
				label_class = "label-success";
			}
			
			$("<span class='label'>" 
				+ data[opts.content] + "</span>")
				.css({"cursor":"pointer"})
				.addClass(label_class)
				.attr("data-fieldname", opts.content)
				.click(function() {
					me.doclistview.set_filter($(this).attr("data-fieldname"), 
						$(this).text());
				})
				.appendTo(parent);
		}
		else if(opts.type=="currency") {
			$(parent).append(format_currency(data[opts.content], opts.df));
		}
		else if(data[opts.content]) {
			$("<span>")
				.html(data[opts.content])
				.appendTo(parent)
		} 
		
		// finally
		if(!$(parent).html()) {
			$("<span>-</span>").css({color:"#ccc"}).appendTo(parent);
		}
		
		// title
		$(parent).attr("title", (opts.title || opts.content) + ":" 
			+ (data[opts.content] || "Not Set"));
		
	},
	render: function(row, data) {
		var me = this;
		this.prepare_data(data);
		rowhtml = '';
				
		// make table
		$.each(this.columns, function(i, v) {
			if(v.content && v.content.substr && v.content.substr(0,6)=="avatar") {
				rowhtml += repl('<td style="width: 40px;"></td>');				
			} else {
				rowhtml += repl('<td style="width: %(width)s"></td>', v);
			}
		});
		var tr = $(row).html('<table class="doclist-row"><tbody><tr>' + rowhtml + '</tr></tbody></table>').find('tr').get(0);
		
		// render cells
		$.each(this.columns, function(i, v) {
			me.render_column(data, tr.cells[i], v);
		});
	},
	prepare_data: function(data) {
		if(data.modified)
			this.prepare_when(data, data.modified);
		
		// docstatus
		if(data.docstatus==0 || data.docstatus==null) {
			data.docstatus_icon = 'icon-pencil';
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
		$(parent).append(repl('<span class="bar-outer" style="width: 30px; float: right" \
			title="%(percent)s% %(label)s">\
			<span class="bar-inner %(fully_delivered)s" \
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
		this.listview = new ListView(this);
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