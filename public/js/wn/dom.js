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
	},
	placeholder: function(dim, letter) {
		function getsinglecol() {
			return Math.min(Math.round(Math.random() * 9) * Math.round(Math.random() * 1) + 3, 9)
		}
		function getcol() {
			return '' + getsinglecol() + getsinglecol() + getsinglecol();
		}
		args = {
			width: Math.round(flt(dim) * 0.7) + 'px',
			height: Math.round(flt(dim) * 0.7) + 'px',
			padding: Math.round(flt(dim) * 0.15) + 'px',
			'font-size': Math.round(flt(dim) * 0.6) + 'px',
			col1: getcol(),
			col2: getcol(),
			letter: letter.substr(0,1).toUpperCase()
		}
		return repl('<div style="\
			height: %(height)s; \
			width: %(width)s; \
			font-size: %(font-size)s; \
			color: #fff; \
			text-align: center; \
			padding: %(padding)s; \
			background: -moz-linear-gradient(top,  #%(col1)s 0%, #%(col2)s 99%); /* FF3.6+ */\
			background: -webkit-gradient(linear, left top, left bottom, color-stop(0%,#%(col1)s), color-stop(99%,#%(col2)s)); /* Chrome,Safari4+ */\
			background: -webkit-linear-gradient(top,  #%(col1)s 0%,#%(col2)s 99%); /* Chrome10+,Safari5.1+ */\
			background: -o-linear-gradient(top,  #%(col1)s 0%,#%(col2)s 99%); /* Opera 11.10+ */\
			background: -ms-linear-gradient(top,  #%(col1)s 0%,#%(col2)s 99%); /* IE10+ */\
			background: linear-gradient(top,  #%(col1)s 0%,#%(col2)s 99%); /* W3C */\
			filter: progid:DXImageTransform.Microsoft.gradient( startColorstr=\'#%(col1)s\', endColorstr=\'#%(col2)s\',GradientType=0 ); /* IE6-9 */\
			">%(letter)s</div>', args);
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