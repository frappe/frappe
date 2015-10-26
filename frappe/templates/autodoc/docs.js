$(function() {
	if(hljs) {
		$('pre code').each(function(i, block) {
			hljs.highlightBlock(block);
		});
	}

	$(".toggle-sidebar").on("click", function() {
		$(".offcanvas").addClass("active-right");
		return false;
	});

	// collapse offcanvas sidebars!
	$(".offcanvas .sidebar").on("click", "a", function() {
		$(".offcanvas").removeClass("active-left active-right");
	});

	$(".offcanvas-main-section-overlay").on("click", function() {
		$(".offcanvas").removeClass("active-left active-right");
		return false;
	});

});
