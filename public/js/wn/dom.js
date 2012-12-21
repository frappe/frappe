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

wn.dom = {
	id_count: 0,
	freeze_count: 0,
	by_id: function(id) {
		return document.getElementById(id);
	},
	set_unique_id: function(ele) {
		var id = 'unique-' + wn.dom.id_count;
		if(ele)
			ele.setAttribute('id', id);
		wn.dom.id_count++;
		return id;
	},
	eval: function(txt) {
		if(!txt) return;
		var el = document.createElement('script');
		el.appendChild(document.createTextNode(txt));
		// execute the script globally
		document.getElementsByTagName('head')[0].appendChild(el);
	},
	set_style: function(txt) {
		if(!txt) return;
		var se = document.createElement('style');
		se.type = "text/css";
		if (se.styleSheet) {
			se.styleSheet.cssText = txt;
		} else {
			se.appendChild(document.createTextNode(txt));
		}
		document.getElementsByTagName('head')[0].appendChild(se);	
	},
	add: function(parent, newtag, className, cs, innerHTML, onclick) {
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
	},
	css: function(ele, s) { 
		if(ele && s) { 
			for(var i in s) ele.style[i]=s[i]; 
		}; 
		return ele;
	},
	freeze: function() {
		// blur
		if(!$('#freeze').length) {
			$("<div id='freeze'>").appendTo("#body_div").css('opacity', 0.6);
		}
		$('#freeze').toggle(true);
		wn.dom.freeze_count++;
	},
	unfreeze: function() {
		if(!wn.dom.freeze_count)return; // anything open?
		wn.dom.freeze_count--;
		if(!wn.dom.freeze_count) {
			$('#freeze').toggle(false);
		}		
	}
}

var pending_req = 0
wn.set_loading = function() {
	pending_req++;
	$('#spinner').css('visibility', 'visible');
	$('body').css('cursor', 'progress');
}

wn.done_loading = function() {
	pending_req--;
	if(!pending_req){
		$('body').css('cursor', 'default');
		$('#spinner').css('visibility', 'hidden');
	}
}

var get_hex = function(i) {
	i = Math.round(i);
	if(i>255) return 'ff';
	if(i<0) return '00';
	i =i .toString(16);
    if(i.length==1) i = '0'+i;
	return i;
}

wn.get_shade = function(color, factor) {
	if(color.substr(0,3)=="rgb") {
		var rgb = function(r,g,b) {
			return get_hex(r) + get_hex(g) + get_hex(b);
		}
		color = eval(color);
	}
	if(color.substr(0,1)=="#") {
		var color = color.substr(1);
	}

	var get_int = function(hex) {
		return parseInt(hex,16); 
	}
	return get_hex(get_int(color.substr(0,2)) + factor)
		+ get_hex(get_int(color.substr(2,2)) + factor)
		+ get_hex(get_int(color.substr(4,2)) + factor)
}

wn.get_gradient_css = function(col, diff) {
	if(!diff) diff = 10
	var col1 = wn.get_shade(col, diff);
	var col2 = wn.get_shade(col, -diff);
	return "\nbackground-color: " + col + " !important;"
		+"\nbackground: -moz-linear-gradient(top,  #"+col1+" 0%, #"+col2+" 99%) !important;"
		+"\nbackground:-webkit-gradient(linear, left top, left bottom, color-stop(0%,#"+col1+"), color-stop(99%,#"+col2+")) !important;"
		+"\nbackground:-webkit-linear-gradient(top,  #"+col1+" 0%,#"+col2+" 99%) !important;"
		+"\nbackground:-o-linear-gradient(top,  #"+col1+" 0%,#"+col2+" 99%) !important;"
		+"\nbackground:-ms-linear-gradient(top,  #"+col1+" 0%,#"+col2+" 99%) !important;"
		+"\nbackground:-o-linear-gradient(top,  #"+col1+" 0%,#"+col2+" 99%) !important;"
		+"\nbackground:linear-gradient(top,  #"+col1+" 0%,#%"+col2+" 99%) !important;"
		+"\nfilter:progid:DXImageTransform.Microsoft.gradient( startColorstr='#"+col1+"', endColorstr='#"+col1+"',GradientType=0 ) !important;"
}

$.fn.gradientify = function(col) {
	if(!col) col = this.css("background-color");
	var col1 = wn.get_shade(col, 1.05);
	var col2 = wn.get_shade(col, 0.95);
	
	this.css({
		"background": "-moz-linear-gradient(top,  #"+col1+" 0%, #"+col2+" 99%)"
	});
	this.css({
		"background": "-webkit-gradient(linear, left top, left bottom, color-stop(0%,#"+col1+"), color-stop(99%,#"+col2+"))"
	});
	this.css({
		"background": "-webkit-linear-gradient(top,  #"+col1+" 0%,#"+col2+" 99%)"
	});
	this.css({
		"background": "-o-linear-gradient(top,  #"+col1+" 0%,#"+col2+" 99%);"
	});
	this.css({
		"background": "-ms-linear-gradient(top,  #"+col1+" 0%,#"+col2+" 99%);"
	});
	this.css({
		"background": "-o-linear-gradient(top,  #"+col1+" 0%,#"+col2+" 99%);"
	});
	this.css({
		"background": "linear-gradient(top,  #"+col1+" 0%,#%"+col2+" 99%);"
	});
	this.css({
		"filter": "progid:DXImageTransform.Microsoft.gradient( startColorstr='#"+col1+"', endColorstr='#"+col1+"',GradientType=0 )"
	});
}

wn.get_cookie = function(c) {
	var clist = (document.cookie+'').split(';');
	var cookies = {};
	for(var i=0;i<clist.length;i++) {
		var tmp = clist[i].split('=');
		cookies[strip(tmp[0])] = strip(tmp[1]);
	}
	return cookies[c];
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
		this.selectedIndex = 0;
		return $(this);
	}
	$.fn.set_working = function() {
		var ele = this.get(0);
		$(ele).attr('disabled', 'disabled');
		if(ele.loading_img) { 
			$(ele.loading_img).toggle(true);
		} else {
			ele.loading_img = $('<img src="lib/images/ui/button-load.gif" \
				style="margin-left: 4px; margin-bottom: -2px; display: inline;" />')
				.insertAfter(ele);
		}		
	}
	$.fn.done_working = function() {
		var ele = this.get(0);
		$(ele).attr('disabled', null);
		if(ele.loading_img) { 
			$(ele.loading_img).toggle(false); 
		};
	}
})(jQuery);