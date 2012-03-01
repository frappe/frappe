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

// find files changed since last version

if(!console) {
	var console = {
		log: function(txt) {
			errprint(txt);
		}
	}
}

wn.check_browser_support = function() {
	var is_supported = function() {
		if($.browser.mozilla && flt($.browser.version)<4) return false;
		if($.browser.msie && flt($.browser.version)<9) return false;
		if($.browser.webkit && flt($.browser.version)<534) return false;
		return true;
	}
	if(!is_supported()) {
		window.location.href= 'unsupported.html';
	}
}

wn.check_browser_support();

wn.versions.check();

/* overload links for ajax pages */
$(document).bind('ready', function() {
	var base = window.location.href.split('#')[0];
	
	// convert hard links to softlinks
	$.each($('a[softlink!="false"]'), function(i, v) {
		
		// if linking on the same site
		if(v.href.substr(0, base.length)==base) {
			var path = (v.href.substr(base.length));
			
			// if hardlink, softlink it
			if(path.substr(0,1)!='#') {				
				v.href = base + '#' + path;
			}
		}
	});

	// go to hash page if exists
	if(!wn.settings.no_history && window.location.hash) {
		wn.page.set(window.location.hash.substr(1));
	}

});
