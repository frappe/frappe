// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
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
			frappe.assets.clear_local_storage();
			console.log("Cleared App Cache.");
		}

		if(localStorage._last_load) {
			var not_updated_since = new Date() - new Date(localStorage._last_load);
			if(not_updated_since < 10000 || not_updated_since > 86400000) {
				frappe.assets.clear_local_storage();
			}
		} else {
			frappe.assets.clear_local_storage();
		}

		frappe.assets.init_local_storage();
	},

	init_local_storage: function() {
		localStorage._last_load = new Date();
		localStorage._version_number = window._version_number;
		if(frappe.boot) localStorage.metadata_version = frappe.boot.metadata_version;
	},

	clear_local_storage: function() {
		$.each(["_last_load", "_version_number", "metadata_version", "page_info",
			"last_visited"], function(i, key) {
			localStorage.removeItem(key);
		});

		// clear assets
		for(key in localStorage) {
			if(key.indexOf("desk_assets:")===0 || key.indexOf("_page:")===0
				|| key.indexOf("_doctype:")===0 || key.indexOf("preferred_breadcrumbs:")===0) {
				localStorage.removeItem(key);
			}
		}
		console.log("localStorage cleared");
	},

	add: function(src, txt) {
		if('localStorage' in window) {
			try {
				frappe.assets.set(src, txt);
			} catch(e) {
				// if quota is exceeded, clear local storage and set item
				frappe.assets.clear_local_storage();
				frappe.assets.set(src, txt);
			}
		}
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

	// load an asset via
	load: function(src) {
		// this is virtual page load, only get the the source
		// *without* the template

		frappe.call({
			type: "GET",
			method:"frappe.client.get_js",
			args: {
				"src": src
			},
			callback: function(r) {
				frappe.assets.add(src, r.message);
			},
			async: false,
			freeze: true,
		})
	},

	// check if the asset exists in
	// localstorage
	exists: function(src) {
		if(frappe.assets.get(src)
				&& (frappe.boot ? !frappe.boot.developer_mode : true))
			return true;
	},

	get: function(src) {
		return localStorage.getItem("desk_assets:" + src);
	},

	set: function(src, txt) {
		localStorage.setItem("desk_assets:" + src, txt);
	},

	extn: function(src) {
		if(src.indexOf('?')!=-1) {
			src = src.split('?').slice(-1)[0];
		}
		return src.split('.').slice(-1)[0];
	},

	handler: {
		js: function(txt, src) {
			frappe.dom.eval(txt);
		},
		css: function(txt, src) {
			frappe.dom.set_style(txt);
		}
	},
};
