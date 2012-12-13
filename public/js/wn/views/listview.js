wn.views.ListView = Class.extend({
	init: function(doclistview) {
		this.doclistview = doclistview;
		this.doctype = doclistview.doctype;
		
		var t = "`tab"+this.doctype+"`.";
		this.fields = [t + 'name', t + 'owner', t + 'docstatus', 
			t + '_user_tags', t + 'modified', t + 'modified_by'];
		this.stats = ['_user_tags'];
		this.show_hide_check_column();

	},
	columns: [
		{width: '3%', content:'check'},
		{width: '4%', content:'avatar'},
		{width: '3%', content:'docstatus', css: {"text-align": "center"}},
		{width: '35%', content:'name'},
		{width: '40%', content:'tags', css: {'color':'#aaa'}},
		{width: '15%', content:'modified', css: {'text-align': 'right', 'color':'#222'}}		
	],
	render_column: function(data, parent, opts) {
		var me = this;
		
		// style
		if(opts.css) {
			$.each(opts.css, function(k, v) { $(parent).css(k, v)});
		}
		
		// multiple content
		if(opts.content.indexOf && opts.content.indexOf('+')!=-1) {
			$.map(opts.content.split('+'), function(v) {
				me.render_column(data, parent, {content:v});
			});
			return;
		}
		
		// content
		if(typeof opts.content=='function') {
			opts.content(parent, data, me);
		}
		else if(opts.content=='name') {
			$(parent).append(repl('<a href="#!Form/%(doctype)s/%(name)s">%(name)s</a>', data));
		} 
		else if(opts.content=='avatar') {
			$(parent).append(wn.avatar(data.owner, false, "Created by: " 
				+ wn.user_info(data.owner).fullname));
		}
		else if(opts.content=='avatar_modified') {
			$(parent).append(wn.avatar(data.modified_by, false, "Modified by: " 
				+ wn.user_info(data.modified_by).fullname));
		}
		else if(opts.content=='check') {
			$(parent).append('<input class="list-delete" type="checkbox">');
			$(parent).find('input').data('name', data.name);			
		}
		else if(opts.content=='docstatus') {
			$(parent).append(repl('<span class="docstatus"><i class="%(docstatus_icon)s" \
				title="%(docstatus_title)s"></i></span>', data));			
		}
		else if(opts.content=='tags') {
			this.add_user_tags(parent, data);
		}
		else if(opts.content=='modified') {
			$(parent).append(data.when);
		}
		else if(opts.type=='bar-graph') {
			this.render_bar_graph(parent, data, opts.content, opts.label);
		}
		else if(opts.type=='link' && opts.doctype) {
			$(parent).append(repl('<a href="#!Form/'+opts.doctype+'/'
				+data[opts.content]+'">'+data[opts.content]+'</a>', data));
		}
		else if(opts.template) {
			$(parent).append(repl(opts.template, data));
		}
		else if(data[opts.content]) {
			if(opts.type=="date") {
				data[opts.content] = wn.datetime.str_to_user(data[opts.content])
			}
			$(parent).append(repl('<span title="%(title)s"> %(content)s</span>', {
				"title": opts.title || opts.content, "content": data[opts.content]}));
		}
		
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
			data.docstatus_title = 'Editable';
		} else if(data.docstatus==1) {
			data.docstatus_icon = 'icon-lock';			
			data.docstatus_title = 'Submitted';
		} else if(data.docstatus==2) {
			data.docstatus_icon = 'icon-remove';			
			data.docstatus_title = 'Cancelled';
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
			data.when = 'Yesterday'
		}
		if(diff == 2) {
			data.when = '2 days ago'
		}
	},
	
	add_user_tags: function(parent, data) {
		var me = this;
		if(data._user_tags) {
			if($(parent).html().length > 0) {
				$(parent).append('<br />');
			}
			$.each(data._user_tags.split(','), function(i, t) {
				if(t) {
					$('<span class="label label-info" style="cursor: pointer; line-height: 200%">' 
						+ strip(t) + '</span>')
						.click(function() {
							me.doclistview.set_filter('_user_tags', $(this).text())
						})
						.appendTo(parent);
				}
			});
		}		
	},
	show_hide_check_column: function() {
		if(!this.doclistview.can_delete) {
			this.columns = $.map(this.columns, function(v, i) { if(v.content!='check') return v });
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