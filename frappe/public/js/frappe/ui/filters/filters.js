// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.FilterList = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.filters = [];
		this.wrapper = this.parent;
		this.stats = [];
		this.make();
		this.set_events();
	},
	make: function() {
		var me = this;

		this.wrapper.find('.show_filters').remove();
		this.wrapper.append(`
			<div class="show_filters">
				<div class="set-filters">
					<button
						class="btn btn-default btn-xs show-filters text-muted"
						style="margin-right: 10px;">
							${__("Show Filters")}
					</button>
					<button style="margin-left: -5px;"
						class="btn btn-default btn-xs new-filter text-muted">
						<i class="octicon octicon-plus"></i></button>
				</div>
			</div>`);
		$(frappe.render_template("filter_dashboard", {})).appendTo(this.wrapper.find('.show_filters'));

		//show filter dashboard
		this.filters_visible = false;
		this.wrapper.find('.show-filters').click(function() {
			var wrapper = $(me.wrapper).find('.filter-dashboard-wrapper');
			if(!me.filters_visible) {
				wrapper.toggle(true);
				$(this).text(__("Hide Filters"));
				me.filters_visible = true;
			} else {
				wrapper.toggle(false);
				$(this).text(__("Show Filters"));
				me.filters_visible = false;
			}
		});

		//add stats
		$.each(frappe.meta.docfield_map[this.doctype], function(i,d) {
			if (d.in_standard_filter && frappe.perm.has_perm(me.doctype, d.permlevel, "read")) {
				if (d.fieldtype != 'Table') {
					me.stats.push({name:d.fieldname,label:d.label,type:d.fieldtype});
				}
			}
		});

		me.stats = me.stats.concat([
			{name:'creation', label:'Created On', type:'Datetime'},
			{name:'modified', label:'Last Modified On', type:'Datetime'},
			{name:'owner', label:'Created By', type:'Data'},
			{name:'modified_by', label:'Last Modified By', type:'Data'},
		]);

		if(frappe.model.is_submittable(me.doctype)) {
			me.stats.push({name:'docstatus', label:'Document Status', type:'Data'});
		}

		$.each(me.stats, function (i, v) {
			me.render_dashboard_headers(v);
		});

		me.reload_stats()
	},
	render_dashboard_headers: function(field){
		var me = this;
		var context = {
			field: field.name,
			label: __(field.label),
			type:field.type
		};
		var sidebar_stat = $(frappe.render_template("filter_dashboard_head", context))
			.appendTo(this.wrapper.find(".filter-dashboard-items"));
	},
	reload_stats: function(){
		if(this.fresh) {
			return;
		}
		// set a fresh so that multiple refreshes do not happen
		// at the same time.
		this.fresh = true;
		setTimeout(function() {
			me.fresh = false;
		}, 1000);

		//get stats
		var me = this
		return frappe.call({
			type: "GET",
			method: 'frappe.desk.reportview.get_filter_dashboard_data',
			args: {
				stats: me.stats,
				doctype: me.doctype,
				filters: me.default_filters
			},
			callback: function(r) {
				// This gives a predictable stats order
				me.wrapper.find(".filter-stat").empty();
				$.each(me.stats, function (i, v) {
						me.render_filters(v, (r.message|| {})[v.name]);
				});
			}
		});
	},
	render_filters: function(field, stat){
		var me = this;
		var sum = 0;
		if (['Date', 'Datetime'].indexOf(field.type)!=-1) {
			return
		}

		var active = this.wrapper.find(".filter-sort-active[data-name='"+__(field.name)+"']");

		// sort filters
		if(active.attr('data-sort-by')==='alphabet') {
			stat = (stat || []).sort(function(a, b) {return a[0].toString().toLowerCase().localeCompare(b[0].toString().toLowerCase());});
		} else {
			stat = (stat || []).sort(function(a, b) { return a[1] - b[1] });
		}

		if(active.attr('data-order')==='desc') {
			stat = stat.reverse();
		}

		//check formatting
		var options = []
		var df = frappe.meta.has_field(me.doctype,field.name)
		var labels =[]
		if(df && df.fieldtype=='Check') {
			options = [
				{value: 0, label: 'No'},
				{value: 1, label: 'Yes'}
			];
		} else if(field.name=="docstatus") {
			labels.length = stat.length;
			options = [
				{value: 0, label: "Draft"},
				{value: 1, label: "Submitted"},
				{value: 2, label: "Cancelled"}
			];
		}

		if(options.length>0) {
			for (i in stat) {
				for (o in options) {
					if (stat[i][0] == options[o].value) {
						if (field.name=="docstatus") {
							labels[i] = options[o].label
						}else{
							stat[i][0] = options[o].label
						}
					}
				}
			}
		}
		var context = {
			field: field.name,
			stat: stat,
			sum: sum,
			label: __(field.label),
			labels:labels
		};
		var dashboard_filter = this.wrapper.find(".filter-stat[data-name='" + __(field.name) + "']")
		dashboard_filter.html(frappe.render_template("filter_dashboard_value", context))
			.on("click", ".filter-stat-link", function() {
				var fieldname = $(this).attr('data-field');
				var label = $(this).attr('data-label');
				if ((df && df.fieldtype=='Check' )|| field.name=="docstatus") {
					var noduplicate = true
				}
				if (label=="No Data"){
					me.base_list.set_filter(fieldname, '', false, noduplicate);
				}else{
					me.base_list.set_filter(fieldname, label, false, noduplicate);
				}
				return false;
			})
		if (stat.length>5) {
			//list for autocomplete
			var autolist = []
			for (var i = 0; i < stat.length; i++) {
				autolist.push({label: stat[i][0], value: field.name});
			}

			var search_input = dashboard_filter.parent().find(".search-dashboard");

			dashboard_filter.parent().find(".search-dropdown")
				.removeClass("hide")
				.on("shown.bs.dropdown", function (event) {
					search_input.focus();
					search_input.val("")
				});

			new Awesomplete(search_input.get(0), {
				minChars: 0,
				maxItems: 99,
				autoFirst: true,
				list: autolist,
				item: function(item, input) {
					return $("<li>").text(item.label).get(0);
				},
				replace: function(text) {
					this.input.value = '';
				}
			});

			search_input.on("awesomplete-select", function(e) {
				var item = e.originalEvent.text;
				if (item) {
					if (df && df.fieldtype == 'Check') {
						var noduplicate = true
					}
					if (item.label == "No Data") {
						me.base_list.set_filter(item.value, '', false, noduplicate);
					} else {
						me.base_list.set_filter(item.value, item.label, false, noduplicate);
					}
				}
			});
		}
	},
	set_events: function() {
		var me = this;
		// show filters
		this.wrapper.find('.new-filter').bind('click', function() {
			me.add_filter();
		});

		this.wrapper.find('.clear-filters').bind('click', function() {
			me.clear_filters();
			$('.date-range-picker').val('')
			me.base_list.run();
			$(this).addClass("hide");
		});

		//set sort filters
		this.wrapper.on("click", ".filter-sort-item", function() {
			var active = $(this).closest(".filter-dash-item").find(".filter-sort-active");
			active.attr('data-sort-by', $(this).attr('data-sort-by'));
			active.attr('data-order', $(this).attr('data-order'));
			me.reload_stats();
		});

		//setup date-time range pickers
		this.wrapper.find(".filter-input-date").each(function(i,v) {
			var self = this;
			var date;
			var date_wrapper = $('<div>').appendTo($(this));
			make_date("range");

			function make_date(mode) {
				var fieldtype = mode==="range" ? "DateRange" : "Date";
				var name = $(v).data("name");
				if(date) {
					//cleanup old datepicker
					date.datepicker.destroy();
				}
				date = frappe.ui.form.make_control({
					df: {
						fieldtype: fieldtype,
						fieldname: name,
					},
					parent: date_wrapper,
					only_input: true
				});
				date.refresh();

				date.datepicker.update("onSelect", function(fd, dateObj) {
					var filt = me.get_filter(name);
					filt && filt.remove(true);
					if(!dateObj.length && dateObj && date.datepicker.opts.range===false) {
						me.add_filter(me.doctype, name, '=', moment(dateObj).format('YYYY-MM-DD'));
						me.base_list.run();
					} else if(dateObj.length===2 && date.datepicker.opts.range===true) {
						var [date1, date2] = [moment(dateObj[0]).format('YYYY-MM-DD'), moment(dateObj[1]).format('YYYY-MM-DD')];
						if(date1==date2) {
							me.add_filter(me.doctype, name, '=', date1);
						} else {
							me.add_filter(me.doctype, name, 'Between', [date1, date2]);
						}
						me.base_list.run();
					}
				});
			}
		})
	},

	show_filters: function() {
		this.wrapper.find('.show_filters').toggle();
		if(!this.filters.length) {
			this.add_filter(this.doctype, 'name');
			this.filters[0].wrapper.find(".filter_field input").focus();
		}
	},

	clear_filters: function() {
		$.each(this.filters, function(i, f) { f.remove(true); });
		this.filters = [];
	},

	add_filter: function(doctype, fieldname, condition, value, hidden) {
		if(doctype && fieldname
			&& !frappe.meta.has_field(doctype, fieldname)
			&& !in_list(frappe.model.std_fields_list, fieldname)) {
			frappe.msgprint({
				message: __('Filter {0} missing', [fieldname.bold()]),
				title: 'Invalid Filter',
				indicator: 'red'
			});
			return;
		}


		this.wrapper.find('.show_filters').toggle(true);
		var is_new_filter = arguments.length===0;

		if (is_new_filter && this.wrapper.find(".is-new-filter:visible").length) {
			// only allow 1 new filter at a time!
			return;
		}

		var filter = this.push_new_filter(doctype, fieldname, condition, value);

		if(this.wrapper.find('.clear-filters').hasClass("hide")) {
			this.wrapper.find('.clear-filters').removeClass("hide");
		}

		if (filter && is_new_filter) {
			filter.wrapper.addClass("is-new-filter");
		}

		if (filter && hidden) {
			filter.freeze();
			filter.$btn_group.addClass("hide");
		}

		return filter;
	},
	push_new_filter: function(doctype, fieldname, condition, value) {
		if(this.filter_exists(doctype, fieldname, condition, value)) return;

		var filter = new frappe.ui.Filter({
			flist: this,
			_doctype: doctype,
			fieldname: fieldname,
			condition: condition,
			value: value
        });

		this.filters.push(filter);

		return filter;
	},

	filter_exists: function(doctype, fieldname, condition, value) {
		var flag = false;
		for(var i in this.filters) {
			if(this.filters[i].field) {
				var f = this.filters[i].get_value();
				if(f[0]==doctype && f[1]==fieldname && f[2]==condition && f[3]==value) {
					flag = true;
				} else if($.isArray(value) && frappe.utils.arrays_equal(value, f[3])) {
					flag = true;
				}
			}
		}
		return flag;
	},

	get_filters: function() {
		// get filter values as dict
		var values = [];
		$.each(this.filters, function(i, filter) {
			if(filter.field) {
				filter.freeze();
				values.push(filter.get_value());
			}
		});
		return values;
	},

	// remove hidden filters
	update_filters: function() {
		var fl = [];
		$.each(this.filters, function(i, f) {
			if(f.field) fl.push(f);
		})
		this.filters = fl;
		if(this.filters.length === 0) {
			this.wrapper.find('.clear-filters').addClass("hide");
		}
	},

	get_filter: function(fieldname) {
		for(var i in this.filters) {
			if(this.filters[i].field && this.filters[i].field.df.fieldname==fieldname)
				return this.filters[i];
		}
	}
});

