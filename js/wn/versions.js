// manage app versioning
// get the last_version_number from the server (loaded)
// and update based on it

wn.versions = {
	is_latest: function() {
		if(window._version_number == (localStorage ? localStorage['_version_number'] : null)) {
			return true;
		}
		return false;
	},
	
	// get the change list of all files
	// from current version and local version
	get_diff: function() {
		if(!localStorage) return;
		wn.xmlhttp.get('index.cgi', function(txt) {
			// add it to localstorage
			r = JSON.parse(txt);
			if(r.exc) { alert(r.exc); }
			wn.versions.set(r.message);
		}, 'cmd=get_diff&version_number=' + localStorage['_version_number'], false);
	},
	
	// set will clear all changes since the last update
	set: function(diff) {
		for(var i=0; i<diff.length; i++) {
			localStorage.removeItem(diff[i]);
		}
		localStorage['_version_number'] = _version_number;
	},
	
	check: function() {
		if(localStorage && !localStorage['_version_number']) {
			// first load
			localStorage['_version_number'] = _version_number;
			return;
		}
		
		if(!wn.versions.is_latest()) wn.versions.get_diff();
	}
}