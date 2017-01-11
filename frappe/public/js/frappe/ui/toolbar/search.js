frappe.provide('frappe.search');

frappe.search.Search = Class.extend({
	init: function() {
        this.setup();
	},

	setup: function() {
		var me = this;
		var d = new frappe.ui.Dialog();

		$(frappe.render_template("search")).appendTo($(d.body));
		$(d.header).html($(frappe.render_template("search_header")));

		this.search_dialog = d;
		this.search_modal = $(d.$wrapper);
		this.search_modal.addClass('search-modal');
		this.result_area = this.search_modal.find(".result-area");

		this.base_list_length = 8;
		this.more_results_length = 7;
		this.condensed_length = 2;

		this.search_modal.find(".search-input").on("input", function (e) {
			var keywords = me.search_modal.find(".search-input").val();
			if(keywords !== ""){
				// setTimeout(function() { me.setup_search(keywords) }, 20);
				me.setup_search(keywords);
			}
		});
	},

	on_dialog_show: function(keywords) {
		var me = this;
		this.search_modal.find(".search-input").val(keywords);
		this.setup_search(keywords);
		// timeout hack: focus and select input
		setTimeout(function() { me.search_modal.find(".search-input").select(); }, 500);
	},

	setup_search: function(keywords) {
		this.search_modal.find(".search-list").addClass("hide");
		this.search_modal.find(".report-list").addClass("hide");
		this.search_modal.find(".help-list").addClass("hide");
		// Set the results-area to no results found or something
		this.get_results(keywords);
	},

	get_results: function(keywords) {
		this.get_search_results(keywords);
		//this.get_reports(keywords);
		this.get_help_results(keywords);
	},

	get_search_results: function(keywords) {
		var me = this;
		this.search_results = {};
		this.results_divs = {};
		frappe.call({
			method: "frappe.utils.global_search.search",
			args: {
				text: keywords, start: 0, limit: 20
			},
			callback: function(r) {
				if(r.message) {
					me.format_search_results(r.message, keywords);
					me.make_all_results_divs();
					me.show_search_list();
					me.bind_search_results();
				}
			}
		});
	},

	format_search_results: function(search_data, keywords) {
		var me = this;
		search_data.forEach(function(d) {
			var fpath = '#Form/' + d.doctype + '/' + d.name;
			var title = d.name;
			var result_html = me.render_result("search", keywords, [fpath, title, d.content]);
			if(me.search_results[d.doctype]) {
				me.search_results[d.doctype].push(result_html);
			} else {
				me.search_results[d.doctype] = [result_html];
			}
		});
	},

	make_all_results_divs: function() {
		for (var doctype in this.search_results) {
			if (this.search_results.hasOwnProperty(doctype)) {
				this.results_divs[doctype] = this.make_results_div(
					this.search_results[doctype], doctype);
			}
		}
	},

	make_results_div: function(results, name) {
		var me = this;
		var results_div = $('<div class="results-div '+name+'-results"></div>');
		if(results.length <= this.base_list_length) {
			results.forEach(function(result_html) {
				results_div.append(result_html);
			});
			results = [];
		} else {
			// Append a more button for additional results
			for(var i = 0; i < this.base_list_length; i++) {
				results_div.append(results.shift());
			}
			results_div.append('<hr><button class="btn btn-default more-' + name +
				' btn-more btn-sm">More...</button>');
			var more_button = results_div.find('.more-'+name);
			console.log("more button", more_button);
			more_button.on("click", function () {
				console.log("more button clicked!");
				for(var i = 0; (i < me.more_results_length) && (results.length !== 0); i++){
					results_div.find('.search-result').last().after(results.shift());
				}
				if(results.length === 0) { more_button.hide(); }
			});
		}
		return results_div;
	},

	show_search_list: function() {
		var me = this;
		var search_list = this.search_modal.find(".search-list");
		search_list.html('').append('<li class="divider"></li>' + 
			'<li class="h6">Global Search</li>').removeClass("hide");
		Object.keys(this.search_results).forEach(function(doctype) {
			search_list.append(me.render_list_item(doctype));
		});
	},

	bind_search_results: function() {
		var me = this;
		this.search_modal.find(".search-list .list-link").on('click', function(){
			me.search_modal.find(".list-link a").removeClass("disabled");
			$(this).find('a').addClass("disabled");
			var doctype = $(this).attr('data-category');
			me.result_area.html(me.results_divs[doctype]);
			return false;
		});
	},

	render_result: function(type, keywords, data) {
		var result_base_html = '<div class="'+ type +'-result">' +
			'<a href="{0}" class="h4">{1}</a>' +
			'<p>{2}</p>' +
			'</div>';
		// no bold if it's a link, then can make everywhere
		var regEx = new RegExp("("+ keywords +")", "ig");
		data[2] = data[2].replace(regEx, '<b>$1</b>');
		return __(result_base_html, data);
	},

	render_list_item: function(doctype) {
		var list_item_base_html = '<li class="list-link"' + 
			'data-category="{0}"><a href="#">{0}</a></li>';
		return __(list_item_base_html, [doctype]);
	},

	get_help_results: function(keywords) {
		var me = this;
		frappe.call({
			method: "frappe.utils.help.get_help",
			args: {
				text: keywords
			},
			callback: function (r) {
				if(r.message) {
					me.format_help_results(r.message, keywords);
					me.make_help();
				}
				me.show_condensed_results();
			}
		});
	},

	format_help_results: function(help_data, keywords) {
		var me = this;
		this.search_results["Help"] = [];
		help_data.forEach(function(d) {
			var title = d[0];
			var intro = d[1];
			var fpath = '#" data-path="' + d[2];
			var result_html = me.render_result("help", keywords, [fpath, title, intro]);
			me.search_results["Help"].push(result_html)
		});
	},

	make_help: function() {
		var me = this;
		this.results_divs["Help"] = this.make_results_div(
			this.search_results["Help"], "Help");
		this.search_modal.find(".help-list").removeClass("hide");
		
		this.search_modal.find(".help-list .list-link").on('click', function() {
			me.search_modal.find(".list-link a").removeClass("disabled");
			$(this).find('a').addClass("disabled");
			
			me.result_area.html(me.results_divs["Help"]);
			me.bind_help_results();
			return false;
		});
	},

	bind_help_results: function() {
		var me = this;
		console.log("path");
		me.search_modal.find(".help-result .h4").on("click", function() {
			var path = $(this).attr("data-path");
			console.log(path);
			if(path) {
				me.show_help_article(path);
			}
			return false;
		});
	},

	show_help_article: function(path) {
		var me = this;
		frappe.call({
			method: "frappe.utils.help.get_help_content",
			args: {
				path: path
			},
			callback: function (r) {
				console.log("inside search callback:", r.message);
				if(r.message && r.message.title) {
					me.result_area.html('<span class="h4">' + 
						r.message.title + '</span>' + r.message.content);
				}
			}
		});
	},

	show_condensed_results: function() {
		this.result_area.html('');
		var me = this;

		for (var doctype in me.search_results) {
			if (this.search_results.hasOwnProperty(doctype)) {
				var results = this.search_results[doctype].slice(0,this.condensed_length);
				var more_link = false;
				if(this.search_results[doctype].length > this.condensed_length){
					more_link = true;
				} 
				this.result_area.append(this.make_condensed_div(results, doctype, more_link));
			}
		}
	},

	make_condensed_div: function(results, name, more_link) {
		var me = this;
		var results_div = $('<div class="results-div '+name+'-results"><h4>'+name+'</h4></div>');
		results.forEach(function(result_html) {
			results_div.append(result_html);
		});
		if(more_link) {
			results_div.append('<a class="more-' + name + '">More...</a><hr>');
			var more_link = results_div.find('.more-'+name);
			more_link.on("click", function () {
				me.search_modal.find('*[data-category="'+ name +'"]').trigger("click");
			});
		} else {
			results_div.append('<hr>');
		}
		
		return results_div;
	},


});


