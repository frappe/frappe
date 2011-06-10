// URL utilities

wn.urllib = {
	
	// get argument from url
	get_arg: function(name) {
		name = name.replace(/[\[]/,"\\\[").replace(/[\]]/,"\\\]");
		var regexS = "[\\?&]"+name+"=([^&#]*)";
		var regex = new RegExp( regexS );
		var results = regex.exec( window.location.href );
		if( results == null )
			return "";
		else
			return decodeURIComponent(results[1]);		
	},
	
	// returns url dictionary
	get_dict: function() {
		var d = {}
		var t = window.location.href.split('?')[1];
		if(!t) return d;

		if(t.indexOf('#')!=-1) t = t.split('#')[0];
		if(!t) return d;

		t = t.split('&');
		for(var i=0; i<t.length; i++) {
			var a = t[i].split('=');
			d[decodeURIComponent(a[0])] = decodeURIComponent(a[1]);
		}
		return d;		
	},
	
	// returns the base url with http + domain + path (-index.cgi or # or ?)
	get_base_url: function() {
		var url= window.location.href.split('#')[0].split('?')[0].split('index.cgi')[0];
		if(url.substr(url.length-1, 1)=='/') url = url.substr(0, url.length-1)
		return url
	},
	
	// return the relative http url for
	// a file upload / attachment
	// by file id / name
	get_file_url: function(file_id) {
		//var url = wn.urllib.get_base_url();		
		var ac_id = locals['Control Panel']['Control Panel'].account_id;		
		return repl('cgi-bin/getfile.cgi?name=%(fn)s&acx=%(ac)s', {fn:file_id, ac:ac_id})
	}	
}

// bc
get_url_arg = wn.urllib.get_arg;
get_url_dict = wn.urllib.get_dict;