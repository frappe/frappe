// library to mange assets (js, css, models, html) etc in the app.
// will try and get from localStorge if latest are available
// or will load them via xmlhttp
// depends on asset_timestamps_ loaded via boot

wn.assets = {
	// keep track of executed assets
	executed_ : {},
	
	// check if the asset exists in
	// localstorage and if the timestamp
	// matches with the loaded timestamp
	exists: function(src) {
		if('localStorage' in window
			&& localStorage.getItem(src)
			&& localStorage.getItem('[ts] '+src) == asset_timestamps_[src])
			return true
	},
	
	// add the asset to
	// localstorage
	add: function(src, txt) {
		if('localStorage' in window) {
			localStorage.setItem(src, txt);
			localStorage.setItem('[ts] ' + src, asset_timestamps_[src]);
		}
	},
	
	get: function(src) {
		return localStorage.getItem(src);
	},
	
	extn: function(src) {
		return src.split('.').slice(-1)[0];
	},

	html_src: function(src) {
		if(src.indexOf('/')!=-1) {
			var t = src.split('/').slice(0,-1);
			t.push('src');
			t = t.join('/') +'/' + a.split('/').slice(-1)[0];
		} else {
			var t = 'src/' + src;
		}
		return t;
	},
	
	// load an asset via
	// xmlhttp
	load: function(src) {
		var t = wn.assets.extn(src)=='html' ? wn.assets.html_src(src) : src;

		wn.xmlhttp.get(t, function(txt) {
			// add it to localstorage
			wn.assets.add(src, txt);			
		}, 'q=' & Math.floor(Math.random()*1000) , false)
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
			var se = document.createElement('style');
			se.type = "text/css";
			if (se.styleSheet) {
				se.styleSheet.cssText = txt;
			} else {
				se.appendChild(document.createTextNode(txt));
			}
			document.getElementsByTagName('head')[0].appendChild(se);			
		},
		html: function(txt, src) {
			// make the html content page
			var page = wn.dom.add($('.outer .inner').get(0), 'div', 'content', null, txt);
			page.setAttribute("_src", src);
		}
	}
}
