// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
frappe.provide('frappe.search');

frappe.search.AwesomeBar = Class.extend({
	setup: function(element) {
		var me = this;

		var $input = $(element);
		var input = $input.get(0);

		this.search = new frappe.search.UnifiedSearch();
		this.global = new frappe.search.GlobalSearch();
		this.nav = new frappe.search.NavSearch();
		this.help = new frappe.search.HelpSearch();

		this.options = [];
		this.global_results = [];

		var awesomplete = new Awesomplete(input, {
			minChars: 0,
			maxItems: 99,
			autoFirst: true,
			list: [],
			filter: function (text, term) {
				return true;
			},
			data: function (item, input) {
				var label = item.label + "%%%" + item.value + "%%%" +
					(item.description || "") + "%%%" + (item.index || "")
					 + "%%%" + (item.type || "") + "%%%" + (item.prefix || "");
				return {
					label: label,
					value: item.value
				};
			},
			item: function(item, term) {
				var d = item;
				var parts = item.split("%%%"),
				d = { label: parts[0], value: parts[1], description: parts[2],
					type: parts[4], prefix: parts[5]};

				if(d.prefix) {
					var html = "<span>" + __((d.prefix + ' ' + d.label)) + "</span>";
				} else if(d.type) {
					var html = "<span>" + __((d.label + ' ' + d.type)) + "</span>";
				} else {
					var html = "<span>" + __(d.label || d.value) + "</span>";
				}
				if(d.description && d.value!==d.description) {
					html += '<br><span class="text-muted">' + __(d.description) + '</span>';
				}
				return $('<li></li>')
					.data('item.autocomplete', d)
					.html('<a style="font-weight:normal"><p>' + html + '</p></a>')
					.get(0);
			},
			sort: function(a, b) {
				var a_index = a.split("%%%")[3];
				var b_index = b.split("%%%")[3];
				return (a_index*10 - b_index*10);
			}
		});

		$input.on("input", function(e) {
			var value = e.target.value;
			var txt = value.trim().replace(/\s\s+/g, ' ');
			var last_space = txt.lastIndexOf(' ');

			if(txt && txt.length > 2) {
				me.global.get_awesome_bar_options(txt.toLowerCase(), me);
			}

			var $this = $(this);
			clearTimeout($this.data('timeout'));

			$this.data('timeout', setTimeout(function(){
				me.options = [];
				if(txt && txt.length > 2) {
					if(last_space !== -1) {
						me.set_specifics(txt.slice(0,last_space), txt.slice(last_space+1));
					}
					me.options = me.options.concat(me.build_options(txt));
					me.build_defaults(txt);
					me.options = me.options.concat(me.global_results);
				}

				me.make_calculator(txt);
				me.add_recent(txt || "");
				me.add_help();

				// de-duplicate
				var out = [], routes = [];
				me.options.forEach(function(option) {
					if(option.route) {
						if(option.route[0] === "List" && option.route[2] && (option.route[2] === "Gantt"
							|| option.route[2] === "Calendar")) {
							option.route.splice(2, 1);
						}
						var str_route = (typeof option.route==='string') ?
								option.route : option.route.join('/');
						if(routes.indexOf(str_route)===-1) {
							out.push(option);
							routes.push(str_route);
						}
					} else {
						out.push(option);
					}
				});
				awesomplete.list = out;
			}, 100));

		});

		var open_recent = function() {
			if (!this.autocomplete_open) {
				$(this).trigger("input");
			}
		}
		$input.on("focus", open_recent);

		$input.on("awesomplete-open", function(e) {
			me.autocomplete_open = e.target;
		});

		$input.on("awesomplete-close", function(e) {
			me.autocomplete_open = false;
		});

		$input.on("awesomplete-select", function(e) {
			var o = e.originalEvent;
			var value = o.text.value;
			var item = awesomplete.get_item(value);

			if(item.route_options) {
				frappe.route_options = item.route_options;
			}

			if(item.onclick) {
				item.onclick(item.match);
			} else {
				var previous_hash = window.location.hash;
				frappe.set_route(item.route);

				// hashchange didn't fire!
				if (window.location.hash == previous_hash) {
					frappe.route();
				}
			}
		});

		$input.on("awesomplete-selectcomplete", function(e) {
			$input.val("");
		});
		this.setup_recent();
		this.search.setup();
	},

	add_help: function() {
		this.options.push({
			label: __("Help on Search"),
			value: "Help on Search",
			index: 70,
			default: "Help",
			onclick: function() {
				var txt = '<table class="table table-bordered">\
					<tr><td style="width: 50%">'+__("Make a new record")+'</td><td>'+
						__("new type of document")+'</td></tr>\
					<tr><td>'+__("List a document type")+'</td><td>'+
						__("document type..., e.g. customer")+'</td></tr>\
					<tr><td>'+__("Search in a document type")+'</td><td>'+
						__("text in document type")+'</td></tr>\
					<tr><td>'+__("Open a module or tool")+'</td><td>'+
						__("module name...")+'</td></tr>\
					<tr><td>'+__("Calculate")+'</td><td>'+
						__("e.g. (55 + 434) / 4 or =Math.sin(Math.PI/2)...")+'</td></tr>\
				</table>'
				msgprint(txt, "Search Help");
			}
		});
	},

	add_recent: function(txt) {
		var me = this;
		values = [];
		$.each(me.recent, function(i, doctype) {
			values.push([doctype[1], ['Form', doctype[0], doctype[1]]]);
		});

		values = values.reverse();

		$.each(frappe.route_history, function(i, route) {
			if(route[0]==='Form') {
				values.push([route[2], route]);
			}
			else if(in_list(['List', 'Report', 'Tree', 'modules', 'query-report'], route[0])) {
				if(route[1]) {
					values.push([route[1], route]);
				}
			}
			else if(route[0]) {
				values.push([frappe.route_titles[route[0]] || route[0], route]);
			}
		});

		this.find(values, txt, function(match) {
			out = {
				route: match[1]
			}
			if(match[1][0]==='Form') {
				out.label = __(match[1][1]) + " " + match[1][2].bold();
				out.value = __(match[1][1]) + " " + match[1][2];
			} else if(in_list(['List', 'Report', 'Tree', 'modules', 'query-report'], match[1][0])) {
				var type = match[1][0], label = type;
				if(type==='modules') label = 'Module';
				else if(type==='query-report') label = 'Report';
				out.label = __(match[1][1]).bold() + " " + __(label);
				out.value = __(match[1][1]) + " " + __(label);
			} else {
				out.label = match[0].bold();
				out.value = match[0];
			}
			out.index = 50;
			out.default = "Recent";
			return out;
		}, true);
	},

	find: function(list, txt, process, prepend) {
		var me = this;
		$.each(list, function(i, item) {
			if($.isArray(item)) {
				_item = item[0];
			} else {
				_item = item;
			}
			_item = __(_item || '').toLowerCase().replace(/-/g, " ");
			if(txt===_item || _item.indexOf(txt) !== -1) {
				var option = process(item);

				if(option) {
					if($.isPlainObject(option)) {
						option = [option];
					}

					option.forEach(function(o) { o.match = item; });

					if(prepend) {
						me.options = option.concat(me.options);
					} else {
						me.options = me.options.concat(option);
					}
				}
			}
		});
	},

	setup_recent: function() {
		this.recent = JSON.parse(frappe.boot.user.recent || "[]") || [];
	},

	fuzzy_search: function(txt, _item) {
		item = __(_item || '').replace(/-/g, " ");

		var ilen = item.length;
		var tlen = txt.length;
		var match_level = tlen/ilen;
		var rendered_label = "";
		var i, j, skips = 0, mismatches = 0;

		if (tlen > ilen) {
			return [];
		}
		if (item.indexOf(txt) !== -1) {
			var regEx = new RegExp("("+ txt +")", "ig");
			rendered_label = _item.replace(regEx, '<b>$1</b>');
			return [_item, ilen/50, rendered_label];
		}
		item = item.toLowerCase();
		txt = txt.toLowerCase();
		if (item.indexOf(txt) !== -1) {
			var regEx = new RegExp("("+ txt +")", "ig");
			rendered_label = _item.replace(regEx, '<b>$1</b>');
			return [_item, 20 + ilen/50, rendered_label];
		}
		outer: for (i = 0, j = 0; i < tlen; i++) {
			var t_ch = txt.charCodeAt(i);
			if(mismatches !== 0) skips++;
			if(skips > 3) return [];
			mismatches = 0;
			while (j < ilen) {
				var i_ch = item.charCodeAt(j);
				if (i_ch === t_ch) {
					var item_char =  _item.charAt(j);
					if(item_char === item_char.toLowerCase()){
						rendered_label += '<b>' + txt.charAt(i) + '</b>';
					} else {
						rendered_label += '<b>' + txt.charAt(i).toUpperCase() + '</b>';
					}
					j++;
					continue outer;
				}
				mismatches++;
				if(mismatches > 2) return [];
				rendered_label += _item.charAt(j);
				j++;
			}
			return [];
		}
		rendered_label += _item.slice(j);
		return [_item, 40 + ilen/50, rendered_label];
	},

	set_specifics: function(txt, end_txt) {
		var me = this;
		var results = this.build_options(txt);
		results.forEach(function(r) {
			if((r.type).toLowerCase().indexOf(end_txt.toLowerCase()) === 0) {
				me.options.push(r);
			}
		});
	},

	build_defaults: function(txt) {
		this.make_global_search(txt);
		this.make_search_in_current(txt);
		this.options = this.options.concat(this.make_search_in_list(txt));
	},

	build_options: function(txt) {
		return this.make_new_doc(txt).concat(
			this.get_doctypes(txt),
			this.get_reports(txt),
			this.get_pages(txt),
			this.get_modules(txt)
		);
	},

	set_global_results: function(global_results, txt){
		this.global_results = this.global_results.concat(global_results);
	},

	make_global_search: function(txt) {
		var me = this;
		this.options.push({
			label: __("Search for '" + txt.bold() + "'"),
			value: __("Search for '" + txt + "'"),
			match: txt,
			index: 10,
			default: "Search",
			onclick: function() {
				me.search.search_dialog.show();
				me.search.setup_search(txt, [me.nav, me.global, me.help]);
			}
		});
	},

	make_search_in_current: function(txt) {
		var route = frappe.get_route();
		if(route[0]==="List" && txt.indexOf(" in") === -1) {
			// search in title field
			var meta = frappe.get_meta(frappe.container.page.list_view.doctype);
			var search_field = meta.title_field || "name";
			var options = {};
			options[search_field] = ["like", "%" + txt + "%"];
			this.options.push({
				label: __('Find {0} in {1}', [txt.bold(), route[1].bold()]),
				value: __('Find {0} in {1}', [txt, route[1]]),
				route_options: options,
				index: 11,
				onclick: function() {
					cur_list.refresh();
				},
				default: "Current",
				match: txt
			});
		}
	},

	make_calculator: function(txt) {
		var first = txt.substr(0,1);
		if(first==parseInt(first) || first==="(" || first==="=") {
			if(first==="=") {
				txt = txt.substr(1);
			}
			try {
				var val = eval(txt);
				var formatted_value = __('{0} = {1}', [txt, (val + '').bold()]);
				this.options.push({
					label: formatted_value,
					value: __('{0} = {1}', [txt, val]),
					match: val,
					index: 12,
					default: "Calculator",
					onclick: function() {
						msgprint(formatted_value, "Result");
					}
				});
			} catch(e) {
				// pass
			}
		}
	},

	make_search_in_list: function(txt) {
		var me = this;
		var out = [];
		if(in_list(txt.split(" "), "in") && (txt.slice(-2) !== "in")) {
			parts = txt.split(" in ");
			frappe.boot.user.can_read.forEach(function (item) {
				var target = me.fuzzy_search(parts[1], item)[0];
				if(target) {
					out.push({
						label: __('Find {0} in {1}', [__(parts[0]).bold(), __(target).bold()]),
						value: __('Find {0} in {1}', [__(parts[0]), __(target)]),
						route_options: {"name": ["like", "%" + parts[0] + "%"]},
						index: 13,
						default: "In List",
						route: ["List", target]
					});
				}
			});
		}
		return out;
	},

	make_new_doc: function(txt) {
		var me = this;
		var out = [];
		if(txt.split(" ")[0]==="new") {
			frappe.boot.user.can_create.forEach(function (item) {
				var result = me.fuzzy_search(txt.substr(4), item);
				var target = result[0];
				var index = result[1];
				var rendered_label = result[2];
				if(target) {
					out.push({
						label: rendered_label,
						value: __("New {0}", [target]),
						index: 14 + index,
						type: "New",
						prefix: "New",
						match: target,
						onclick: function() { frappe.new_doc(target, true); }
					});
				}
			});
		}
		return out;
	},

	get_doctypes: function(txt) {
		var me = this;
		var out = [];

		var result, target, index, rendered_label;
		var option = function(type, route, order) {
			return {
				label: rendered_label,
				value: __(target),
				route: route,
				index: 15 + index + order,
				match: target,
				type: type
			}
		};
		frappe.boot.user.can_read.forEach(function (item) {
			result = me.fuzzy_search(txt, item);
			target = result[0];
			index = result[1];
			rendered_label = result[2];
			if(target) {
				// include 'making new' option
				if(in_list(frappe.boot.user.can_create, target)) {
					var match = target;
					out.push({
						label: rendered_label,
						value: __("New {0}", [target]),
						index: 15 + index + 0.004,
						type: "New",
						prefix: "New",
						match: target,
						onclick: function() { frappe.new_doc(match, true); }
					});
				}
				if(in_list(frappe.boot.single_types, target)) {
					out.push(option("", ["Form", target, target], 0));

				} else if(in_list(frappe.boot.treeviews, target)) {
					out.push(option("Tree", ["Tree", target], 0));

				} else {
					out.push(option("List", ["List", target], 0));
					if(frappe.model.can_get_report(target)) {
						out.push(option("Report", ["Report", target], 0.001));
					}
					if(frappe.boot.calendars.indexOf(target) !== -1) {
						out.push(option("Calendar", ["List", target, "Calendar"], 0.002));
						out.push(option("Gantt", ["List", target, "Gantt"], 0.003));
					}
				}
			}
		});
		return out;
	},

	get_reports: function(txt) {
		var me = this;
		var out = [];
		Object.keys(frappe.boot.user.all_reports).forEach(function(item) {
			var result = me.fuzzy_search(txt, item);
			var target = result[0];
			var index = result[1];
			var rendered_label = result[2];
			if(target) {
				var report = frappe.boot.user.all_reports[target];
				var route = [];
				if(report.report_type == "Report Builder")
					route = ["Report", report.ref_doctype, target];
				else
					route = ["query-report",  target];

				out.push({
					label: rendered_label,
					value: __("Report {0}" , [__(target)]),
					match: txt,
					index: 20 + index,
					type: "Report",
					prefix: "Report",
					route: route
				});
			}
		});
		return out;
	},

	get_pages: function(txt) {
		var me = this;
		var out = [];
		this.pages = {};
		$.each(frappe.boot.page_info, function(name, p) {
			me.pages[p.title] = p;
			p.name = name;
		});
		Object.keys(this.pages).forEach(function(item) {
			var result = me.fuzzy_search(txt, item);
			var target = result[0];
			var index = result[1];
			var rendered_label = result[2];
			if(target) {
				var page = me.pages[target];
				out.push({
					label: rendered_label,
					value: __("Open {0}", [__(target)]),
					match: txt,
					index: 21 + index,
					type: "Page",
					prefix: "Open",
					route: [page.route || page.name]
				});
			}
		});
		// calendar
		var target = 'Calendar';
		if(__('calendar').indexOf(txt.toLowerCase()) === 0) {
			out.push({
				label: rendered_label,
				value: __("Open {0}", [__(target)]),
				route: [target, 'Event'],
				index: 21,
				type: "Calendar",
				prefix: "Open",
				match: target
			});
		}
		return out;
	},

	get_modules: function(txt) {
		var me = this;
		var out = [];
		Object.keys(frappe.modules).forEach(function(item) {
			var result = me.fuzzy_search(txt, item);
			var target = result[0];
			var index = result[1];
			var rendered_label = result[2];
			if(target) {
				var module = frappe.modules[target];
				if(module._doctype) return;
				ret = {
					label: rendered_label,
					value: __("Open {0}", [__(target)]),
					match: txt,
					index: 22 + index,
					type: "Module",
					prefix: "Open"
				}
				if(module.link) {
					ret.route = [module.link];
				} else {
					ret.route = ["Module", target];
				}
				out.push(ret);
			}
		});
		return out;
	},
});
