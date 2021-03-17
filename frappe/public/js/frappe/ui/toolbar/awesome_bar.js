// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
frappe.provide('frappe.search');
frappe.provide('frappe.tags');

frappe.search.AwesomeBar = Class.extend({
	setup: function(element) {
		var me = this;

		$('.search-bar').removeClass('hidden');
		var $input = $(element);
		var input = $input.get(0);

		this.options = [];
		this.global_results = [];

		var awesomplete = new Awesomplete(input, {
			minChars: 0,
			maxItems: 99,
			autoFirst: true,
			list: [],
			filter: function(text, term) {
				return true;
			},
			data: function(item, input) {
				return {
					label: (item.index || ""),
					value: item.value
				};
			},
			item: function(item, term) {
				var d = this.get_item(item.value);
				var name = __(d.label || d.value);
				var html = '<span>' + name + '</span>';
				if(d.description && d.value!==d.description) {
					html += '<br><span class="text-muted ellipsis">' + __(d.description) + '</span>';
				}
				return $('<li></li>')
					.data('item.autocomplete', d)
					.html(`<a style="font-weight:normal">${html}</a>`)
					.get(0);
			},
			sort: function(a, b) {
				return (b.label - a.label);
			}
		});

		// Added to aid UI testing of global search
		input.awesomplete = awesomplete;

		this.awesomplete = awesomplete;

		$input.on("input", function(e) {
			var value = e.target.value;
			var txt = value.trim().replace(/\s\s+/g, ' ');
			var last_space = txt.lastIndexOf(' ');
			me.global_results = [];
			// if(txt && txt.length > 1) {
			// 	me.global.get_awesome_bar_options(txt.toLowerCase(), me);
			// }

			var $this = $(this);
			clearTimeout($this.data('timeout'));

			$this.data('timeout', setTimeout(function(){
				me.options = [];
				if(txt && txt.length > 1) {
					if(last_space !== -1) {
						me.set_specifics(txt.slice(0,last_space), txt.slice(last_space+1));
					}
					me.add_defaults(txt);
					me.options = me.options.concat(me.build_options(txt));
					me.options = me.options.concat(me.global_results);
				} else {
					me.options = me.options.concat(
						me.deduplicate(frappe.search.utils.get_recent_pages(txt || "")));
					me.options = me.options.concat(frappe.search.utils.get_frequent_links());
				}
				me.add_help();

				awesomplete.list = me.deduplicate(me.options);
			}, 100));

		});

		var open_recent = function() {
			if (!this.autocomplete_open) {
				$(this).trigger("input");
			}
		};
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
				frappe.set_route(item.route);
			}
			$input.val("");
		});

		$input.on("awesomplete-selectcomplete", function(e) {
			$input.val("");
		});

		$input.on("keydown", null, 'esc', function() {
			$input.blur();
		});
		frappe.search.utils.setup_recent();
		frappe.tags.utils.fetch_tags();
	},

	add_help: function() {
		this.options.push({
			value: __("Help on Search"),
			index: -10,
			default: "Help",
			onclick: function() {
				var txt = '<table class="table table-bordered">\
					<tr><td style="width: 50%">'+__('Create a new record')+'</td><td>'+
						__("new type of document")+'</td></tr>\
					<tr><td>'+__("List a document type")+'</td><td>'+
						__("document type..., e.g. customer")+'</td></tr>\
					<tr><td>'+__("Search in a document type")+'</td><td>'+
						__("text in document type")+'</td></tr>\
					<tr><td>'+__("Tags")+'</td><td>'+
						__("tag name..., e.g. #tag")+'</td></tr>\
					<tr><td>'+__("Open a module or tool")+'</td><td>'+
						__("module name...")+'</td></tr>\
					<tr><td>'+__("Calculate")+'</td><td>'+
						__("e.g. (55 + 434) / 4 or =Math.sin(Math.PI/2)...")+'</td></tr>\
				</table>';
				frappe.msgprint(txt, __("Search Help"));
			}
		});
	},

	set_specifics: function(txt, end_txt) {
		var me = this;
		var results = this.build_options(txt);
		results.forEach(function(r) {
			if(r.type && (r.type).toLowerCase().indexOf(end_txt.toLowerCase()) === 0) {
				me.options.push(r);
			}
		});
	},

	add_defaults: function(txt) {
		this.make_global_search(txt);
		this.make_search_in_current(txt);
		this.make_calculator(txt);
		this.make_random(txt);
	},

	build_options: function(txt) {
		var options = frappe.search.utils.get_creatables(txt).concat(
			frappe.search.utils.get_search_in_list(txt),
			frappe.search.utils.get_doctypes(txt),
			frappe.search.utils.get_reports(txt),
			frappe.search.utils.get_pages(txt),
			frappe.search.utils.get_workspaces(txt),
			frappe.search.utils.get_dashboards(txt),
			frappe.search.utils.get_recent_pages(txt || ""),
			frappe.search.utils.get_executables(txt)
		);
		if (txt.charAt(0) === "#") {
			options = frappe.tags.utils.get_tags(txt);
		}
		var out = this.deduplicate(options);
		return out.sort(function(a, b) {
			return b.index - a.index;
		});
	},

	deduplicate: function(options) {
		var out = [], routes = [];
		options.forEach(function(option) {
			if(option.route) {
				if(option.route[0] === "List" && option.route[2] !== 'Report') {
					option.route.splice(2);
				}
				var str_route = (typeof option.route==='string') ?
					option.route : option.route.join('/');
				if(routes.indexOf(str_route)===-1) {
					out.push(option);
					routes.push(str_route);
				} else {
					var old = routes.indexOf(str_route);
					if(out[old].index < option.index && !option.recent) {
						out[old] = option;
					}
				}
			} else {
				out.push(option);
				routes.push("");
			}
		});
		return out;
	},

	set_global_results: function(global_results, txt) {
		this.global_results = this.global_results.concat(global_results);
	},

	make_global_search: function(txt) {
		// let search_text = $(this.awesomplete.ul).find('.search-text');

		// if (txt.charAt(0) === "#" || !txt) {
		// 	search_text && search_text.remove();
		// 	return;
		// }

		// if (!search_text.length) {
		// 	search_text = $(this.awesomplete.ul).prepend(`
		// 		<div class="search-text">
		// 			<span class="search-text"></span>
		// 		<div>`
		// 	).find(".search-text");
		// }

		// search_text.html(`
		// 	<span class="flex justify-between">
		// 		<span class="ellipsis">Search for ${frappe.utils.xss_sanitise(txt).bold()}</span>
		// 		<kbd>↵</kbd>
		// 	</span>
		// `);

		// search_text.click(() => {
		// 	frappe.searchdialog.search.init_search(txt, "global_search");
		// });

		// REDESIGN TODO: Remove this as a selectable option
		if (txt.charAt(0) === "#") {
			return;
		}

		this.options.push({
			label: `
				<span class="flex justify-between text-medium">
					<span class="ellipsis">${ __('Search for {0}', [frappe.utils.xss_sanitise(txt).bold()])}</span>
					<kbd>↵</kbd>
				</span>
			`,
			value: __("Search for {0}", [txt]),
			match: txt,
			index: 100,
			default: "Search",
			onclick: function() {
				frappe.searchdialog.search.init_search(txt, "global_search");
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
				label: __('Find {0} in {1}', [txt.bold(), __(route[1]).bold()]),
				value: __('Find {0} in {1}', [txt, __(route[1])]),
				route_options: options,
				onclick: function() {
					cur_list.show();
				},
				index: 90,
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
					index: 80,
					default: "Calculator",
					onclick: function() {
						frappe.msgprint(formatted_value, "Result");
					}
				});
			} catch(e) {
				// pass
			}
		}
	},

	make_random: function(txt) {
		if(txt.toLowerCase().includes('random')) {
			this.options.push({
				label: "Generate Random Password",
				value: frappe.utils.get_random(16),
				onclick: function() {
					frappe.msgprint(frappe.utils.get_random(16), "Result");
				}
			})
		}
	}
});