frappe.ui.Filter = Class.extend({
	init: function(opts) {
		$.extend(this, opts);

		this.doctype = this.flist.doctype;
		this.make();
		this.make_select();
		this.set_events();
	},
	make: function() {
		this.wrapper = $(frappe.render_template("edit_filter", {}))
			.appendTo(this.flist.wrapper.find('.filter_area'));
	},
	make_select: function() {
		var me = this;
		this.fieldselect = new frappe.ui.FieldSelect({
			parent: this.wrapper.find('.fieldname_select_area'),
			doctype: this.doctype,
			filter_fields: this.filter_fields,
			select: function(doctype, fieldname) {
				me.set_field(doctype, fieldname);
			}
		});
		if(this.fieldname) {
			this.fieldselect.set_value(this._doctype || this.doctype, this.fieldname);
		}
	},
	set_events: function() {
		var me = this;

		this.wrapper.find("a.remove-filter").on("click", function() {
			me.remove();
		});

		this.wrapper.find(".set-filter-and-run").on("click", function() {
			me.wrapper.removeClass("is-new-filter");
			me.flist.base_list.run();
		});

		// add help for "in" codition
		me.wrapper.find('.condition').change(function() {
			if(!me.field) return;
			var condition = $(this).val();
			if(in_list(["in", "like", "not in", "not like"], condition)) {
				me.set_field(me.field.df.parent, me.field.df.fieldname, 'Data', condition);
				if(!me.field.desc_area) {
					me.field.desc_area = $('<div class="text-muted small">').appendTo(me.field.wrapper);
				}
				// set description
				me.field.desc_area.html((in_list(["in", "not in"], condition)==="in"
					? __("values separated by commas")
					: __("use % as wildcard"))+'</div>');
			} else {
				me.set_field(me.field.df.parent, me.field.df.fieldname, null,
					 condition);
			}
		});

		// set the field
		if(me.fieldname) {
			// pre-sets given (could be via tags!)
			this.set_values(me._doctype, me.fieldname, me.condition, me.value);
		} else {
			me.set_field(me.doctype, 'name');
		}
	},

	remove: function(dont_run) {
		this.wrapper.remove();
		this.$btn_group && this.$btn_group.remove();
		this.field = null;
		this.flist.update_filters();

		if(!dont_run) {
			this.flist.base_list.clean_dash = true;
			this.flist.base_list.refresh(true);
		}
	},

	set_values: function(doctype, fieldname, condition, value) {
		// presents given (could be via tags!)
		this.set_field(doctype, fieldname);

		// change 0,1 to Yes, No for check field type
		if(this.field.df.original_type==='Check') {
			if(value==0) value = 'No';
			else if(value==1) value = 'Yes';
		}

		if(condition) this.wrapper.find('.condition').val(condition).change();
		if(value!=null) this.field.set_input(value);
	},

	set_field: function(doctype, fieldname, fieldtype, condition) {
		var me = this;

		// set in fieldname (again)
		var cur = me.field ? {
			fieldname: me.field.df.fieldname,
			fieldtype: me.field.df.fieldtype,
			parent: me.field.df.parent,
		} : {};

		var original_docfield = me.fieldselect.fields_by_name[doctype][fieldname];
		if(!original_docfield) {
			msgprint(__("Field {0} is not selectable.", [fieldname]));
			return;
		}

		var df = copy_dict(me.fieldselect.fields_by_name[doctype][fieldname]);

		// filter field shouldn't be read only or hidden
		df.read_only = 0;
		df.hidden = 0;

		if(!condition) this.set_default_condition(df, fieldtype);
		this.set_fieldtype(df, fieldtype);

		// called when condition is changed,
		// don't change if all is well
		if(me.field && cur.fieldname == fieldname && df.fieldtype == cur.fieldtype &&
			df.parent == cur.parent) {
			return;
		}

		// clear field area and make field
		me.fieldselect.selected_doctype = doctype;
		me.fieldselect.selected_fieldname = fieldname;

		// save old text
		var old_text = null;
		if(me.field) {
			old_text = me.field.get_parsed_value();
		}

		var field_area = me.wrapper.find('.filter_field').empty().get(0);
		var f = frappe.ui.form.make_control({
			df: df,
			parent: field_area,
			only_input: true,
		})
		f.refresh();

		me.field = f;
		if(old_text && me.field.df.fieldtype===cur.fieldtype)
			me.field.set_input(old_text);

		// run on enter
		$(me.field.wrapper).find(':input').keydown(function(ev) {
			if(ev.which==13) {
				me.flist.base_list.run();
			}
		})
	},

	set_fieldtype: function(df, fieldtype) {
		// reset
		if(df.original_type)
			df.fieldtype = df.original_type;
		else
			df.original_type = df.fieldtype;

		df.description = ''; df.reqd = 0;

		// given
		if(fieldtype) {
			df.fieldtype = fieldtype;
			return;
		}

		// scrub
		if(df.fieldname=="docstatus") {
			df.fieldtype="Select",
			df.options=[
				{value:0, label:__("Draft")},
				{value:1, label:__("Submitted")},
				{value:2, label:__("Cancelled")}
			]
		} else if(df.fieldtype=='Check') {
			df.fieldtype='Select';
			df.options='No\nYes';
		} else if(['Text','Small Text','Text Editor','Code','Tag','Comments',
			'Dynamic Link','Read Only','Assign'].indexOf(df.fieldtype)!=-1) {
			df.fieldtype = 'Data';
		} else if(df.fieldtype=='Link' && this.wrapper.find('.condition').val()!="=") {
			df.fieldtype = 'Data';
		}
		if(df.fieldtype==="Data" && (df.options || "").toLowerCase()==="email") {
			df.options = null;
		}
		if(this.wrapper.find('.condition').val()== "Between" && (df.fieldtype == 'Date' || df.fieldtype == 'Datetime')){
			df.fieldtype = 'DateRange';
		}
	},

	set_default_condition: function(df, fieldtype) {
		if(!fieldtype) {
			// set as "like" for data fields
			if (df.fieldtype == 'Data') {
				this.wrapper.find('.condition').val('like');
			} else if (df.fieldtype == 'Date' || df.fieldtype == 'Datetime'){
				this.wrapper.find('.condition').val('Between');
			}else{
				this.wrapper.find('.condition').val('=');
			}
		}
	},

	get_value: function() {
		return [this.fieldselect.selected_doctype,
			this.field.df.fieldname, this.get_condition(), this.get_selected_value()];
	},

	get_selected_value: function() {
		var val = this.field.get_parsed_value();

		if(typeof val==='string') {
			val = strip(val);
		}

		if(this.field.df.original_type == 'Check') {
			val = (val=='Yes' ? 1 :0);
		}

		if(this.get_condition().indexOf('like', 'not like')!==-1) {
			// automatically append wildcards
			if(val) {
				if(val.slice(0,1) !== "%") {
					val = "%" + val;
				}
				if(val.slice(-1) !== "%") {
					val = val + "%";
				}
			}
		} else if(in_list(["in", "not in"], this.get_condition())) {
			val = $.map(val.split(","), function(v) { return strip(v); });
		} if(val === '%') {
			val = "";
		}

		return val;
	},

	get_condition: function() {
		return this.wrapper.find('.condition').val();
	},

	freeze: function() {
		if(this.$btn_group) {
			// already made, just hide the condition setter
			this.set_filter_button_text();
			this.wrapper.toggle(false);
			return;
		}

		var me = this;

		// add a button for new filter if missing
		this.$btn_group = $('<div class="btn-group">\
			<button class="btn btn-default btn-xs toggle-filter"\
				title="'+__("Edit Filter")+'">\
				%(label)s %(condition)s "%(value)s"\
			</button>\
			<button class="btn btn-default btn-xs remove-filter"\
				title="'+__("Remove Filter")+'">\
				<i class="fa fa-remove text-muted"></i>\
			</button></div>')
			.insertAfter(this.flist.wrapper.find(".set-filters .show-filters"));

		this.set_filter_button_text();

		this.$btn_group.find(".remove-filter").on("click", function() {
			me.remove();
		});

		this.$btn_group.find(".toggle-filter").on("click", function() {
			$(this).closest('.show_filters').find('.filter_area').show()
			me.wrapper.toggle();
		})
		this.wrapper.toggle(false);
	},

	set_filter_button_text: function() {
		var value = this.get_selected_value();

		if(this.field.df.fieldname==="docstatus") {
			value = {0:"Draft", 1:"Submitted", 2:"Cancelled"}[value] || value;
		} else if(this.field.df.original_type==="Check") {
			value = {0:"No", 1:"Yes"}[cint(value)];
		} else if (in_list(["Date", "Datetime"], this.field.df.fieldtype)) {
			value = frappe.datetime.str_to_user(value);
		} else {
			value = this.field.get_value();
		}

		// for translations
		// __("like"), __("not like"), __("in")

		this.$btn_group.find(".toggle-filter")
			.html(repl('%(label)s %(condition)s "%(value)s"', {
				label: __(this.field.df.label),
				condition: __(this.get_condition()),
				value: __(value),
			}));
	}

});

