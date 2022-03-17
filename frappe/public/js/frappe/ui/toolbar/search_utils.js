frappe.provide('frappe.search');

frappe.search.utils = {
	setup_recent: function() {
		this.recent = JSON.parse(frappe.boot.user.recent || "[]") || [];
	},

	get_recent_pages: function(keywords) {
		if (keywords === null) keywords = '';
		var me = this, values = [], options = [];

		function find(list, keywords, process) {
			list.forEach(function(item, i) {
				var _item = ($.isArray(item)) ? item[0] : item;
				_item = __(_item || '').toLowerCase().replace(/-/g, " ");

				if(keywords===_item || _item.indexOf(keywords) !== -1) {
					var option = process(item);

					if(option) {
						if($.isPlainObject(option)) {
							option = [option];
						}
						option.forEach(function(o) {
							o.match = item; o.recent = true;
						});

						options = option.concat(options);
					}
				}
			});
		}

		me.recent.forEach(function(doctype, i) {
			values.push([doctype[1], ['Form', doctype[0], doctype[1]]]);
		});

		values = values.reverse();

		frappe.route_history.forEach(function(route, i) {
			if(route[0]==='Form') {
				values.push([route[2], route]);
			} else if(['List', 'Tree', 'Workspaces', 'query-report'].includes(route[0]) || route[2]==='Report') {
				if(route[1]) {
					values.push([route[1], route]);
				}
			} else if(route[0]) {
				values.push([frappe.route_titles[route.join('/')] || route[0], route]);
			}
		});

		find(values, keywords, function(match) {
			var out = {
				route: match[1]
			};
			if (match[1][0]==='Form') {
				if (match[1].length > 2 && match[1][1] !== match[1][2]) {
					out.label = __(match[1][1]) + " " + match[1][2].bold();
					out.value = __(match[1][1]) + " " + match[1][2];
				} else {
					out.label = __(match[1][1]).bold();
					out.value = __(match[1][1]);
				}
			} else if (['List', 'Tree', 'Workspaces', 'query-report'].includes(match[1][0]) && (match[1].length > 1)) {
				var type = match[1][0], label = type;
				if (type==='Workspaces') label = 'Workspace';
				else if (type==='query-report' || match[1][2] ==='Report') label = 'Report';
				out.label = __(`{0} ${label}`, [__(match[1][1]).bold()]);
				out.value = __(`{0} ${label}`, [__(match[1][1])]);

			} else if (match[0]) {
				out.label = match[0].bold();
				out.value = match[0];
			} else {
				// eslint-disable-next-line
				console.log('Illegal match', match);
			}
			out.index = 80;
			return out;
		});

		return options;
	},

	get_frequent_links() {
		let options = [];
		frappe.boot.frequently_visited_links.forEach(link => {
			const label = frappe.utils.get_route_label(link.route);
			options.push({
				'route': link.route,
				'label': label,
				'value': label,
				'index': link.count,
			});
		});
		if (!options.length) {
			return this.get_recent_pages('');
		}
		return options;
	},

	get_search_in_list: function(keywords) {
		var me = this;
		var out = [];
		if(in_list(keywords.split(" "), "in") && (keywords.slice(-2) !== "in")) {
			var parts = keywords.split(" in ");
			frappe.boot.user.can_read.forEach(function(item) {
				if(frappe.boot.user.can_search.includes(item)) {
					var level = me.fuzzy_search(parts[1], item);
					if(level) {
						out.push({
							type: "In List",
							label: __('Find {0} in {1}', [__(parts[0]), me.bolden_match_part(__(item), parts[1])]),
							value: __('Find {0} in {1}', [__(parts[0]), __(item)]),
							route_options: {"name": ["like", "%" + parts[0] + "%"]},
							index: 1 + level,
							route: ["List", item]
						});
					}
				}
			});
		}
		return out;
	},

	get_creatables: function(keywords) {
		var me = this;
		var out = [];
		var firstKeyword = keywords.split(" ")[0];
		if(firstKeyword.toLowerCase() === __("new")) {
			frappe.boot.user.can_create.forEach(function(item) {
				var level = me.fuzzy_search(keywords.substr(4), item);
				if(level) {
					out.push({
						type: "New",
						label: __("New {0}", [me.bolden_match_part(__(item), keywords.substr(4))]),
						value: __("New {0}", [__(item)]),
						index: 1 + level,
						match: item,
						onclick: function() {
							frappe.new_doc(item, true);
						}
					});
				}
			});
		}
		return out;
	},

	get_doctypes: function(keywords) {
		var me = this;
		var out = [];

		var level, target;
		var option = function(type, route, order) {
			// check to skip extra list in the text
			// eg. Price List List should be only Price List
			let skip_list = type === 'List' && target.endsWith('List');
			let label_without_type = me.bolden_match_part(__(target), keywords);
			if (skip_list) {
				var label = label_without_type;
			} else {
				label = __(`{0} ${skip_list ? '' : type}`, [label_without_type]);
			}

			return {
				type: type,
				label: label,
				value: __(`{0} ${type}`, [target]),
				index: level + order,
				match: target,
				route: route,
			};
		};
		frappe.boot.user.can_read.forEach(function(item) {
			level = me.fuzzy_search(keywords, item);
			if (level) {
				target = item;
				if (in_list(frappe.boot.single_types, item)) {
					out.push(option("", ["Form", item, item], 0.05));

				} else if (frappe.boot.user.can_search.includes(item)) {
					// include 'making new' option
					if (in_list(frappe.boot.user.can_create, item)) {
						var match = item;
						out.push({
							type: "New",
							label: __("New {0}", [me.bolden_match_part(__(item), keywords)]),
							value: __("New {0}", [__(item)]),
							index: level + 0.015,
							match: item,
							onclick: function() {
								frappe.new_doc(match, true);
							}
						});
					}
					if (in_list(frappe.boot.treeviews, item)) {
						out.push(option("Tree", ["Tree", item], 0.05));

					} else {
						out.push(option("List", ["List", item], 0.05));
						if (frappe.model.can_get_report(item)) {
							out.push(option("Report", ["List", item, "Report"], 0.04));
						}
					}
				}
			}
		});
		return out;
	},

	get_reports: function(keywords) {
		var me = this;
		var out = [];
		var route;
		Object.keys(frappe.boot.user.all_reports).forEach(function(item) {
			var level = me.fuzzy_search(keywords, item);
			if(level > 0) {
				var report = frappe.boot.user.all_reports[item];
				if(report.report_type == "Report Builder")
					route = ["List", report.ref_doctype, "Report", item];
				else
					route = ["query-report",  item];
				out.push({
					type: "Report",
					label: __("Report {0}" , [me.bolden_match_part(__(item), keywords)]),
					value: __("Report {0}" , [__(item)]),
					index: level,
					route: route
				});
			}
		});
		return out;
	},

	get_pages: function(keywords) {
		var me = this;
		var out = [];
		this.pages = {};
		$.each(frappe.boot.page_info, function(name, p) {
			me.pages[p.title] = p;
			p.name = name;
		});
		Object.keys(this.pages).forEach(function(item) {
			if(item == "Hub" || item == "hub") return;
			var level = me.fuzzy_search(keywords, item);
			if(level) {
				var page = me.pages[item];
				out.push({
					type: "Page",
					label: __("Open {0}", [me.bolden_match_part(__(item), keywords)]),
					value: __("Open {0}", [__(item)]),
					match: item,
					index: level,
					route: [page.route || page.name]
				});
			}
		});
		var target = 'Calendar';
		if(__('calendar').indexOf(keywords.toLowerCase()) === 0) {
			out.push({
				type: "Calendar",
				value: __("Open {0}", [__(target)]),
				index: me.fuzzy_search(keywords, 'Calendar'),
				match: target,
				route: ['List', 'Event', target],
			});
		}
		target = 'Hub';
		if(__('hub').indexOf(keywords.toLowerCase()) === 0) {
			out.push({
				type: "Hub",
				value: __("Open {0}", [__(target)]),
				index: me.fuzzy_search(keywords, 'Hub'),
				match: target,
				route: [target, 'Item'],
			});
		}
		if(__('email inbox').indexOf(keywords.toLowerCase()) === 0) {
			out.push({
				type: "Inbox",
				value: __("Open {0}", [__('Email Inbox')]),
				index: me.fuzzy_search(keywords, 'email inbox'),
				match: target,
				route: ['List', 'Communication', 'Inbox'],
			});
		}
		return out;
	},

	get_workspaces: function(keywords) {
		var me = this;
		var out = [];
		frappe.boot.allowed_workspaces.forEach(function(item) {
			var level = me.fuzzy_search(keywords, item.name);
			if (level > 0) {
				var ret = {
					type: "Workspace",
					label: __("Open {0}", [me.bolden_match_part(__(item.name), keywords)]),
					value: __("Open {0}", [__(item.name)]),
					index: level,
					route: [frappe.router.slug(item.name)]
				};

				out.push(ret);
			}
		});
		return out;
	},

	get_dashboards: function(keywords) {
		var me = this;
		var out = [];
		frappe.boot.dashboards.forEach(function(item) {
			var level = me.fuzzy_search(keywords, item.name);
			if (level > 0) {
				var ret = {
					type: "Dashboard",
					label: __("{0} Dashboard", [me.bolden_match_part(__(item.name), keywords)]),
					value: __("{0} Dashboard", [__(item.name)]),
					index: level,
					route: ["dashboard-view", item.name]
				};

				out.push(ret);
			}
		});
		return out;
	},

	get_global_results: function(keywords, start, limit, doctype = "") {
		var me = this;
		function get_results_sets(data) {
			var results_sets = [], result, set;
			function get_existing_set(doctype) {
				return results_sets.find(function(set) {
					return set.title === doctype;
				});
			}

			function make_description(content, doc_name) {
				var parts = content.split(" ||| ");
				var result_max_length = 300;
				var field_length = 120;
				var fields = [];
				var result_current_length = 0;
				var field_text = "";
				for(var i = 0; i < parts.length; i++) {
					var part = parts[i];
					if(part.toLowerCase().indexOf(keywords) !== -1) {
						// If the field contains the keyword
						if(part.indexOf(' &&& ') !== -1) {
							var colon_index = part.indexOf(' &&& ');
							var field_value = part.slice(colon_index + 5);
						} else {
							var colon_index = part.indexOf(' : ');
							var field_value = part.slice(colon_index + 3);
						}
						if(field_value.length > field_length) {
							// If field value exceeds field_length, find the keyword in it
							// and trim field value by half the field_length at both sides
							// ellipsify if necessary
							var field_data = "";
							var index = field_value.indexOf(keywords);
							field_data += index < field_length/2 ? field_value.slice(0, index)
								: '...' + field_value.slice(index - field_length/2, index);
							field_data += field_value.slice(index, index + field_length/2);
							field_data += index + field_length/2 < field_value.length ? "..." : "";
							field_value = field_data;
						}
						var field_name = part.slice(0, colon_index);

						// Find remaining result_length and add field length to result_current_length
						var remaining_length = result_max_length - result_current_length;
						result_current_length += field_name.length + field_value.length + 2;
						if(result_current_length < result_max_length) {
							// We have room, push the entire field
							field_text = '<span class="field-name text-muted">' +
								me.bolden_match_part(field_name, keywords) + ': </span> ' +
								me.bolden_match_part(field_value, keywords);
							if(fields.indexOf(field_text) === -1 && doc_name !== field_value) {
								fields.push(field_text);
							}
						} else {
							// Not enough room
							if(field_name.length < remaining_length){
								// Ellipsify (trim at word end) and push
								remaining_length -= field_name.length;
								field_text = '<span class="field-name text-muted">' +
									me.bolden_match_part(field_name, keywords) + ': </span> ';
								field_value = field_value.slice(0, remaining_length);
								field_value = field_value.slice(0, field_value.lastIndexOf(' ')) + ' ...';
								field_text += me.bolden_match_part(field_value, keywords);
								fields.push(field_text);
							} else {
								// No room for even the field name, skip
								fields.push('...');
							}
							break;
						}
					}
				}
				return fields.join(', ');
			}

			data.forEach(function(d) {
				// more properties
				result = {
					label: d.name,
					value: d.name,
					description: make_description(d.content, d.name),
					route: ['Form', d.doctype, d.name],
				};
				if(d.image || d.image === null){
					result.image = d.image;
				}
				set = get_existing_set(d.doctype);
				if(set) {
					set.results.push(result);
				} else {
					set = {
						title: d.doctype,
						results: [result],
						fetch_type: "Global"
					};
					results_sets.push(set);
				}

			});
			return results_sets;
		}
		return new Promise(function(resolve, reject) {
			frappe.call({
				method: "frappe.utils.global_search.search",
				args: {
					text: keywords,
					start: start,
					limit: limit,
					doctype: doctype
				},
				callback: function(r) {
					if(r.message) {
						resolve(get_results_sets(r.message));
					} else {
						resolve([]);
					}
				}
			});
		});
	},

	get_nav_results: function(keywords) {
		function sort_uniques(array) {
			var routes = [], out = [];
			array.forEach(function(d) {
				if(d.route) {
					if(d.route[0] === "List" && d.route[2]) {
						d.route.splice(2);
					}
					var str_route = d.route.join('/');
					if(routes.indexOf(str_route) === -1) {
						routes.push(str_route);
						out.push(d);
					} else {
						var old = routes.indexOf(str_route);
						if(out[old].index > d.index) {
							out[old] = d;
						}
					}
				} else {
					out.push(d);
				}
			});
			return out.sort(function(a, b) {
				return b.index - a.index;
			});
		}
		var lists = [], setup = [];
		var all_doctypes = sort_uniques(this.get_doctypes(keywords));
		all_doctypes.forEach(function(d) {
			if(d.type === "") {
				setup.push(d);
			} else {
				lists.push(d);
			}
		});
		var in_keyword = keywords.split(" in ")[0];
		return [{
			title: __("Recents"),
			fetch_type: "Nav",
			results: sort_uniques(this.get_recent_pages(keywords))
		},
		{
			title: __("Create a new ..."),
			fetch_type: "Nav",
			results: sort_uniques(this.get_creatables(keywords))
		},
		{
			title: __("Lists"),
			fetch_type: "Nav",
			results: lists
		},
		{
			title: __("Reports"),
			fetch_type: "Nav",
			results: sort_uniques(this.get_reports(keywords))
		},
		{
			title: __("Administration"),
			fetch_type: "Nav",
			results: sort_uniques(this.get_pages(keywords))
		},
		{
			title: __("Workspace"),
			fetch_type: "Nav",
			results: sort_uniques(this.get_workspaces(keywords))
		},
		{
			title: __("Dashboard"),
			fetch_type: "Nav",
			results: sort_uniques(this.get_dashboards(keywords))
		},
		{
			title: __("Setup"),
			fetch_type: "Nav",
			results: setup
		},
		{
			title: __("Find '{0}' in ...", [in_keyword]),
			fetch_type: "Nav",
			results: sort_uniques(this.get_search_in_list(keywords))
		}];
	},

	fuzzy_search: function(keywords, _item) {
		// Returns 10 for case-perfect contain, 0 for not found
		//  	9 for perfect contain,
		//  	0 - 6 for fuzzy contain

		// **Specific use-case step**
		keywords = keywords || '';
		var item = __(_item || '');
		var item_without_hyphen = item.replace(/-/g, " ");

		var item_length = item.length;
		var query_length = keywords.length;
		var length_ratio = query_length / item_length;
		var max_skips = 3, max_mismatch_len = 2;

		if (query_length > item_length) {
			return 0;
		}

		// check for perfect string matches or
		// matches that start with the keyword
		if ([item, item_without_hyphen].includes(keywords)
				|| [item, item_without_hyphen].some((txt) => txt.toLowerCase().indexOf(keywords) === 0)) {
			return 10 + length_ratio;
		}

		if (item.indexOf(keywords) !== -1 && keywords !== keywords.toLowerCase()) {
			return 9 + length_ratio;
		}

		item = item.toLowerCase();
		keywords = keywords.toLowerCase();

		if (item.indexOf(keywords) !== -1) {
			return 8 + length_ratio;
		}

		var skips = 0, mismatches = 0;
		outer: for (var i = 0, j = 0; i < query_length; i++) {
			if (mismatches !== 0) skips++;
			if (skips > max_skips) return 0;
			var k_ch = keywords.charCodeAt(i);
			mismatches = 0;
			while (j < item_length) {
				if (item.charCodeAt(j++) === k_ch) {
					continue outer;
				}
				if(++mismatches > max_mismatch_len)  return 0 ;
			}
			return 0;
		}

		// Since indexOf didn't pass, there will be atleast 1 skip
		// hence no divide by zero, but just to be safe
		if((skips + mismatches) > 0) {
			return (5 + length_ratio)/(skips + mismatches);
		} else {
			return 0;
		}
	},

	bolden_match_part: function(str, subseq) {
		var rendered = "";
		if(this.fuzzy_search(subseq, str) === 0) {
			return str;
		} else if(this.fuzzy_search(subseq, str) > 6) {
			var regEx = new RegExp("("+ subseq +")", "ig");
			return str.replace(regEx, '<mark>$1</mark>');
		} else {
			var str_orig = str;
			var str = str.toLowerCase();
			var str_len = str.length;
			var subseq = subseq.toLowerCase();

			outer: for(var i = 0, j = 0; i < subseq.length; i++) {
				var sub_ch = subseq.charCodeAt(i);
				while(j < str_len) {
					if(str.charCodeAt(j) === sub_ch) {
						var str_char = str_orig.charAt(j);
						if(str_char === str_char.toLowerCase()) {
							rendered += '<mark>' + subseq.charAt(i) + '</mark>';
						} else {
							rendered += '<mark>' + subseq.charAt(i).toUpperCase() + '</mark>';
						}
						j++;
						continue outer;
					}
					rendered += str_orig.charAt(j);
					j++;
				}
				return str_orig;
			}
			rendered += str_orig.slice(j);
			return rendered;
		}

	},

	get_executables(keywords) {
		let results = [];
		this.searchable_functions.forEach(item => {
			const target = item.label.toLowerCase();
			const txt = keywords.toLowerCase();
			if (txt === target || target.indexOf(txt) === 0) {
				results.push({
					type: "Executable",
					value:  this.bolden_match_part(__(item.label), txt),
					index: this.fuzzy_search(txt, target),
					match: item.label,
					onclick: () => item.action.apply(this, item.args)
				});
			}
		});
		return results;
	},
	make_function_searchable(_function, label=null, args=null) {
		if (typeof _function !== 'function') {
			throw new Error('First argument should be a function');
		}

		this.searchable_functions.push({
			'label': label || _function.name,
			'action': _function,
			'args': args,
		});
	},
	searchable_functions: [],
};
