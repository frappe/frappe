

frappe.search = {
	setup: function(type) {
		var me = this;
		var d = new frappe.ui.Dialog({title: __(type)});

		$(frappe.render_template("search")).appendTo($(d.body));
		$(d.$wrapper).addClass('search-modal');
		this.$search_modal = d;

		$(".search-modal input").on("keydown", function (e) {
			if(e.which === 13) {
				var keywords = $(".search-modal input").val();
				me.get_results(keywords);
			}
		});
		
		$(".search-modal input + span").on("click", function () {
			var keywords = $(".search-modal input").val();
			me.get_results(keywords);
		});
	},

	render_result: function(keywords, data) {
		var result_base_html = "<div class='search-result'>" +
			"<a href='{0}' class='h4'>{1}</a>" +
			"<p>{2}</p>" +
			"</div>";
		var regEx = new RegExp("("+ keywords +")", "ig");
		data.forEach(function(d, i) {
			if(i===1) return;
			data[i] = d.replace(regEx, '<b>$1</b>');
		});
		return __(result_base_html, data);
	},

	get_results: function(keywords) {
		var results = [];
		var me = this;
		frappe.call({
			method: "frappe.utils.global_search.search",
			args: {
				text: keywords, start: 0, limit: 20
			},
			callback: function(r) {
				if(r.message) {
					r.message.forEach(function(e) {
						var fpath = '#Form/' + e.doctype + '/' + e.name;
						var title = e.doctype + ": " + e.name;
						results.push(me.render_result(keywords, [fpath, title, e.content]));
					});
				}
				$(".search-modal .modal-body h4").html("<span></span>'"+keywords+"'");
				me.show_results(results);
			}
		});

	},

	show_results: function(results) {
		var base_list_length = 8;
		var more_results_length = 7;
		var $results_list = $('.search-modal .results');
		var $more_button = $('.search-modal .btn-more');

		$results_list.html("");
		$more_button.hide();

		if(results.length === 0) {
			$(".search-modal h4 span").html("No results found for ");
		} else {
			$(".search-modal h4 span").html("Showing results for ");
			if(results.length <= base_list_length) {
				results.forEach(function(e) {
					$results_list.append(e);
				});
			} else {
				for (var i = 0; i < base_list_length; i++){
					$results_list.append(results.shift());
				};
				$more_button.show();
				$more_button.on("click", function () {
					for(var i = 0; (i < more_results_length) && (results.length !== 0); i++){
						$results_list.append(results.shift());
					}
					if(results.length === 0) {
						$more_button.hide();
					}
				});
			}
		}
	}

};