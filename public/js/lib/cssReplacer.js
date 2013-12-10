var refreshId = setInterval(function() {
	if (userLanguage == "ar") {
		var elements = $('link[href$="css"]');
		$('link[href$="css"]').each(function() {
			var href = $(this).attr('href');
			var pos = href.lastIndexOf('.');
			var underscore = href.lastIndexOf('_');
			if (pos != -1) {
				if (href.substring(pos - 3, pos) != "_" + userLanguage && underscore != (pos - 3)) {
					href = href.substring(0, pos) + "_" + userLanguage + href.substring(pos);
					$(this).attr('href', href);				
				}
			}
		});
	}
}, 100);