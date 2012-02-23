// Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
// 
// MIT License (MIT)
// 
// Permission is hereby granted, free of charge, to any person obtaining a 
// copy of this software and associated documentation files (the "Software"), 
// to deal in the Software without restriction, including without limitation 
// the rights to use, copy, modify, merge, publish, distribute, sublicense, 
// and/or sell copies of the Software, and to permit persons to whom the 
// Software is furnished to do so, subject to the following conditions:
// 
// The above copyright notice and this permission notice shall be included in 
// all copies or substantial portions of the Software.
// 
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
// INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
// PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
// HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
// CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
// OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
// 

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
		var sep = ((args && args.indexOf('?'))==-1) ? '?' : '&';
		
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
