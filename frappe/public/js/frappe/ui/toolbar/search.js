frappe.provide('frappe.search');

frappe.search.Search = Class.extend({
	init: function() {
        this.setup();
	},

	setup: function() {
		var me = this;
		var d = new frappe.ui.Dialog();
		this.awesome_bar = new frappe.search.AwesomeBar();

		$(frappe.render_template("search")).appendTo($(d.body));
		$(d.header).html($(frappe.render_template("search_header")));

		this.search_dialog = d;
		this.search_modal = $(d.$wrapper);
		this.search_modal.addClass('search-modal');
		this.result_area = this.search_modal.find(".result-area .module-body");

		this.condensed_length = 3;
	},

	on_awesome_bar: function(keywords) {
		var me = this;
		this.search_modal.find(".search-input").on("input", function (e) {
			var keywords = me.search_modal.find(".search-input").val();
			if(keywords !== ""){
				me.get_all_results(keywords);
			} else {
				me.result_area.html("");
			}
		});
		this.search_modal.find(".search-input").val(keywords);
		this.get_all_results(keywords);
		// timeout hack: focus and select input
		setTimeout(function() { me.search_modal.find(".search-input").select(); }, 500);
	},

	on_help_search: function() {
		var me = this;
		this.search_modal.find(".search-input").on("input", function (e) {
			var keywords = me.search_modal.find(".search-input").val();
			if(keywords !== ""){
				me.get_help_menu_results(keywords);
			} else {
				me.result_area.html("");
			}
		});
		this.search_modal.find(".search-input").val(keywords);
		this.get_help_menu_results(keywords);
		// timeout hack: focus and select input
		setTimeout(function() { me.search_modal.find(".search-input").select(); }, 500);
	},

	get_all_results: function(keywords) {
		this.setup_search(keywords);
		this.get_search_results(keywords);
		this.get_nav_results(keywords);
		this.get_help_results(keywords);
		
	},

	get_help_menu_results: function(keywords) {
		this.setup_search(keywords);
		this.get_help_results(keywords);
	},

	setup_search: function(keywords) {
		this.results_modules = [];
		this.search_modal.find(".search-list").addClass("hide");
		this.search_modal.find(".nav-list").addClass("hide");
		this.search_modal.find(".help-list").addClass("hide");
		// Set the results-area to no results found 
		this.result_area.empty();
		this.result_area.html('<p class="result-status text-muted">'+
			'No results found for: '+ "'"+ keywords +"'" +'</p>');
	},

	bold_keywords: function(keywords){
		this.result_area.contents().filter(function() {
			return this.nodeType == 3
		}).each(function(){
			console.log("inside bold_keywords");
			this.textContent = this.textContent.replace(keywords, keywords.bold);
		});
	},

	get_search_results: function(keywords) {
		var me = this;
		this.search_results = {};
		frappe.call({
			method: "frappe.utils.global_search.search",
			args: {
				text: keywords, start: 0, limit: 20
			},
			callback: function(r) {
				if(r.message) {
					me.format_search_results(r.message, keywords);
					me.make_all_results_modules();
				}
			}
		});
	},

	format_search_results: function(search_data, keywords) {
		var me = this;
		search_data.forEach(function(d) {
			var result = {};
			result.route = '#Form/' + d.doctype + '/' + d.name;
			result.title = d.name;
			result.content = me.get_finds(d.content, keywords);
			var result_html = me.render_result("search", result);
			if(me.search_results[d.doctype]) {
				me.search_results[d.doctype].push(result_html);
			} else {
				me.search_results[d.doctype] = [result_html];
			}
		});
	},

	get_finds: function(searchables, keywords) {
		parts = searchables.split("|||");
		content = "";
		parts.forEach(function(part) {
			if(part.toLowerCase().indexOf(keywords) !== -1) {
				console.log("part", part);
				content += part;
			}
		});
		return content;
	},

	render_result: function(type, result) {
		var result_base_html = '<div class="result '+ type +'-result">' +
			'<a href="{0}" class="module-section-link">{1}</a>' +
			'<p class="small">{2}</p>' +
			'</div>';
		return __(result_base_html, [result.route, result.title, result.content]);
	},

	make_all_results_modules: function() {
		this.result_area.html("");
		this.result_area.empty();
		for (var doctype in this.search_results) {
			if (this.search_results.hasOwnProperty(doctype)) {
				this.results_modules.push(this.make_results_module(
					this.search_results[doctype], doctype));
			}
		}
	},

	make_results_module: function(results, name) {
		var me = this;
		var results_module = $('<div class="row module-section '+name+'-section">'+
			'<div class="col-sm-12 module-section-column">' +
			'<div class="h4 section-head">'+name+'</div>' +
			'<div class="section-body"></div>'+
			'</div></div>');
		var results_col = results_module.find('.module-section-column');
		if(results.length <= this.condensed_length) {
			results.forEach(function(result) {
				results_col.append(result);
			});
		} else {
			var more_div = $('<div class="more-results"></div>');
			for(var i = 0; i < this.condensed_length; i++) {
				results_col.append(results.shift());
			}
			results.forEach(function(result) {
				more_div.append(result);
			});
			results_col.append(more_div);
			results_col.append('<a class="more-' + name + '">More...</a>');
			var more_link = results_col.find('.more-'+name);
			more_link.click(function () {
				more = $(this);
				var more_results = results_col.find('.more-results');
				more_results.slideToggle(500, function () {
					more.text(function () {
						return more_results.is(":visible") ? "Less" : "More...";
					});
				});

			});
		}
		return results_module;
	},

	get_nav_results: function(keywords) {
		var me = this;
		this.nav_results = {};

		var get_nav = function(options, type) {
			if(options.length > 0) {
				me.nav_results[type] = [];
				options.forEach(function(result) {
					me.nav_results[type].push(me.render_nav_result(result));
				});
			}
		}
		console.log("Lists", this.awesome_bar.get_doctypes(keywords));
		get_nav(this.awesome_bar.get_doctypes(keywords), "Lists");
		get_nav(this.awesome_bar.get_reports(keywords), "Reports");
		// get_nav(this.awesome_bar.get_pages(keywords), "Pages");
		get_nav(this.awesome_bar.get_modules(keywords), "Modules");

		this.make_nav_modules();
	},

	render_nav_result: function(result) {
		console.log("nav result", result);
		var result_base_html = '<div> <a class="module-section-link small" href="{0}">{1}</a></div>   ';
		return __(result_base_html, [this.make_path(result.route), result.label]);
	},

	make_path: function(route) {
		var path = "#";
		route.forEach(function(r) {
			path += r + '/';
		});
		return path;
	},

	make_nav_modules: function() {
		for (var nav_type in this.nav_results) {
			if (this.nav_results.hasOwnProperty(nav_type)) {
				this.results_modules.push(this.make_results_module(
					this.nav_results[nav_type], nav_type));
			}
		}
	},

	get_help_results: function(keywords) {
		var me = this;
		this.help_results = [];
		frappe.call({
			method: "frappe.utils.help.get_help",
			args: {
				text: keywords
			},
			callback: function (r) {
				if(r.message) {
					me.format_help_results(r.message, keywords);
					me.make_help_module();
				}
				me.show_results();
				me.bold_keywords();
			}
		});
	},
	
	format_help_results: function(help_data, keywords) {
		var me = this;
		help_data.forEach(function(d) {
			var result = {};
			result.title = d[0];
			result.content = d[1];
			result.route = '#" data-path="' + d[2];
			var result_html = me.render_result("help", result);
			me.help_results.push(result_html);
		});
	},

	make_help_module: function() {
		var me = this;
		this.results_modules.push(this.make_results_module(
			this.help_results, "Help"));
	},

	show_results: function() {
		var me = this;
		if(this.results_modules.length > 0) {
			me.result_area.html("");
			me.result_area.empty();
			this.results_modules.forEach(function(results_module) {
				me.result_area.append(results_module);
			});
		}
	}
});


