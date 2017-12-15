frappe.provide('frappe.search');

frappe.search.SearchDialog = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
	},

	make: function() {
		var d = new frappe.ui.Dialog();
		$(d.header).html($(frappe.render_template("search_header")));
		this.search_dialog = d;
		this.$search_modal = $(d.$wrapper).addClass('search-dialog');
		this.$modal_body = $(d.body);
		this.$input = this.$search_modal.find(".search-input");
		this.setup();
	},

	setup: function() {
		this.modal_state = 0;
		this.current_keyword = "";
		this.more_count = 20;
		this.full_lists = {};
		this.nav_lists = {};
		this.bind_input();
		this.bind_events();
	},

	update: function($r) {
		this.$search_modal.find('.loading-state').addClass('hide');
		this.$modal_body.append($r);
		if(this.$modal_body.find('.search-results').length > 1) {
			this.$modal_body.find('.search-results').first().addClass("hide");
			$r.removeClass("hide");
			this.$modal_body.find('.search-results').first().remove();
		} else {
			$r.removeClass("hide");
		}
	},

	put_placeholder: function(status_text) {
		var $placeholder = $('<div class="row search-results hide">' +
				'<div class="empty-state"><span style="margin-top: -100px">' +
				'<i class="mega-octicon octicon-telescope status-icon">' +
				'<i class="fa fa-square cover twinkle-one hide" style="left:0px;"></i>'+
				'<i class="fa fa-square cover twinkle-two hide" style="left:8px; top:5px;"></i>'+
				'<i class="fa fa-square cover twinkle-three hide" style="left:13px; top:-3px;"></i></i>'+
				'<p>' + status_text + '</p></span></div>' +
			'</div>');
		this.update($placeholder);
	},

	bind_input: function() {
		var me = this;
		this.$input.on("input", function() {
			var $this = $(this);
			clearTimeout($this.data('timeout'));
			$this.data('timeout', setTimeout(function() {
				if(me.$input.val() === me.current_keyword) return;
				var keywords = me.$input.val();
				if(keywords.length > 1) {
					me.get_results(keywords);
				} else {
					me.current_keyword = "";
					me.put_placeholder(me.search.empty_state_text);
				}
			}, 300));
		});
	},

	bind_events: function() {
		var me = this;

		// Sidebar
		this.$modal_body.on('click', '.list-link',  function() {
			var link = $(this);
			me.$modal_body.find('.search-sidebar').find(".list-link").removeClass("active select");
			link.addClass("active select");
			var type = link.attr('data-category');
			me.$modal_body.find('.results-area').empty().html(me.full_lists[type]);
			me.$modal_body.find('.module-section-link').first().focus();
			me.current_type = type;
		});

		// Summary more links
		this.$modal_body.on('click', '.section-more', function() {
			var type = $(this).attr('data-category');
			me.$modal_body.find('.search-sidebar').find('*[data-category="'+ type +'"]').trigger('click');
		});

		// Back-links (mobile-view)
		this.$modal_body.on('click', '.all-results-link', function() {
			me.$modal_body.find('.search-sidebar').find('*[data-category="All Results"]').trigger('click');
		});

		// Full list more links
		this.$modal_body.on('click', '.list-more', function() {
			var type = $(this).attr('data-category');
			var fetch_type = $(this).attr('data-search');
			var current_count = me.$modal_body.find('.result').length;
			if(fetch_type === "Global") {
				frappe.search.utils.get_global_results(me.current_keyword,
					current_count, me.more_count, type)
					.then(function(doctype_results) {
						me.add_more_results(doctype_results);
					}, function (err) {
						console.error(err);
					});
			} else {
				var results = me.nav_lists[type].slice(0, me.more_count);
				me.nav_lists[type].splice(0, me.more_count);
				me.add_more_results([{title: type, results: results}]);
			}
		});

		// Switch to global search link
		this.$modal_body.on('click', '.switch-to-global-search', function() {
			me.search = me.searches['global_search'];
			me.$input.attr("placeholder", me.search.input_placeholder);
			me.put_placeholder(me.search.empty_state_text);
			me.get_results(me.current_keyword);
		});

		// Help results
		this.$modal_body.on('click', 'a[data-path]', frappe.help.show_results);
		this.bind_keyboard_events();
	},

	bind_keyboard_events: function() {
		var me = this;
		this.$search_modal.on('keydown', function(e) {

			if(me.$modal_body.find('.list-link').length > 1) {
				if(me.modal_state === 0) {
					// DOWN and UP keys navigate sidebar
					var { UP_ARROW, DOWN_ARROW, TAB } = frappe.ui.keyCode;
					if(e.which === DOWN_ARROW || e.which === TAB) {
						e.preventDefault();
						var $link = me.$modal_body.find('.list-link.select').next();
						if($link.length > 0) {
							// me.$modal_body.find('.list-link').removeClass('select');
							// $link.addClass('select');
							$link.trigger('click');
						}
					} else if(e.which === UP_ARROW) {
						e.preventDefault();
						var $link = me.$modal_body.find('.list-link.select').prev();
						if($link.length > 0) {
							$link.trigger('click');
						}
					}
				}
			}

			if(!me.$input.is(":focus")) {
				me.$input.focus();
			}
		});

	},

	init_search: function(keywords, search_type) {
		var me = this;
		this.search = this.searches[search_type];
		this.$input.attr("placeholder", this.search.input_placeholder);
		this.put_placeholder(this.search.empty_state_text);
		this.get_results(keywords);
		this.search_dialog.show();
		this.$input.val(keywords);
		setTimeout(function() { me.$input.select(); }, 500);
	},

	get_results: function(keywords) {
		this.current_keyword = keywords;
		if(this.$modal_body.find('.empty-state').length > 0) {
			this.put_placeholder(__("Searching ..."));
			this.$modal_body.find('.cover').removeClass('hide')
		} else {
			this.$search_modal.find('.loading-state').removeClass('hide');
		}
		this.search.get_results(keywords, this.parse_results.bind(this));
	},

	parse_results: function(result_sets, keyword) {
		result_sets = result_sets.filter(function(set) {
			return set.results.length > 0;
		})
		if(result_sets.length > 0) {
			this.render_data(result_sets);
		} else {
			this.put_placeholder(this.search.no_results_status(keyword));
		}
	},

	render_data: function(result_sets) {
		var me = this;
		var $search_results = $(frappe.render_template("search")).addClass('hide');
		var $sidebar = $search_results.find(".search-sidebar").empty();
		var sidebar_item_html = '<li class="module-sidebar-item list-link" data-category="{0}">' +
			'<a><span class="ellipsis">{0}</span><i class="octicon octicon-chevron-right"' +
			'></a></li>';

		this.modal_state = 0;
		this.full_lists = {	'All Results': $('<div class="module-body results-summary"></div>') };
		this.nav_lists = {};

		result_sets.forEach(function(set) {
			$sidebar.append($(__(sidebar_item_html, [set.title])));
			me.add_section_to_summary(set.title, set.results);
			me.full_lists[set.title] = me.render_full_list(set.title, set.results, set.fetch_type);
		});

		if(result_sets.length > 1) {
			$sidebar.prepend($(__(sidebar_item_html, ["All Results"])));
		}

		this.update($search_results.clone());
		this.$modal_body.find('.list-link').first().trigger('click');
	},

	render_full_list: function(type, results, fetch_type) {
		var me = this, max_length = 20;
		var $results_list = $(' <div class="module-body"><div class="row module-section full-list '+
			type+'-section">'+'<div class="col-sm-12 module-section-column">' +
			'<div class="back-link"><a class="all-results-link small"> All Results</a></div>' +
			'<div class="h4 section-head">'+type+'</div>' +
			'<div class="section-body"></div></div></div></div>');

		var $results_col = $results_list.find('.module-section-column');
		for(var i = 0; i < max_length && results.length > 0; i++) {
			$results_col.append(me.render_result(type, results.shift()));
		}
		if(results.length > 0) {
			if(fetch_type === "Nav") this.nav_lists[type] = results;
			$results_col.append('<a class="list-more small" data-search="'+ fetch_type +
				'" data-category="'+ type + '" data-count="' + max_length +
				'" style="margin-top:10px">'+__("More...")+'</a>');
		}
		return $results_list;
	},

	add_section_to_summary: function(type, results) {
		var me = this;
		var are_expansive = false;
		var margin_more = "10px";
		for(var i = 0; i < results.length; i++) {
			if(results[i]["description" || "image" || "subtypes"] || false) {
				are_expansive = true;
				break;
			}
		}
		if(results[0].image) margin_more = "20px";
		var [section_length, col_width] = are_expansive ? [3, "12"] : [4, "6"];

		// check state of last summary section
		if(this.full_lists['All Results'].find('.module-section').last().find('.col-sm-6').length !== 1
			|| are_expansive) {
			this.full_lists['All Results'].append($('<div class="row module-section"></div>'));
		}
		var $results_col = $(`<div class="col-sm-${col_width} module-section-column" data-type="${type}">
			<div class="h4 section-head">${type}</div>
			<div class="section-body"></div>
			</div>`);
		results.slice(0, section_length).forEach(function(result) {
			$results_col.append(me.render_result(type, result));
		});
		if(results.length > section_length) {
			$results_col.append(`<div style="margin-top:${margin_more}"><a class="section-more small"
				data-category="${type}">${__("More...")}</a></div>`);
		}

		this.full_lists['All Results'].find('.module-section').last().append($results_col);
	},

	render_result: function(type, result) {
		var $result = $('<div class="result '+ type +'-result"></div>');

		function get_link(result) {
			var link;
			if(result.route) {
				link = 'href="#'+result.route.join('/')+'" ';
			} else if (result.data_path) {
				link = 'data-path="'+result.data_path+'"';
			} else {
				link = "";
			}
			return link;
		}

		if(result.image) {
			$result.append('<div class="result-image"><img data-name="' + result.label + '" src="'+ result.image +'" alt="' + result.label + '"></div>');
		} else if (result.image === null) {
			$result.append('<div class="result-image"><div class="flex-text"><span>'+ frappe.get_abbr(result.label) +'</span></div></div>');
		}

		var title_html = '<a '+ get_link(result) +' class="module-section-link small">'+ result.label +'</a>';
		var $result_text = $('<div style="display: inline-block;"></div>');
		if(result.description) {
			$result_text.append($('<b>' + title_html + '</b>'));
			$result_text.append('<p class="small">'+ result.description +'</p>');
		} else {
			$result_text.append($(title_html));
			if(result.route_options) {
				frappe.route_options = result.route_options;
			}
			$result_text.on('click', (e) => {
				this.search_dialog.hide();
				if(result.onclick) {
					result.onclick(result.match);
				} else {
					var previous_hash = window.location.hash;
					frappe.set_route(result.route);

					// hashchange didn't fire!
					if (window.location.hash == previous_hash) {
						frappe.route();
					}
				}
			});
		}

		$result.append($result_text);

		if(result.subtypes) {
			result.subtypes.forEach(function(subtype) {
				$result.append(subtype);
			});
		}

		return $result;
	},

	add_more_results: function(results_set) {
		var me = this;
		var more_results = $('<div class="more-results last"></div>');
		results_set[0].results.forEach(function(result) {
			more_results.append(me.render_result(results_set[0].title, result));
		});
		this.$modal_body.find('.list-more').before(more_results);

		if(results_set[0].results.length < this.more_count) {
			// hide more button and add a result count
			this.$modal_body.find('.list-more').hide();
			var no_of_results = this.$modal_body.find('.result').length;
			var no_of_results_cue = $('<p class="results-status text-muted small">'+
				no_of_results +' results found</p>');
			this.$modal_body.find(".more-results:last").append(no_of_results_cue);
		}
		this.$modal_body.find('.more-results.last').slideDown(200, function() {});
	},

	// Search objects
	searches: {
		global_search: {
			input_placeholder: __("Global Search"),
			empty_state_text: __("Search for anything"),
			no_results_status: (keyword) => __("<p>No results found for '" + keyword + "' in Global Search</p>"),

			get_results: function(keywords, callback) {
				var start = 0, limit = 100;
				var results = frappe.search.utils.get_nav_results(keywords);
				frappe.search.utils.get_global_results(keywords, start, limit)
					.then(function(global_results) {
						results = results.concat(global_results);
						return frappe.search.utils.get_help_results(keywords);
					}).then(function(help_results) {
						results = results.concat(help_results);
						callback(results, keywords);
					}, function (err) {
						console.error(err);
					});
			}
		},
		help: {
			input_placeholder: __("Search Help"),
			empty_state_text: __("Search the docs"),
			no_results_status: (keyword) => __("<p>No results found for '" + keyword +
				"' in Help</p><p>Would you like to search <a class='switch-to-global-search text-muted' "+
				"style='text-decoration: underline;'>globally</a>" +
				" or the <a href='https://discuss.erpnext.com' class='forum-link text-muted' " +
				"style='text-decoration: underline;'>forums</a> instead?</p>"),

			get_results: function(keywords, callback) {
				var results = [];
				frappe.search.utils.get_help_results(keywords)
					.then(function(help_results) {
						results = results.concat(help_results);
						callback(results, keywords);
					}, function (err) {
						console.error(err);
					});
			}
		}
	},

});