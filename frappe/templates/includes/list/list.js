frappe.ready(function() {
	let scroll_position = sessionStorage.getItem('scroll_position') || 0;
	window.scrollTo(0, scroll_position);
	$(".website-list .btn-more").on("click", function() {
		const q = frappe.utils.get_query_params();
		if (q.limit) {
			q.limit = parseInt(q.limit);
			q.limit += 20;
		} else q.limit = 40;
		const s = frappe.utils.make_query_string(q);
        sessionStorage.setItem('scroll_position', window.scrollY);
		location.href = `${location.origin}${location.pathname}${s}`;
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