// <select> widget with all fields of a doctype as options
frappe.ui.FieldSelect = Class.extend({
	// opts parent, doctype, filter_fields, with_blank, select
	init: function(opts) {
		var me = this;
		$.extend(this, opts);
		this.fields_by_name = {};
		this.options = [];
		this.$select = $('<input class="form-control">')
			.appendTo(this.parent)
			.on("click", function () { $(this).select(); });
		this.select_input = this.$select.get(0);
		this.awesomplete = new Awesomplete(this.select_input, {
			minChars: 0,
			maxItems: 99,
			autoFirst: true,
			list: me.options,
			item: function(item, input) {
				return $(repl('<li class="filter-field-select"><p>%(label)s</p></li>', item))
				.data("item.autocomplete", item)
				.get(0);
			}
		});
		this.$select.on("awesomplete-select", function(e) {
			var o = e.originalEvent;
			var value = o.text.value;
			var item = me.awesomplete.get_item(value);
			me.selected_doctype = item.doctype;
			me.selected_fieldname = item.fieldname;
			if(me.select) me.select(item.doctype, item.fieldname);
		});
		this.$select.on("awesomplete-selectcomplete", function(e) {
			var o = e.originalEvent;
			var value = o.text.value;
			var item = me.awesomplete.get_item(value);
			me.$select.val(item.label);
		});

		if(this.filter_fields) {
			for(var i in this.filter_fields)
				this.add_field_option(this.filter_fields[i])
		} else {
			this.build_options();
		}
		this.set_value(this.doctype, "name");
		window.last_filter = this;
	},
	get_value: function() {
		return this.selected_doctype ? this.selected_doctype + "." + this.selected_fieldname : null;
	},
	val: function(value) {
		if(value===undefined) {
			return this.get_value();
		} else {
			this.set_value(value);
		}
	},
	clear: function() {
		this.selected_doctype = null;
		this.selected_fieldname = null;
		this.$select.val("");
	},
	set_value: function(doctype, fieldname) {
		var me = this;
		this.clear();
		if(!doctype) return;

		// old style
		if(doctype.indexOf(".")!==-1) {
			parts = doctype.split(".");
			doctype = parts[0];
			fieldname = parts[1];
		}

		$.each(this.options, function(i, v) {
			if(v.doctype===doctype && v.fieldname===fieldname) {
				me.selected_doctype = doctype;
				me.selected_fieldname = fieldname;
				me.$select.val(v.label);
				return false;
			}
		});
	},
	build_options: function() {
		var me = this;
		me.table_fields = [];
		var std_filters = $.map(frappe.model.std_fields, function(d) {
			var opts = {parent: me.doctype}
			if(d.fieldname=="name") opts.options = me.doctype;
			return $.extend(copy_dict(d), opts);
		});

		// add parenttype column
		var doctype_obj = locals['DocType'][me.doctype];
		if(doctype_obj && cint(doctype_obj.istable)) {
			std_filters = std_filters.concat([{
				fieldname: 'parent',
				fieldtype: 'Data',
				label: 'Parent',
				parent: me.doctype,
			}]);
		}

		// blank
		if(this.with_blank) {
			this.options.push({
				label:"",
				value:"",
			})
		}

		// main table
		var main_table_fields = std_filters.concat(frappe.meta.docfield_list[me.doctype]);
		$.each(frappe.utils.sort(main_table_fields, "label", "string"), function(i, df) {
			// show fields where user has read access and if report hide flag is not set
			if(frappe.perm.has_perm(me.doctype, df.permlevel, "read") && !df.report_hide)
				me.add_field_option(df);
		});

		// child tables
		$.each(me.table_fields, function(i, table_df) {
			if(table_df.options) {
				var child_table_fields = [].concat(frappe.meta.docfield_list[table_df.options]);
				$.each(frappe.utils.sort(child_table_fields, "label", "string"), function(i, df) {
					// show fields where user has read access and if report hide flag is not set
					if(frappe.perm.has_perm(me.doctype, df.permlevel, "read") && !df.report_hide)
						me.add_field_option(df);
				});
			}
		});
	},

	add_field_option: function(df) {
		var me = this;
		if(me.doctype && df.parent==me.doctype) {
			var label = __(df.label);
			var table = me.doctype;
			if(df.fieldtype=='Table') me.table_fields.push(df);
		} else {
			var label = __(df.label) + ' (' + __(df.parent) + ')';
			var table = df.parent;
		}
		if(frappe.model.no_value_type.indexOf(df.fieldtype)==-1 &&
			!(me.fields_by_name[df.parent] && me.fields_by_name[df.parent][df.fieldname])) {
				this.options.push({
					label: label,
					value: table + "." + df.fieldname,
					fieldname: df.fieldname,
					doctype: df.parent
				})
			if(!me.fields_by_name[df.parent]) me.fields_by_name[df.parent] = {};
			me.fields_by_name[df.parent][df.fieldname] = df;
		}
	},
})
