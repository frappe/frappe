frappe.provide('frappe.search');

frappe.search.BaseSearch = Class.extend({
	init: function(title) {
		this.setup(title);
		$.extend(this, title);
	},
	setup: function() {
		var me = this;
		var d = new frappe.ui.Dialog({title: __(me.title)});

		$(frappe.render_template("search")).appendTo($(d.body));
		this.search_dialog = d;
		this.search_modal = $(d.$wrapper);
		this.search_modal.addClass('search-modal');

		this.search_modal.find(".search-input").on("keydown", function (e) {
			console.log("enter pressed");
			if(e.which === 13) {
				var keywords = me.search_modal.find(".search-input").val();
				me.get_results(keywords);
			}
		});
		
		this.search_modal.find(".search-button").on("click", function () {
			console.log("search clicked");
			var keywords = me.search_modal.find(".search-input").val();
			me.get_results(keywords);
		});
	},

	render_result: function(keywords, data) {
		var result_base_html = "<div class='search-result'>" +
			"<a href='{0}' class='h4'>{1}</a>" +
			"<p>{2}</p>" +
			"</div>";
		// var regEx = new RegExp("("+ keywords +")", "ig");
		// data.forEach(function(d, i) {
		// 	if(i===1) return;
		// 	data[i] = d.replace(regEx, '<b>$1</b>');
		// });
		return __(result_base_html, data);
	},

	show_results: function(results, keywords) {
		var base_list_length = 8;
		var more_results_length = 7;
		var results_list = this.search_modal.find('.results');
		var more_button = this.search_modal.find('.btn-more');

		results_list.html("");
		more_button.hide();

		if(results.length === 0) {
			this.search_modal.find('.results-status').html("No results found for '" + keywords + "'");
		} else {
			this.search_modal.find('.results-status').html("Showing results for '" + keywords + "'");
			if(results.length <= base_list_length) {
				results.forEach(function(e) {
					results_list.append(e);
				});
			} else {
				for (var i = 0; i < base_list_length; i++){
					results_list.append(results.shift());
				};
				more_button.show();
				more_button.on("click", function () {
					for(var i = 0; (i < more_results_length) && (results.length !== 0); i++){
						results_list.append(results.shift());
					}
					if(results.length === 0) {
						more_button.hide();
					}
				});
			}
		}
	}

});