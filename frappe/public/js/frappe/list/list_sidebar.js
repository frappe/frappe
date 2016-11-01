// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
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
		this.make();
		this.get_stats();
		this.cat_tags = [];
	},
	make: function() {
		var sidebar_content = frappe.render_template("list_sidebar", {doctype: this.doclistview.doctype});

		this.sidebar = $('<div class="list-sidebar overlay-sidebar hidden-xs hidden-sm"></div>')
			.html(sidebar_content)
			.appendTo(this.page.sidebar.empty());

		this.setup_reports();
		this.setup_assigned_to_me();
		this.setup_views();

	},
	setup_views: function() {
		var show_list_link = false;

		if(frappe.views.calendar[this.doctype]) {
			this.sidebar.find(".calendar-link").removeClass("hide");
			this.sidebar.find('.list-link[data-view="Gantt"]').removeClass('hide');
			show_list_link = true;
		}

		if(frappe.treeview_settings[this.doctype]) {
			this.sidebar.find(".tree-link").removeClass("hide");
		}

		this.current_view = 'List';
		var route = frappe.get_route();
		if(route.length > 2 && (route[2]==='Gantt' || route[2]==='Image')) {
			this.current_view = route[2];
		}

		// disable link for current view
		this.sidebar.find('.list-link[data-view="'+ this.current_view +'"] a')
			.attr('disabled', 'disabled').addClass('disabled');

		// show image link if image_view
		if(this.doclistview.meta.image_field) {
			this.sidebar.find('.list-link[data-view="Image"]').removeClass('hide');
			show_list_link = true;
		}

		if(show_list_link) {
			this.sidebar.find('.list-link[data-view="List"]').removeClass('hide');
		}
	},
	setup_reports: function() {
		// add reports linked to this doctype to the dropdown
		var me = this;
		var added = [];
		var dropdown = this.page.sidebar.find('.reports-dropdown');
		var divider = false;

		var add_reports = function(reports) {
			$.each(reports, function(name, r) {
				if(!r.ref_doctype || r.ref_doctype==me.doctype && !r.disabled) {
					var report_type = r.report_type==='Report Builder'
						? 'Report/' + r.ref_doctype : 'query-report';
					var route = r.route || report_type + '/' + r.name;

					if(added.indexOf(route)===-1) {
						// don't repeat
						added.push(route);

						if(!divider) {
							$('<li role="separator" class="divider"></li>').appendTo(dropdown);
							divider = true;
						}

						$('<li><a href="#'+ route + '">'
							+ __(r.name)+'</a></li>').appendTo(dropdown);
					}
				}
			});
		}

		// from reference doctype
		if(this.doclistview.listview.settings.reports) {
			add_reports(this.doclistview.listview.settings.reports)
		}

		// from specially tagged reports
		add_reports(frappe.boot.user.all_reports || []);
	},
	setup_assigned_to_me: function() {
		var me = this;
		this.page.sidebar.find(".assigned-to-me a").on("click", function() {
			me.doclistview.assigned_to_me();
		});
	},
	get_cat_tags:function(){
		return this.cat_tags;
	},
	get_stats: function() {
		var me = this
		frappe.call({
			type: "GET",
			method: 'frappe.desk.reportview.get_sidebar_stats',
			args: {
				stats: me.stats,
				doctype: me.doctype,
				filters:me.default_filters
			},
			callback: function(r) {
				
				if(r.message.defined_cat){
					me.defined_category = r.message.defined_cat
					me.cats = {};
					//structure the tag categories
					for (i in me.defined_category){
						if (me.cats[me.defined_category[i].category]===undefined){
							me.cats[me.defined_category[i].category]=[me.defined_category[i].tag];
						}else{
							me.cats[me.defined_category[i].category].push(me.defined_category[i].tag);
						}
						me.cat_tags[i]=me.defined_category[i].tag
					}
					me.tempstats = r.message.stats;
					var len = me.cats.length;
					$.each(me.cats, function (i, v) {
						me.render_stat(i, (me.tempstats || {})["_user_tags"],v);
					});
					me.render_stat("_user_tags", (me.tempstats || {})["_user_tags"]);
				}
				else
				{
					//render normal stats
					me.render_stat("_user_tags", (r.message.stats|| {})["_user_tags"]);
				}
				me.doclistview.set_sidebar_height();
			}
		});
	},
	render_stat: function(field, stat, tags) {
		var me = this;
		var sum = 0;
		var stats = []
		var label = frappe.meta.docfield_map[this.doctype][field] ?
			frappe.meta.docfield_map[this.doctype][field].label : field;
		var show_tags = '<a class="list-tag-preview hidden-xs" title="' + __("Show tags")
			+ '"><i class="octicon octicon-pencil"></i></a>';

		stat = (stat || []).sort(function(a, b) { return b[1] - a[1] });
		$.each(stat, function(i,v) { sum = sum + v[1]; })

		if(tags)
		{
			for (var t in tags) {
				var nfound = -1;
				for (var i in stat) {
					if (tags[t] ===stat[i][0]) {
						stats.push(stat[i]);
						nfound = i;
						break
					}
				}
				if (nfound<0)
				{
					stats.push([tags[t],0])
				}
				else
				{
					me.tempstats["_user_tags"].splice(nfound,1);
				}
			}
			field = "_user_tags"
		}
		else
		{
			stats = stat
		}
		var context = {
			field: field,
			stat: stats,
			sum: sum,
			label: field==='_user_tags' ?  tags ? __(label)+ show_tags:(__("UnCatagorised Tags") + show_tags): __(label),
		};
		var sidebar_stat = $(frappe.render_template("list_sidebar_stat", context))
			.on("click", ".stat-link", function() {
				var fieldname = $(this).attr('data-field');
				var label = $(this).attr('data-label');
				if (label == "No Tags") {
					me.doclistview.filter_list.add_filter(me.doclistview.doctype, fieldname, 'not like', '%,%')
					me.doclistview.run();
				} else {
					me.set_filter(fieldname, label);
				}
			})
			.appendTo(this.sidebar);
	},
	set_fieldtype: function(df, fieldtype) {

		// scrub
		if(df.fieldname=="docstatus") {
			df.fieldtype="Select",
			df.options=[
				{value:0, label:"Draft"},
				{value:1, label:"Submitted"},
				{value:2, label:"Cancelled"},
			]
		} else if(df.fieldtype=='Check') {
			df.fieldtype='Select';
			df.options=[{value:0,label:'No'},
				{value:1,label:'Yes'}]
		} else if(['Text','Small Text','Text Editor','Code','Tag','Comments',
			'Dynamic Link','Read Only','Assign'].indexOf(df.fieldtype)!=-1) {
			df.fieldtype = 'Data';
		} else if(df.fieldtype=='Link' && this.wrapper.find('.condition').val()!="=") {
			df.fieldtype = 'Data';
		}
		if(df.fieldtype==="Data" && (df.options || "").toLowerCase()==="email") {
			df.options = null;
		}
	},
	reload_stats: function() {
		this.sidebar.find(".sidebar-stat").remove();
		this.get_stats();
	},
});
