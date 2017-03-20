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
		this.full_lists = {};
		this.bind_input();
		this.bind_events();
	},

	update: function($r) {
		// TO DO: hide/remove all loading elements
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
				'<div class="search-placeholder"><span>' +
				'<i class="mega-octicon octicon-telescope"></i><p>'+
				status_text + '</p></span></div>' +
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
				keywords = me.$input.val();
				if(keywords.length > 1) {
					me.get_results(keywords);
				} else if (keywords.length === 0) {
					me.put_placeholder(me.search.empty_state_text);
				} else {
					me.current_type = '';
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
			// increment current result count as well in its data attr

		});

		// Switch to global search link
		this.$modal_body.on('click', '.switch-to-global-search', function() {
			me.search = me.searches['global_search'];
			me.$input.attr("placeholder", me.search.input_placeholder);
			me.put_placeholder(me.search.empty_state_text);
			me.get_results(me.current_keyword);
		});

		// Help results
		// this.$modal_body.on('click', 'a[data-path]', frappe.help.show_results);
		this.bind_keyboard_events();
	},

	bind_keyboard_events: function() {
		var me = this;
		this.$search_modal.on('keydown', function(e) {

			function focus_input() {
				if(!me.$input.is(":focus")) {
					me.$input.focus();
				}
			}

			// Backspace key triggers input
			if(e.which === 8) focus_input();

			if(me.$modal_body.find('.list-link').length > 1) {

				if(me.modal_state === 0) {
					// DOWN and UP keys navigate sidebar
					if(e.which === DOWN_ARROW || e.which === TAB) {
						e.preventDefault();
						var $link = me.$modal_body.find('.list-link.select').next();
						if($link.length > 0) {
							me.$modal_body.find('.list-link').removeClass('select');
							$link.addClass('select');
						}
						focus_input();
					} else if(e.which === UP_ARROW) {
						e.preventDefault();
						var $link = me.$modal_body.find('.list-link.select').prev();
						if($link.length > 0) {
							me.$modal_body.find('.list-link').removeClass('select');
							$link.addClass('select');
						}
						focus_input();
					} else if (e.which === 39 || e.which === 13) {
						// This state has only right arrow
						e.preventDefault();
						// me.modal_state = 1;
						me.$modal_body.find('.search-sidebar').find('.list-link.select').trigger('click');
						// call_focusser(); // Should remember last focussed result?
						focus_input();
					}

				} else {
					// // DOWN and UP keys navigate results
					if(e.which === DOWN_ARROW || e.which === TAB) {
						// only focus on down key, don't trigger
						var link = me.$modal_body.find('.list-link.select').next();
						me.$modal_body.find('.list-link').removeClass('select');
					} else if(e.which === UP_ARROW) {
						me.$modal_body.find('.list-link.active').prev();
					} else if(e.which === 37) {
						me.modal_state = 0;
					} else if (e.which === 13) {
						// Tab key rolls back after the last result
						if(me.results_area.find('a').last().is(":focus")) {
							e.preventDefault();
							me.results_area.find('.module-section-link').first().focus();
						}
					}
				}
			}
		});
		this.$search_modal.on('keypress', function(e) {
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
		// TO DO: put loading sign: if placeholder present then that, else the normal one
		this.search.get_results(keywords, this.parse_results.bind(this));
	},

	parse_results: function(result_sets) {
		result_sets = result_sets.filter(function(set) {
			return set.results.length > 0;
		})
		if(result_sets.length > 0) {
			// TO DO: de-duplicate
			this.render_data(result_sets);
		} else {
			this.put_placeholder(this.search.no_results_status(this.current_keyword));
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

		result_sets.forEach(function(set) {
			$sidebar.append($(__(sidebar_item_html, [set.title])));
			me.add_section_to_summary(set.title, set.results);
			me.full_lists[set.title] = me.render_full_list(set.title, set.results, true);
		});

		if(result_sets.length > 1) {
			$sidebar.prepend($(__(sidebar_item_html, ["All Results"])));
		}

		this.update($search_results.clone());
		this.$modal_body.find('.list-link').first().trigger('click');
	},

	render_full_list: function(type, results, more) {
		var me = this;
		var $results_list = $(' <div class="module-body"><div class="row module-section full-list '+
			type+'-section">'+'<div class="col-sm-12 module-section-column">' +
			'<div class="back-link"><a class="all-results-link small"> All Results</a></div>' +
			'<div class="h4 section-head">'+type+'</div>' +
			'<div class="section-body"></div></div></div></div>');

		var $results_col = $results_list.find('.module-section-column');
		results.forEach(function(result) {
			$results_col.append(me.render_result(type, result));
		});
		if(more) {
			$results_col.append('<a class="list-more small" data-search="'+ this.search_type +
				'" data-category="'+ type + '" style="margin-top:10px">'+__("More...")+'</a>');
		}
		return $results_list;
	},

	add_section_to_summary: function(type, results) {
		var me = this;
		var are_expansive = results[0]["description" || "image" || "subtypes"] || false;
		var [section_length, col_width] = are_expansive ? [3, "12"] : [4, "6"];

		// check state of last summary section
		if(this.full_lists['All Results'].find('.module-section').last().find('.col-sm-6').length !== 1
			|| are_expansive) {
			this.full_lists['All Results'].append($('<div class="row module-section"></div>'));
		}
		var $results_col = $('<div class="col-sm-'+ col_width +' module-section-column" data-type="'+type+'">' +
			'<div class="h4 section-head">'+type+'</div>' +
			'<div class="section-body"></div>'+
			'</div>');
		results.slice(0, section_length).forEach(function(result) {
			$results_col.append(me.render_result(type, result));
		});
		if(results.length > section_length) {
			$results_col.append('<a class="section-more small" data-category="'
				+ type + '" style="margin-top:10px">'+__("More...")+'</a>');
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

		function make_description(desc){
			// TO DO: process?
			return desc;
		}

		$result.append($('<b><a '+ get_link(result) +' class="module-section-link small">'+ result.label +'</a></b>'));

		if(result.description) {
			$result.append(make_description('<p class="small">'+ result.description +'</p>'));
		}

		if(result.image) {
			$result.append(result.image);
		}

		if(result.subtypes) {
			result.subtypes.forEach(function(subtype) {
				$result.append(subtype);
			});
		}

		return $result;
	},

	// Search objects (can be relocated)
	searches: {
		global_search: {
			input_placeholder: __("Global Search"),
			empty_state_text: __("Search for anything"),
			no_results_status: (keyword) => __("No results found for '" + keyword + "'"),
			get_results: function(keywords, callback) {
				var start = 0, limit = 20;
				var results = frappe.search.utils.get_nav_results(keywords);
				frappe.search.utils.get_all_global_results(keywords, start, limit)
					.then(function(global_results) {
						results = results.concat(global_results);
						return frappe.search.utils.get_help_results(keywords);
					}).then(function(help_results) {
						results = results.concat(help_results);
						callback(results);
					}, function (err) {
						console.error(err);
					});
			}
		},
		help: {
			input_placeholder: __("Search Help"),
			empty_state_text: __("Search the docs"),
			no_results_status: (keyword) => __("No results found for '" + keyword +
				"' in Help<br>Search <a class='switch-to-global-search'>globally</a>"),
			get_results: function(keywords, callback) {
				var results = [];
				frappe.search.utils.get_help_results(keywords)
					.then(function(help_results) {
						results = results.concat(help_results);
						return frappe.search.utils.get_forum_results(keywords);
					}).then(function(forum_results) {
						results = results.concat(forum_results);
						callback(results);
					}, function (err) {
						console.error(err);
					});
			}
		}
	},

});