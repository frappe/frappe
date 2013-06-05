// Copyright 2013 Web Notes Technologies Pvt Ltd
// License: MIT. See license.txt

// library to mange assets (js, css, models, html) etc in the app.
// will try and get from localStorge if latest are available
// depends on wn.versions to manage versioning

wn.require = function(items) {
	if(typeof items === "string") {
		items = [items];
	}
	var l = items.length;

	for(var i=0; i< l; i++) {
		var src = items[i];
		//if(!(src in wn.assets.executed_)) {
			// check if available in localstorage
		wn.assets.execute(src);
		//}
	}
}

wn.assets = {
	// keep track of executed assets
	executed_ : {},
	
	check: function() {
		// if version is different then clear localstorage
		if(window._version_number != localStorage.getItem("_version_number")) {
			localStorage.clear();
			localStorage.setItem("_version_number", window._version_number)
			console.log("Cleared App Cache.");
		}
	},
	
	// check if the asset exists in
	// localstorage 
	exists: function(src) {
		if('localStorage' in window
			&& localStorage.getItem(src) && (wn.boot ? !wn.boot.developer_mode : true))
			return true
	},
	
	// add the asset to
	// localstorage
	add: function(src, txt) {
		if('localStorage' in window) {
			try {
				localStorage.setItem(src, txt);
			} catch(e) {
				console.log("Local Storage quota exceeded?")
			}
		}
	},
	
	get: function(src) {
		return localStorage.getItem(src);
	},
	
	extn: function(src) {
		if(src.indexOf('?')!=-1) {
			src = src.split('?').slice(-1)[0];
		}
		return src.split('.').slice(-1)[0];
	},
	
	// load an asset via
	load: function(src) {
		// this is virtual page load, only get the the source
		// *without* the template
		var t = src;
		
		wn.set_loading();

		$.ajax({
			url: t,
			data: {
				q: Math.floor(Math.random()*1000)
			},
			dataType: 'text',
			success: function(txt) {
				// add it to localstorage
				wn.assets.add(src, txt);				
			},
			async: false
		});
		
		wn.done_loading();
	},
	
	// pass on to the handler to set
	execute: function(src) {
		if(!wn.assets.exists(src)) {
			wn.assets.load(src);
		}
		var type = wn.assets.extn(src);
		if(wn.assets.handler[type]) {
			wn.assets.handler[type](wn.assets.get(src), src);
			wn.assets.executed_[src] = 1;
		}
	},
	
	// handle types of assets
	// and launch them in the
	// app
	handler: {
		js: function(txt, src) {
			wn.dom.eval(txt);
		},
		css: function(txt, src) {
			wn.dom.set_style(txt);
		}
	}
}

wn.markdown = function(txt) {
	if(!wn.md2html) {
		wn.require('lib/js/lib/showdown.js');
		wn.md2html = new Showdown.converter();
	}
	
	while(txt.substr(0,1)==="\n") {
		txt = txt.substr(1);
	}
	
	// remove leading tab (if they exist in the first line)
	var whitespace_len = 0,
		first_line = txt.split("\n")[0];

	while([" ", "\n", "\t"].indexOf(first_line.substr(0,1))!== -1) {
		whitespace_len++;
		first_line = first_line.substr(1);
	}
		
	if(whitespace_len && whitespace_len != first_line.length) {
		var txt1 = [];
		$.each(txt.split("\n"), function(i, t) {
			txt1.push(t.substr(whitespace_len));
		})
		txt = txt1.join("\n");
	}
	
	return wn.md2html.makeHtml(txt);
}
