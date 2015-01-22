// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// library to mange assets (js, css, models, html) etc in the app.
// will try and get from localStorge if latest are available
// depends on frappe.versions to manage versioning

frappe.require = function(items) {
	if(typeof items === "string") {
		items = [items];
	}
	var l = items.length;

	for(var i=0; i< l; i++) {
		var src = items[i];
		frappe.assets.execute(src);
	}
};

frappe.assets = {
	// keep track of executed assets
	executed_ : {},
	
	check: function() {
		// if version is different then clear localstorage
		if(window._version_number != localStorage.getItem("_version_number")) {
			localStorage.clear();
			console.log("Cleared App Cache.");
		}
		
		if(localStorage._last_load) {
			var not_updated_since = new Date() - new Date(localStorage._last_load);
			if(not_updated_since < 10000 || not_updated_since > 86400000) {
				localStorage.clear();
				console.log("Cleared localstorage");
			}
		} else {
			localStorage.clear();
			console.log("Cleared localstorage");
		}
		
		frappe.assets.init_local_storage();
	},
	
	init_local_storage: function() {
		localStorage._last_load = new Date();
		localStorage._version_number = window._version_number;
		if(frappe.boot) localStorage.metadata_version = frappe.boot.metadata_version;
	},
	
	// check if the asset exists in
	// localstorage 
	exists: function(src) {
		if('localStorage' in window
			&& localStorage.getItem(src) && (frappe.boot ? !frappe.boot.developer_mode : true))
			return true;
	},
	
	// add the asset to
	// localstorage
	add: function(src, txt) {
		if('localStorage' in window) {
			try {
				localStorage.setItem(src, txt);
			} catch(e) {
				// if quota is exceeded, clear local storage and set item
				localStorage.clear();
				console.log("Local Storage cleared");
				
				localStorage.setItem(src, txt);
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
		frappe.set_loading();

		frappe.call({
			method:"frappe.client.get_js",
			args: {
				"src": src
			},
			callback: function(r) {
				frappe.assets.add(src, r.message);
			},
			async: false
		})
		
		frappe.done_loading();
	},
	
	// pass on to the handler to set
	execute: function(src) {
		if(!frappe.assets.exists(src)) {
			frappe.assets.load(src);
		}
		var type = frappe.assets.extn(src);
		if(frappe.assets.handler[type]) {
			frappe.assets.handler[type](frappe.assets.get(src), src);
			frappe.assets.executed_[src] = 1;
		}
	},
	
	// handle types of assets
	// and launch them in the
	// app
	handler: {
		js: function(txt, src) {
			frappe.dom.eval(txt);
		},
		css: function(txt, src) {
			frappe.dom.set_style(txt);
		}
	}
};