frappe.provide('frappe.search');

frappe.search.SearchDialog = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
	},

	make: function() {
		var d;
		if(!frappe.search.dialog) {
			d = new frappe.ui.Dialog();
			frappe.search.dialog = d;
		} else {
			d = frappe.search.dialog;
			$(d.body).empty();
		}

		$('<div class="row results-area">' +
			'<div class="col-md-2 col-sm-2 hidden-xs layout-side-section search-sidebar"></div>' +
			'<div class="col-md-10 col-sm-10 layout-main-section search-results"></div>' +
		'</div>').appendTo($(d.body));
		$(d.header).html($(frappe.render_template("search_header")));

		this.search_dialog = d;
		this.$search_modal = $(d.$wrapper);
		this.$search_modal.addClass('search-dialog');
		this.$modal_body = $(d.body);
		this.$input = this.$search_modal.find(".search-input");

		this.$results_area = this.$search_modal.find(".results-area");
		this.$sidebar = this.$results_area.find(".search-sidebar");
		this.$search_results = this.$results_area.find(".search-results");

		this.$modal_body.append($('<div class="search-intro-placeholder"><span>' +
			'<i class="mega-octicon octicon-telescope"></i><p>'+__("Search for anything")+'</p></span></div>'));

		this.setup();
	},

	setup: function() {
		this.current_keyword = "";
		this.reset();
		this.bind_input();
		this.bind_events();
	},

	reset: function() {
		this.$results_area.addClass('hide');
		this.$modal_body.find('.search-intro-placeholder').removeClass('hide');
		this.$sidebar.empty();
		this.$search_results.empty();
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
					me.get_results(keywords);
				} else {
					me.current_type = '';
				}
			}, 300));
		});
	},

	bind_events: function() {
		var me = this;
		// Sidebar
		this.$sidebar.on('click', '.list-link',  function() {
			var link = $(this);
			me.$sidebar.find(".list-link").removeClass("active");
			link.addClass("active");
			var type = link.attr('data-category');
			me.$search_results.empty().html(me.full_lists[type]);
			me.$search_results.find('.module-section-link').first().focus();
		});

		// Summary more links
		this.$search_results.on('click', '.section-more', function() {
			var type = $(this).attr('data-category');
			me.$sidebar.find('*[data-category="'+ type +'"]').trigger('click');
		});

		// Back-links (mobile-view)
		this.$search_results.on('click', '.all-results-link', function() {
			me.$sidebar.find('*[data-category="All Results"]').trigger('click');
		});

		// Full list more links
		this.$search_results.on('click', '.list-more', function() {
			// increment current result count as well in its data attr

		});

		this.bind_keyboard_events();
	},

	bind_keyboard_events: function() {

	},

	// Search types
	searches: {
		global: function(keywords, start, limit, callback) {
			return frappe.search.utils.get_all_global_results(keywords, start, limit, callback);
		},
		help: function(keywords) {

		}
	},

	// Show modal with first results
	init_search: function(keywords, search_type) {
		var me = this;
		this.get_results(keywords, search_type);
		this.search_dialog.show();
		this.$input.val(keywords);
		setTimeout(function() { me.$input.select(); }, 500);
	},

	//
	get_results: function(keywords, search_type) {
		this.current_keyword = keywords;
		var result_sets = this.searches[search_type](keywords, 0, 20, this.render_data.bind(this));

		// get results type object megatype arrays [ {title:"Item", results: [{a:foo, b:..}, {}, ()]}, {title:"", re} ]   and so on
		// pass them onto render_results
		// categorize acc to modal: top, quick_links, results --> for summary
	},

	render_data: function(result_sets, keywords) {
		var me = this;
		var sidelist = $('<ul class="module-sidebar-nav overlay-sidebar nav nav-pills nav-stacked search-sidelist"></ul>');
		this.full_lists = {};
		result_sets.forEach(function(set) {
			var sidebar_item_html = '<li class="module-sidebar-item list-link" data-category="{0}">' +
				'<a><span>{0}</span><i class="octicon octicon-chevron-right pull-right"' +
				'></a></li>';
			var $sidebar_item = $(__(sidebar_item_html, [set.title]));
			sidelist.append($sidebar_item);

			me.full_lists[set.title] = me.render_full_list(set.title, set.results, true);


		});

		// gather all the results objects, collect type and list from each of each
		// make sidebar item array, full_list dict,
		// render_summary (only if sidebar array has > 1)

		this.$sidebar.append(sidelist);

		this.$modal_body.find('.search-intro-placeholder').addClass('hide');
		this.$results_area.removeClass('hide');
	},

	render_summary: function() {
		//
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
			results_col.append('<a href="#" class="list-more small" data-search="'+ this.search_type +
				'" data-category="'+ type + '" style="margin-top:10px">'+__("More...")+'</a>');
		}
		return results_list;
	},

	render_result: function(type, result, condensed) {
		// big ... based on result contents ... keep expanding
		var link_html = '<div class="result '+ type +'-result">' +
			'<b><a href="{0}" class="module-section-link small">{1}</a></b>' +
			'<p class="small">{2}</p>' +
			'</div>';
		return $(__(link_html, ['#'+result.route.join('/'), result.label, result.description]));
	}

});