// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.search = {
	setup: function(element) {
		var $input = $(element);
		var input = $input.get(0);

		var awesomplete = new Awesomplete(input, {
			minChars: 0,
			maxItems: 99,
			autoFirst: true,
			list: [],
			filter: function (text, term) { return true; },
			item: function(item, term) {
				var d = item;
				var html = "<span>" + __(d.label || d.value) + "</span>";
				if(d.description && d.value!==d.description) {
					html += '<br><span class="text-muted">' + __(d.description) + '</span>';
				}
				return $('<li></li>')
					.data('item.autocomplete', d)
					.html('<a style="font-weight:normal"><p>' + html + '</p></a>')
					.get(0);
			},
			sort: function(a, b) { return 0; }
		});

		$input.on("input", function(e) {
			var value = e.target.value;
			var txt = strip(value);
			frappe.search.options = [];
			if(txt) {
				var lower = strip(txt.toLowerCase());
				$.each(frappe.search.verbs, function(i, action) {
					action(lower);
				});
			}

			// sort options
			frappe.search.options.sort(function(a, b) {
				return (a.match || "").length - (b.match || "").length; });

			frappe.search.add_recent(txt || "");
			frappe.search.add_help();

			// de-duplicate
			var out = [], routes = [];
			frappe.search.options.forEach(function(option) {
				if(option.route) {
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
		});

		var open_recent = function() {
			if (!frappe.search.autocomplete_open) {
				$(this).trigger("input");
			}
		}
		$input.on("focus", open_recent);

		$input.on("awesomplete-open", function(e) {
			frappe.search.autocomplete_open = e.target;
		});

		$input.on("awesomplete-close", function(e) {
			frappe.search.autocomplete_open = false;
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

		frappe.search.make_page_title_map();
		frappe.search.setup_recent();


		if ($('#global-search').length == 0){
			frappe.search.setup_search();
		}
	},
	add_help: function() {
		frappe.search.options.push({
			label: __("Help on Search"),
			value: "Help on Search",
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
		values = [];
		$.each(frappe.search.recent, function(i, doctype) {
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

		frappe.search.find(values, txt, function(match) {
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
			return out;
		}, true);
	},
	make_page_title_map: function() {
		frappe.search.pages = {};
		$.each(frappe.boot.page_info, function(name, p) {
			frappe.search.pages[p.title] = p;
			p.name = name;
		});
	},
	setup_recent: function() {
		frappe.search.recent = JSON.parse(frappe.boot.user.recent || "[]") || [];
	},
	find: function(list, txt, process, prepend) {
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
						frappe.search.options = option.concat(frappe.search.options);
					} else {
						frappe.search.options = frappe.search.options.concat(option);
					}
				}
			}
		});
	},

	setup_search: function() {
		var $search_modal = frappe.get_modal('Global Search', "");
		$search_modal.addClass('search-modal');
		$search_modal.attr('id', 'global-search');
		var $search_input = $('<div class="input-group" style="margin-top:5px; margin-bottom:5px; margin-left:80px; margin-right:80px">' + 
							'<input id="input-global" type="text" class="form-control" placeholder="Search for..." autofocus>' + 
							'<span class="input-group-btn"><button class="btn btn-secondary btn-default" type="button">' + 
							'<i class="glyphicon glyphicon-search"></i></button></span></div>');
		$search_input.appendTo($search_modal.find('.modal-body'));
		var $result_div = $('<div class="results">Results</div>');
		$result_div.appendTo($search_modal.find('.modal-body'));

		$("#input-global").on("keydown", function (e) {
			console.log("search input typed", e.which);
			if(e.which == 13) {
				var keywords = $(this).val();
				console.log("input is", $(this).val());
				frappe.search.show_search_results(keywords);
			}
		});

		$("#input-global + span").on("click", function () {
			var keywords = $("#input-global").val();
			frappe.search.show_search_results(keywords);
		});

	},

	show_search_results: function (keywords) {

		frappe.call({
			method: "frappe.utils.global_search.search",
			args: {
				text: keywords, start: 0, limit: 20
			},
			callback: function(r) {
				var results = r.message || [];
				var results_html = "<h4 style='margin-bottom: 25px'>Showing results for '" + keywords + "' </h4>";
				var result_base_html = "<div class='search-result'>" +
									"<a href='{0}' class='h4'>{1}</a>" +
									"<p>{2}</p>" +
									"</div>";
				var data = [];
				var initial_length = 6;
				var more_length = 5;
				var $modal = $('#global-search');

				for (var i = 0, l = results.length; i < l; i++) {
					var fpath = '#Form/' + results[i].doctype + '/' + results[i].name;
					var title = results[i].doctype + ": " + results[i].name;
					var regEx = new RegExp("("+ keywords +")", "ig");
					// parts = results[i].content.split(/;(.+)/);
					var rendered_content = results[i].content.replace(regEx, '<b>$1</b>');
					data.push([fpath, title, rendered_content]);

				}

				console.log("data after:", data);

				if(results.length === 0) {
					results_html += "<p class='padding'>No results found</p>";

				} else if(data.length <= initial_length) {
					data.forEach(function(e) {
						results_html += __(result_base_html, e);
					});
					results_html += '<div id="no-more" align="center" style="color:#aaa; padding:5px;">No more results</div>';
					data = [];

				} else {
					for (var i = 0; i < initial_length; i++){
						results_html += __(result_base_html, data[0]);
						data.splice(0, 1);
					};
					// ISSUE for data-dismiss: https://github.com/twbs/bootstrap/issues/7192
					results_html += '<div id="show-more" align="center" style="color:#aaa; padding:5px;"><a>Show more results</a></div>';
				}

				$modal.find('.results').html(results_html);
				if(!$modal.hasClass('in')) {
					$modal.modal('show');
				}

				$(window).on('hashchange', function(e){
					console.log("hashchange");
				    $modal.modal('hide');
				});

				if(data.length > 0) {
					$show = document.getElementById("show-more");
					$show.addEventListener('click', function() {
						var more_rendered_results = "";
						for(var i = 0; (i < more_length) && (data.length !== 0); i++) {
							results_html += __(result_base_html, data[0]);
							data.splice(0, 1);	
						}

						$show.insertAdjacentHTML('beforebegin', more_rendered_results);
						if(data.length === 0){
							$modal.find('#show-more').html('No more results');
						}	

					});

				}

			}
		});
	}

}

frappe.search.verbs = [

	// Global Search
	// But shows up at the very top
	function(txt) {
		frappe.search.options.unshift({
			label: __("Search in Global Search: " + txt.bold()),
			value: __("Search in Global Search: " + txt.bold()),
			onclick: function(match) {
					frappe.search.show_search_results(txt);
			}
		});
	},

	// search in list if current
	function(txt) {
		
		var route = frappe.get_route();
		//console.log("current route", route);
		if(route[0]==="List" && txt.indexOf(" in") === -1) {
			// search in title field
			var meta = frappe.get_meta(frappe.container.page.doclistview.doctype);
			var search_field = meta.title_field || "name";
			// console.log("meta", meta.name);
			// var whatList = frappe.get_list(meta.name, fields=["name"], order_by="name");
			// console.log("whatList", frappe.get_value(meta.name, 'Chair', 'Status'));
			// frappe.model.with_doctype(meta.name, function(){
				
			// });

			var list = $(".list-id").map(function(){return $(this).attr("data-name");}).get();
			console.log("whatList", list);
			var options = {};
			var result = [];
			frappe.require('assets/frappe/js/lib/fuse.min.js', function() {
				var fuzzyEgList = 
				[
					 {
					    title: "Old Man's War"
					 },
					 {
					    title: "The Lock Artist"
					 }
				];

				var fuzzyList = [];

				list.forEach(function(d){
					var element = {};
					element["title"] = d;
					fuzzyList.push(element);
				});

				console.log("fuzzyEgList", fuzzyEgList);
				console.log("fuzzyList", fuzzyList);

				var options = {
					  id: "title",
					  shouldSort: true,
					  threshold: 0.4,
					  location: 0,
					  distance: 100,
					  maxPatternLength: 32,
					  minMatchCharLength: 1,
					  keys: [ "title" ]
				};

				var fuse = new Fuse(fuzzyList, options);
				result = fuse.search(txt);

				
				console.log(result);

			});

			options[search_field] = ["like", "%" + txt + "%"];
			if(result){
				result.forEach(function(res){
					console.log("REEESSSS", res);
					frappe.search.options.push({
						label: __('{0}: {1}', [meta.name, res.bold()]),
						value: __('{0}: {1}', [meta.name, res.bold()]),
						//route_options: options,
						onclick: function() {
							//cur_list.refresh();
						}
						//,match: txt
					});
				});
			}
		}
	},

	// new doc
	function(txt) {
		var ret = false;
		if(txt.split(" ")[0]==="new") {
			frappe.search.find(frappe.boot.user.can_create, txt.substr(4), function(match) {
				return {
					label: __("New {0}", [match.bold()]),
					value: __("New {0}", [match]),
					onclick: function() { frappe.new_doc(match, true); }
				}
			});
		}
	},

	// doctype list
	function(txt) {
		if (txt.toLowerCase().indexOf(" list")) {
			// remove list keyword
			txt = txt.replace(/ list/ig, "").trim();
		}

		frappe.search.find(frappe.boot.user.can_read, txt, function(match) {
			if(in_list(frappe.boot.single_types, match)) {
				return {
					label: __("{0}", [__(match).bold()]),
					value: __(match),
					route:["Form", match, match]
				}
			} else if(in_list(frappe.boot.treeviews, match)) {
				return {
					label: __("{0} Tree", [__(match).bold()]),
					value: __(match),
					route:["Tree", match]
				}
			} else {
				out = [
					{
						label: __("{0} List", [__(match).bold()]),
						value: __("{0} List", [__(match)]),
						route:["List", match]
					},
				];
				if(frappe.model.can_get_report(match)) {
					out.push({
						label: __("{0} Report", [__(match).bold()]),
						value: __("{0} Report", [__(match)]),
						route:["Report", match]
					});
				}
				if(frappe.boot.calendars.indexOf(match) !== -1) {
					out.push({
						label: __("{0} Calendar", [__(match).bold()]),
						value: __("{0} Calendar", [__(match)]),
						route:["Calendar", match]
					});

					out.push({
						label: __("{0} Gantt", [__(match).bold()]),
						value: __("{0} Gantt", [__(match)]),
						route:["List", match, "Gantt"]
					});
				}
				return out;
			}
		});
	},

	// reports
	function(txt) {
		frappe.search.find(keys(frappe.boot.user.all_reports), txt, function(match) {
			//console.log("Reports", (frappe.boot.user.all_reports));
			var report = frappe.boot.user.all_reports[match];
			var route = [];
			
			if(report.report_type == "Report Builder")
				route = ["Report", report.ref_doctype, match];
			else
				route = ["query-report",  match];

			return {
				label: __("Report {0}", [__(match).bold()]),
				value: __("Report {0}", [__(match)]),
				route: route
			}
		});
	},

	// pages
	function(txt) {
		frappe.search.find(keys(frappe.search.pages), txt, function(match) {
			//console.log("Pages", frappe.search.pages)
			return {
				label: __("Open {0}", [__(match).bold()]),
				value: __("Open {0}", [__(match)]),
				route: [frappe.search.pages[match].route || frappe.search.pages[match].name]
			}
		});

		// calendar
		var match = 'Calendar';
		if(__('calendar').indexOf(txt.toLowerCase()) === 0) {
			frappe.search.options.push({
				label: __("Open {0}", [__(match).bold()]),
				value: __("Open {0}", [__(match)]),
				route: [match, 'Event'],
				match: match
			});
		}
	},

	// modules
	function(txt) {
		frappe.search.find(keys(frappe.modules), txt, function(match) {
			var module = frappe.modules[match];

			if(module._doctype) return;

			ret = {
				label: __("Open {0}", [__(match).bold()]),
				value: __("Open {0}", [__(match)]),
			}
			if(module.link) {
				ret.route = [module.link];
			} else {
				ret.route = ["Module", match];
			}
			return ret;
		});
	},

	// in
	function(txt) {
		if(in_list(txt.split(" "), "in")) {
			parts = txt.split(" in ");
			frappe.search.find(frappe.boot.user.can_read, parts[1], function(match) {
				//console.log("Can read: ", frappe.boot.user.can_read);
				return {
					label: __('Find {0} in {1}', [__(parts[0]).bold(), __(match).bold()]),
					value: __('Find {0} in {1}', [__(parts[0]), __(match)]),
					route_options: {"name": ["like", "%" + parts[0] + "%"]},
					route: ["List", match]
				}
			});
		}
	},

	// calculator
	function(txt) {
		var first = txt.substr(0,1);
		if(first==parseInt(first) || first==="(" || first==="=") {
			if(first==="=") {
				txt = txt.substr(1);
			}

			try {
				var val = eval(txt);
				var formatted_value = __('{0} = {1}', [txt, (val + '').bold()]);
				frappe.search.options.push({
					label: formatted_value,
					value: __('{0} = {1}', [txt, val]),
					match: val,
					onclick: function(match) {
						//console.log("match1 ", match);
						msgprint(formatted_value, "Result");
					}
				});
			} catch(e) {
				// pass
			}

		};
	},
];
