// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.views');

// opts:
// stats = list of fields
// doctype
// parent
// set_filter = function called on click

frappe.views.ListSidebar = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.wrapper = $(frappe.render(frappe.templates.list_sidebar,
			{doctype: this.doclistview.doctype}))
			.appendTo(this.parent);
		this.get_stats();
	},
	get_stats: function() {
		var me = this
		return frappe.call({
			type: "GET",
			method: 'frappe.desk.reportview.get_stats',
			args: {
				stats: me.stats,
				doctype: me.doctype
			},
			callback: function(r) {
				// This gives a predictable stats order
				$.each(me.stats, function(i, v) {
					me.render_stat(v, (r.message || {})[v]);
				});

				// reload button at the end
				if(me.stats.length) {
					$('<a class="small">'+__('Refresh Stats')+'</a>')
						.css({"margin-top":"15px", "display":"inline-block"})
						.click(function() {
							me.reload_stats();
							return false;
						}).appendTo($('<div class="stat-wrapper">')
							.appendTo(me.wrapper));
				}
				me.doclistview.set_sidebar_height();
			}
		});
	},
	render_stat: function(field, stat) {
		var me = this;
		var show_tags =  '<a class="list-tag-preview small" style="margin-left: 7px;">'
			+__("Show tags") +'</a>';

		if(!stat || !stat.length) {
			if(field==='_user_tags') {
				$('<div class="sidebar-section">\
					<h5 class="text-muted">\
						</i> '+__('Tags')+show_tags+'</h5>\
					<div class="side-panel-body">\
						<div class="text-muted small"><i>'+__('No records tagged.')+'</i><br>'
						+'</div>\
					</div></div>').appendTo(this.wrapper);
			}
			return;
		}

		var label = frappe.meta.docfield_map[this.doctype][field] ?
			frappe.meta.docfield_map[this.doctype][field].label : field;
		if(label==='_user_tags') label = 'Tags' + show_tags;

		// grid
		var $w = $('<div class="sidebar-section">\
			<h5 class="text-muted">'+ __(label) +'</h5>\
			<div class="side-panel-body">\
			</div>\
		</div>');

		// sort items
		stat = stat.sort(function(a, b) { return b[1] - a[1] });
		var sum = 0;
		$.each(stat, function(i,v) { sum = sum + v[1]; })

		// render items
		$.each(stat, function(i, v) {
			me.render_stat_item(i, v, sum, field).appendTo($w.find('.side-panel-body'));
		});

		$w.appendTo(this.wrapper);
	},
	render_stat_item: function(i, v, max, field) {
		var me = this;
		var args = {}
		args.label = v[0];
		args._label = __(v[0]);
		args.width = flt(v[1]) / max * 100;
		args.count = v[1];
		args.field = field;
		args.bar_style = "";

		$item = $(repl('<div class="progress" style="height: 7px;">\
				<div class="progress-bar %(bar_style)s" style="width: %(width)s%"></div>\
			</div>\
			<div class="stat-label" style="margin-top: -19px; text-align: center; \
				margin-bottom: 5px; font-size: 80%;">\
				<a href="#" data-label="%(label)s" data-field="%(field)s">\
					%(_label)s</a> (%(count)s)\
		</div>', args));

		this.setup_stat_item_click($item);
		return $item;
	},
	reload_stats: function() {
		this.wrapper.empty();
		this.get_stats();
	},
	setup_stat_item_click: function($item) {
		var me = this;
		$item.find('a').click(function() {
			var fieldname = $(this).attr('data-field');
			var label = $(this).attr('data-label');
			me.set_filter(fieldname, label);
			return false;
		});
	},
});
