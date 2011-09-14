wn.xmlhttp = {
	request: function() {
		if ( window.XMLHttpRequest ) // Gecko
			return new XMLHttpRequest() ;
		else if ( window.ActiveXObject ) // IE
			return new ActiveXObject("MsXml2.XmlHttp") ;		
	},
	
	complete: function(req, callback, url) {
		if (req.status==200 || req.status==304) {
			callback(req.responseText);
		} else {
			alert(url +' request error: ' + req.statusText + ' (' + req.status + ')' ) ;
		}		
	},
	
	get: function(url, callback, args, async) {
		// async by default
		if(async === null) async=true;
		var req = wn.xmlhttp.request();
		
		// for async type
		req.onreadystatechange = function() {
			if (req.readyState==4) {
				wn.xmlhttp.complete(req, callback, url)
			}
		}
		// separator can be & or ? 
		// based on if there are already arguments
		var sep = (args.indexOf('?')==-1 ? '?' : '&');
		
		// add arguments to url
		var u = args ? (url + sep + args) : url;

		// call the server
		req.open('GET', u, async);
		req.send(null);
		
		// for sync
		if(!async) {
			wn.xmlhttp.complete(req, callback, url)
		}
	}
}
