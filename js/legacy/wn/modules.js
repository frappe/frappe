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
		alert('checking in local')
		if(wn.module.in_local(module_name)) {
			if(callback) callback();
			return;
		}
		alert('loading from server')
		wn.module.get_from_server(module_name,callback )
		
	
	},
	get_from_server : function(module_name, callback) {
			
		req = $.ajax({
			url: 'cgi-bin/getjsfile.cgi?module=' + module_name, // TODO use getjsfile.cgi, replace not reqd
			datatype:'text',
			success: [wn.module.accept,callback]
		})
	},
	
	in_local: function(module_name) {
		// check if module in local and recent
		var m = JSON.parse(localStorage.getItem(module_name));
		alert('in_local' + m.timestamp)
		if( m && m.timestamp == wn.timestamps[module_name]) {
			eval(m.code);
			return true;
		}
		return false
	},
	
	accept: function(data, status, jqXHR) {

		data = JSON.parse(data)
		for (var codename in data)
		{
			localStorage.setItem(codename, JSON.stringify({
							
			timestamp	: wn.timestamps[codename],
			code		: data[codename] 	
							
			}))
			eval(data[codename])
		}
	}
}
