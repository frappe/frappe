// Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
// 
// MIT License (MIT)
// 
// Permission is hereby granted, free of charge, to any person obtaining a 
// copy of this software and associated documentation files (the "Software"), 
// to deal in the Software without restriction, including without limitation 
// the rights to use, copy, modify, merge, publish, distribute, sublicense, 
// and/or sell copies of the Software, and to permit persons to whom the 
// Software is furnished to do so, subject to the following conditions:
// 
// The above copyright notice and this permission notice shall be included in 
// all copies or substantial portions of the Software.
// 
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
// INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
// PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
// HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
// CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
// OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
// 

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
		state = window.location.hash;
		if(state!=src) {
			window.location.hash = state;
		}
		else {
			document.title = title;
		}
	}
}