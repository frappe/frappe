frappe.ready(function() {
	var next_start = {{ next_start }};
	var result_wrapper = $(".website-list .result");

	$(".website-list .btn-more").on("click", function() {
		var btn = $(this);

		var data = $.extend(get_query_params(), {
			doctype: "{{ doctype }}",
			txt: "{{ txt or '' }}",
			limit_start: next_start,
			pathname: location.pathname,
			is_web_form: "{{ is_web_form }}"
		});

		btn.prop("disabled", true);
		return $.ajax({
			url:"/api/method/frappe.www.list.get",
			data: data,
			statusCode: {
				200: function(data) {
					var data = data.message;
					next_start = data.next_start;
					$.each(data.result, function(i, d) {
						$(d).appendTo(result_wrapper);
					});
					toggle_more(data.show_more);
				}
			}
		}).always(function() {
			btn.prop("disabled", false);
		});
	});

	var toggle_more = function(show) {
		if (!show) {
			$(".website-list .more-block").addClass("hide");
		}
	};
	
	if($('.navbar-header .navbar-toggle:visible').length === 1)
	{
		$('.page-head h1').addClass('list-head').click(function(){
			window.history.back();
	 	});
	}
});
