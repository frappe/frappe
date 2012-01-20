// library to mange assets (js, css, models, html) etc in the app.
// will try and get from localStorge if latest are available
// or will load them via xmlhttp
// depends on wn.versions to manage versioning

wn.assets = {
	// keep track of executed assets
	executed_ : {},
	
	// check if the asset exists in
	// localstorage 
	exists: function(src) {
		if('localStorage' in window
			&& localStorage.getItem(src))
			return true
	},
	
	// add the asset to
	// localstorage
	add: function(src, txt) {
		if('localStorage' in window) {
			localStorage.setItem(src, txt);
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
	// xmlhttp
	load: function(src) {
		// this is virtual page load, only get the the source
		// *without* the template
		var t = src;

		wn.xmlhttp.get(t, function(txt) {
			// add it to localstorage
			wn.assets.add(src, txt);			
		}, 'q=' + Math.floor(Math.random()*1000) , false)
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
		cgi: function(txt, src) {
			// dynamic content, will return content as
			// javascript
			wn.dom.eval(txt)
		}
	}
}
