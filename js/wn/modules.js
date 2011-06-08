/*

Modules

wn.module.$import('forms') will load wn.forms, if loaded will return nothing

timestamps will be loaded with the window in wn.timestamps

*/
wn.module = {
	// 
	$import: function(module_name, callback) {
		if(wn[module_name]) return;
		wn.module.load(module_name, callback);
	},
	
	load: function(module_name, callback) {
		// if loaded in local and recent
		if(wn.module.in_local(module_name)) {
			if(callback) callback();
			return;
		}
			
		var req = $.ajax({
			url: 'js/' + module_name.replace(/./g, "/"),
			datatype:'script',
			success: wn.module.accept
		});
		req.module_name = module_name;
		req.callback = callback;
	},
	
	in_local: function(module_name) {
		var m = localStorage.getItem(module_name);
		if(m && m.timestamp == wn.timestamps[module_name]) {
			eval(m.code);
			return true;
		}
	},
	
	accept: function(data, status, req) {
		var m = {
			timestamp: wn.timestamps[req.module_name],
			code: data,
		}
		localStorage.setItem(req.module_name, m);
		if(req.callback) req.callback();
	}
}
