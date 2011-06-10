// methods on the browser window

wn.window = {
	objpos: function (obj) {
	  if(obj.substr)obj = $i(obj);
	  var p = $(obj).offset();
	  return {x : cint(p.left), y : cint(p.top) }
	},

	screen_size: function() {
	  var d={};
	  d.w = 0; d.h = 0;
	  if( typeof( window.innerWidth ) == 'number' ) {
		//Non-IE
		d.w = window.innerWidth;
		d.h = window.innerHeight;
	  } else if( document.documentElement && ( document.documentElement.clientWidth || document.documentElement.clientHeight ) ) {
		//IE 6+ in 'standards compliant mode'
		d.w = document.documentElement.clientWidth;
		d.h = document.documentElement.clientHeight;
	  } 
	  return d
	},

	// get full page size
	get_page_size: function(){
		if (window.innerHeight && window.scrollMaxY) {// Firefox
			yh = window.innerHeight + window.scrollMaxY;
			xh = window.innerWidth + window.scrollMaxX;
		} else if (document.body.scrollHeight > document.body.offsetHeight){ // all but Explorer Mac
			yh = document.body.scrollHeight;
			xh = document.body.scrollWidth;
		} else { // works in Explorer 6 Strict, Mozilla (not FF) and Safari
			yh = document.body.offsetHeight;
			xh = document.body.offsetWidth;
	  	}
		r = [xh, yh];
		//alert( 'The height is ' + yh + ' and the width is ' + xh );
		return r;
	}

	// get scroll top
	get_scroll_top: function() {
		var st = 0;
		if(document.documentElement && document.documentElement.scrollTop)
			st = document.documentElement.scrollTop;
		else if(document.body && document.body.scrollTop)
			st = document.body.scrollTop;
		return st;
	}

	get_cookie: function(c) {
		var t=""+document.cookie;
		var ind=t.indexOf(c);
		if (ind==-1 || c=="") return ""; 
		var ind1=t.indexOf(';',ind);
		if (ind1==-1) ind1=t.length; 
		return unescape(t.substring(ind+c.length+1,ind1));
	}	
}