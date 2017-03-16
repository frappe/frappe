frappe.provide('frappe.search');

frappe.search.SearchDialog = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
	},

	make: function() {
		var d = new frappe.ui.Dialog();
		$('<div class="row search-results">' +
			'<div class="col-md-2 col-sm-2 hidden-xs layout-side-section search-sidebar"></div>' +
			'<div class="col-md-10 col-sm-10 layout-main-section results-area"></div>' +
		'</div>').appendTo($(d.body));
		$(d.header).html($(frappe.render_template("search_header")));

		this.search_dialog = d;
		this.$search_modal = $(d.$wrapper);
		this.$search_modal.addClass('search-dialog');
		this.$modal_body = $(d.body);
		this.$input = this.$search_modal.find(".search-input");

		this.$search_results = $('<div class="row search-results hide">' +
			'<div class="col-md-2 col-sm-2 hidden-xs layout-side-section search-sidebar"></div>' +
			'<div class="col-md-10 col-sm-10 layout-main-section results-area"></div>' +
		'</div>');
		this.$sidebar = this.$search_results.find(".search-sidebar");
		this.$results_area = this.$search_results.find(".results-area");

		// this.$modal_body.append($('<div class="search-intro-placeholder"><span>' +
			// '<i class="mega-octicon octicon-telescope"></i><p>'+__("Search for anything")+'</p></span></div>'));

		this.setup();
	},

	setup: function() {
		this.current_keyword = "";
		this.full_lists = {};
		this.reset();
		this.modal_state = 0;
		this.bind_input();
		this.bind_events();
	},

	reset: function() {
		// this.$search_results.addClass('hide');
		// this.$modal_body.find('.search-intro-placeholder').removeClass('hide');
		this.$sidebar.empty();
		this.$results_area.empty();
	},

	// Bind events
	bind_input: function() {
		var me = this;
		this.$input.on("input", function() {
			var $this = $(this);
			clearTimeout($this.data('timeout'));

			$this.data('timeout', setTimeout(function() {
				if(me.$input.val() === me.current_keyword) return;
				keywords = me.$input.val();
				me.reset();
				if(keywords.length > 2) {
					me.modal_state = 0;
					me.get_results(keywords);
				} else {
					me.current_type = '';
				}
			}, 300));
		});
	},

	bind_events: function() {
		var me = this;
		// var $sidebar = this.$modal_body.find('.search-sidebar');
		// var $results_area = this.$modal_body.find('.results-area');

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

		this.bind_keyboard_events();
	},

	bind_keyboard_events: function() {
		var me = this;
		this.$search_modal.on('keydown', function(e) {
			if(me.$modal_body.find('.list-link').length > 1) {
				function focus_input() {
					if(!me.$input.is(":focus")) {
						me.$input.focus();
					}
				}

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

	// Search types (can be relocated)
	searches: {
		global: function(keywords, callback) {
			var results = {}, start = 0, limit = 20;
			frappe.search.utils.get_all_global_results(keywords, start, limit)
				.then(function(global_results) {
					results.global = global_results;
					return frappe.search.utils.get_help_results(keywords);
				}).then(function(help_results) {
					results.help = help_results;
					callback(results);
				}, function (err) {
					console.error(err);
				});
		},
		help: function(keywords, callback) {
			frappe.search.utils.get_help_results(keywords)
				.then(function(help_results) {
					callback(help_results);
				}, function (err) {
					console.error(err);
				});
		}
	},

	// Show modal with first results
	init_search: function(keywords, search_type) {
		var me = this;
		this.search = search_type;
		this.reset();
		this.get_results(keywords, search_type);
		this.search_dialog.show();
		this.$input.val(keywords);
		setTimeout(function() { me.$input.select(); }, 500);
	},

	//
	get_results: function(keywords) {
		this.current_keyword = keywords;
		var result_sets = this.searches[this.search](keywords, this.render_data.bind(this));
		// get results type object megatype arrays [ {title:"Item", results: [{a:foo, b:..}, {}, ()]}, {title:"", re} ]   and so on
		// pass them onto render_results
		// categorize acc to modal: top, quick_links, results --> for summary
	},

	render_data: function(result_sets) {
		var me = this;
		var sidelist = $('<ul class="module-sidebar-nav overlay-sidebar nav nav-pills nav-stacked search-sidelist"></ul>');
		var sidebar_item_html = '<li class="module-sidebar-item list-link" data-category="{0}">' +
			'<a><span>{0}</span><i class="octicon octicon-chevron-right pull-right"' +
			'></a></li>';
		this.full_lists = {	'All Results': $('<div class="module-body results-summary"></div>') };

		result_sets.filter(function(set) {
			return set.results.length > 0;
		}).forEach(function(set) {
			sidelist.append($(__(sidebar_item_html, [set.title])));
			me.add_section_to_summary(set.title, set.results);
			me.full_lists[set.title] = me.render_full_list(set.title, set.results, true);
		});

		// gather all the results objects, collect type and list from each of each
		// make sidebar item array, full_list dict,
		// render_summary (only if sidebar array has > 1)

		if(sidelist.find('.list-link').length > 1) {
			sidelist.prepend($(__(sidebar_item_html, ["All Results"])));
		}

		this.$sidebar.append(sidelist);
		// this.$modal_body.find('.search-intro-placeholder').addClass('hide');

		// Last step
		var $r = this.$search_results.clone();

		this.$modal_body.append($r);
		this.$modal_body.find('.search-results').first().addClass("hide");
		$r.removeClass("hide");
		this.$modal_body.find('.search-results').first().remove();
		this.$modal_body.find('.list-link').first().trigger('click');
	},

	render_full_list: function(type, results, more) {
		var me = this;
		var results_list = $(' <div class="module-body"><div class="row module-section full-list '+
			type+'-section">'+'<div class="col-sm-12 module-section-column">' +
			'<div class="back-link"><a class="all-results-link small"> All Results</a></div>' +
			'<div class="h4 section-head">'+type+'</div>' +
			'<div class="section-body"></div></div></div></div>');

		var results_col = results_list.find('.module-section-column');
		results.forEach(function(result) {
			results_col.append(me.render_result(type, result, false));
		});
		if(more) {
			results_col.append('<a class="list-more small" data-search="'+ this.search_type +
				'" data-category="'+ type + '" style="margin-top:10px">'+__("More...")+'</a>');
		}
		return results_list;
	},

	add_section_to_summary: function(type, results) {
		var me = this, section_length, col_width;
		var are_expansive = results[0]["description" || "image" || "subtypes"] || false;
		[section_length, col_width] = are_expansive ? [3, "12"] : [4, "6"];

		// check state of last summary section
		if(this.full_lists['All Results'].find('.module-section').last().find('.col-sm-6').length !== 1
			|| are_expansive) {
			this.full_lists['All Results'].append($('<div class="row module-section"></div>'));
		}

		var results_col = $('<div class="col-sm-'+ col_width +' module-section-column" data-type="'+type+'">' +
			'<div class="h4 section-head">'+type+'</div>' +
			'<div class="section-body"></div>'+
			'</div>');
		results.slice(0, section_length).forEach(function(result) {
			results_col.append(me.render_result(type, result));
		});
		if(results.length > section_length) {
			results_col.append('<a class="section-more small" data-category="'
				+ type + '" style="margin-top:10px">'+__("More...")+'</a>');
		}
		this.full_lists['All Results'].find('.module-section').last().append(results_col);
	},

	render_result: function(type, result) {
		// big ... based on result contents ... keep expanding
		var link_html = '<div class="result '+ type +'-result">' +
			'<b><a href="{0}" class="module-section-link small">{1}</a></b>' +
			'<p class="small">{2}</p>' +
			'</div>';
		return $(__(link_html, ['#'+result.route.join('/'), result.label, result.description]));
	},

});