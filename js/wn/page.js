wn.page = {
	set: function(src) {
		var new_selection = $('.inner div.content[_src="'+ src +'"]');
		if(!new_selection.length) {
			// get from server / localstorage
			wn.assets.execute(src);
			new_selection = $('.inner div.content[_src="'+ src +'"]');
		}

		// hide current
		$('.inner .current_page').removeClass('current_page');
		
		// show new
		new_selection.addClass('current_page');
		
		// get title (the first h1, h2, h3)
		var title = $('nav ul li a[href*="' + src + '"]').attr('title') || 'No Title'
		
		// replace state (to url)
		state = History.getState();
		if(state.hash!=src) {
			History.replaceState(null, title, src);	
		}
		else {
			document.title = title;
		}
	}
}