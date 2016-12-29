frappe.provide('frappe.ui.search');
frappe.ui.search.setup = function() {
	if(!frappe.ui.search.global_dialog) {
		var d = new frappe.ui.Dialog({title: __('Global Search')});
		$(d.body).html(repl("<div>" +
		"<div class='input-group' style='margin:5px 60px;'>" +
			"<input id='input-global' type='text' class='form-control' placeholder='Search for...' autofocus>" + 
			"<span class='input-group-btn'><button class='btn btn-secondary btn-default' type='button'>" + 
			"<i class='glyphicon glyphicon-search'></i></button></span></div>" +
		"<h4 style='margin-bottom: 25px'></h4>" +
		"<div class='results'></div>" +
		"<hr>" + "<span class='results-footer'></span>" + 
		"</div>", frappe.app));

		var $search_modal = $('#input-global').closest('.modal');
		$search_modal.addClass('search-modal');

		frappe.ui.search.global_dialog = d;
		frappe.ui.search.set_listeners();

	}
}

frappe.ui.search.set_listeners = function() {
	$("#input-global").on("keydown", function (e) {
		if(e.which === 13) {
			frappe.ui.search.get_results($(this).val());
		}
	});
	
	$("#input-global + span").on("click", function () {
		frappe.ui.search.get_results($("#input-global").val());
	});
};

frappe.ui.search.render_result = function(keywords, data) {
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
};

frappe.ui.search.get_results = function(keywords) {
	var results = [];
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
					results.push(frappe.ui.search.render_result(keywords, [fpath, title, e.content]));
				});
			}
			$(".modal-body h4").html("<span></span>'"+keywords+"'");
			frappe.ui.search.show_results(results);
		}
	});

};

frappe.ui.search.show_results = function(results) {
	var base_list_length = 6;
	var more_results_length = 5;
	var $results_list = $('#input-global').closest('.modal').find('.results');
	$results_list.html("");
	$(".results-footer").html("");

	if(results.length === 0) {
		$(".modal-body h4 span").html("No results found for ");
	} else {
		$(".modal-body h4 span").html("Showing results for ");
		if(results.length <= base_list_length) {
			results.forEach(function(e) {
				$results_list.append(e);
			});
		} else {
			for (var i = 0; i < base_list_length; i++){
				$results_list.append(results[i]);
				results.splice(0, 1);
			};
			$(".results-footer").html("<button class='btn btn-default btn-more btn-sm'>More...</button>");
			$(".results-footer .btn-more").on("click", function () {
				for(var i = 0; (i < more_results_length) && (results.length !== 0); i++){
					$results_list.append(results[i]);
					results.splice(0, 1);
				}
				if(results.length === 0) {
					$(".results-footer").html("");
				}
			});
		}
	}
};
