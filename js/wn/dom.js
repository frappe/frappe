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

// add a new dom element
wn.provide('wn.dom');

wn.dom.by_id = function(id) {
	return document.getElementById(id);
}

wn.dom.eval = function(txt) {
	if(!txt) return;
	var el = document.createElement('script');
	el.appendChild(document.createTextNode(txt));
	// execute the script globally
	document.getElementsByTagName('head')[0].appendChild(el);
}

wn.dom.set_style = function(txt) {
	if(!txt) return;
	var se = document.createElement('style');
	se.type = "text/css";
	if (se.styleSheet) {
		se.styleSheet.cssText = txt;
	} else {
		se.appendChild(document.createTextNode(txt));
	}
	document.getElementsByTagName('head')[0].appendChild(se);	
}

wn.dom.add = function(parent, newtag, className, cs, innerHTML, onclick) {
	if(parent && parent.substr)parent = wn.dom.by_id(parent);
	var c = document.createElement(newtag);
	if(parent)
		parent.appendChild(c);
		
	// if image, 3rd parameter is source
	if(className) {
		if(newtag.toLowerCase()=='img')
			c.src = className
		else
			c.className = className;		
	}
	if(cs) wn.dom.css(c,cs);
	if(innerHTML) c.innerHTML = innerHTML;
	if(onclick) c.onclick = onclick;
	return c;
}

// add css to element
wn.dom.css= function(ele, s) { 
	if(ele && s) { 
		for(var i in s) ele.style[i]=s[i]; 
	}; 
	return ele;
}

wn.get_cookie = function(c) {
	var t=""+document.cookie;
	var ind=t.indexOf(c);
	if (ind==-1 || c=="") return ""; 
	var ind1=t.indexOf(';',ind);
	if (ind1==-1) ind1=t.length; 
	return unescape(t.substring(ind+c.length+1,ind1));
}

wn.dom.set_box_shadow = function(ele, spread) {
	$(ele).css('-moz-box-shadow', '0px 0px '+ spread +'px rgba(0,0,0,0.3);')
	$(ele).css('-webkit-box-shadow', '0px 0px '+ spread +'px rgba(0,0,0,0.3);')
	$(ele).css('-box-shadow', '0px 0px '+ spread +'px rgba(0,0,0,0.3);')
	
};

// add <option> list to <select>
(function($) {
	$.fn.add_options = function(options_list) {
		// create options
		for(var i=0; i<options_list.length; i++) {
			var v = options_list[i];
			value = v.value || v;
			label = v.label || v;
			$('<option>').html(label).attr('value', value).appendTo(this);
		}
		// select the first option
		$(this).val(options_list[0].value || options_list[0]);
	}
	$.fn.set_working = function() {
		var ele = this.get(0);
		if(ele.loading_img) { 
			$di(ele.loading_img) 
		} else {
			ele.disabled = 1;
			ele.loading_img = $('<img src="lib/images/ui/button-load.gif" \
				style="margin-left: 4px; margin-bottom: -2px; display: inline;" />')
				.insertAfter(ele);			
		}		
	}
	$.fn.done_working = function() {
		var ele = this.get(0);
		ele.disabled = 0;
		if(ele.loading_img) { $(ele.loading_img).toggle(false); };
	}
})(jQuery);
