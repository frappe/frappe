// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt 

// short hand functions for setting up
// rich text editor tinymce
wn.tinymce = {
	add_simple: function(ele, height) {
		if(ele.myid) {
			tinyMCE.execCommand( 'mceAddControl', true, ele.myid);
			return;
		}
		
		// no create
		ele.myid = wn.dom.set_unique_id(ele);
		$(ele).tinymce({
			// Location of TinyMCE script
			script_url : 'js/lib/tiny_mce_3.5.7/tiny_mce.js',

			height: height ? height : '200px',
			
			// General options
		    theme : "advanced",
		    theme_advanced_buttons1 : "bold,italic,underline,separator,strikethrough,justifyleft,justifycenter,justifyright,justifyfull,bullist,numlist,outdent,indent,link,unlink,forecolor,backcolor,code,",
		    theme_advanced_buttons2 : "",
		    theme_advanced_buttons3 : "",
		    theme_advanced_toolbar_location : "top",
		    theme_advanced_toolbar_align : "left",
			theme_advanced_path : false,
			theme_advanced_resizing : false
		});		
	},
	
	remove: function(ele) {
		tinyMCE.execCommand( 'mceRemoveControl', true, ele.myid);
	},
	
	get_value: function(ele) {
		return tinymce.get(ele.myid).getContent();
	}
}

wn.ele = {
	link: function(args) {
		var span = $a(args.parent, 'span', 'link_type', args.style);
		span.loading_img = $a(args.parent,'img','',{margin:'0px 4px -2px 4px', display:'none'});
		span.loading_img.src= 'assets/webnotes/images/ui/button-load.gif';

		span.innerHTML = args.label;
		span.user_onclick = args.onclick;
		span.onclick = function() { if(!this.disabled) this.user_onclick(this); }

		// working
		span.set_working = function() {
			this.disabled = 1;
			$di(this.loading_img);
		}
		span.done_working = function() {
			this.disabled = 0;
			$dh(this.loading_img);
		}

		return span;
	}
}

function $ln(parent, label, onclick, style) { 
	return wn.ele.link({parent:parent, label:label, onclick:onclick, style:style})
}

function $btn(parent, label, onclick, style, css_class, is_ajax) {
	if(css_class==='green') css_class='btn-info';
	return new wn.ui.Button(
		{parent:parent, label:label, onclick:onclick, style:style, is_ajax: is_ajax, css_class: css_class}
	).btn;
}

// item (for tabs and triggers)
// ====================================

$item_normal = function(ele) { 
	$y(ele, {padding:'6px 8px',cursor:'pointer',marginRight:'8px', whiteSpace:'nowrap',overflow:'hidden',borderBottom:'1px solid #DDD'});
	$bg(ele,'#FFF'); $fg(ele,'#000');
}
$item_active = function(ele) {
	$bg(ele,'#FE8'); $fg(ele,'#000');
}
$item_selected = function(ele) {
	$bg(ele,'#777'); $fg(ele,'#FFF');
}
$item_pressed = function(ele) {
	$bg(ele,'#F90'); $fg(ele,'#FFF');
};

// set out of 100
function set_opacity(ele, ieop) {
	var op = ieop / 100;
	if (ele.filters) { // internet explorer
		try { 
			ele.filters.item("DXImageTransform.Microsoft.Alpha").opacity = ieop;
		} catch (e) { 
			ele.style.filter = 'progid:DXImageTransform.Microsoft.Alpha(opacity='+ieop+')';
		}
	} else  { // other browsers 
		ele.style.opacity = op; 
	}
}

// border radius
// ====================================

$br = function(ele, r, corners) {
	if(corners) { 
		var cl = ['top-left', 'top-right', 'bottom-right' , 'bottom-left'];
		for(var i=0; i<4; i++) {
			if(corners[i]) {
				$(ele).css('-moz-border-radius-'+cl[i].replace('-',''),r).css('-webkit-'+cl[i]+'-border-radius',r);
			}
		}
	} else {
		$(ele).css('-moz-border-radius',r).css('-webkit-border-radius',r).css('border-radius',r); 
	}
}
$bs = function(ele, r) { $(ele).css('-moz-box-shadow',r).css('-webkit-box-shadow',r).css('box-shadow',r); }

function empty_select(s) {
	if(s.custom_select) { s.empty(); return; }
	if(s.inp)s = s.inp;
	if(s) { 
		var tmplen = s.length; for(var i=0;i<tmplen; i++) s.options[0] = null; 
	} 
}

function sel_val(s) { 
	if(s.custom_select) {
		return s.inp.value ? s.inp.value : '';
	}
	if(s.inp)s = s.inp;
	try {
		if(s.selectedIndex<s.options.length) return s.options[s.selectedIndex].value;
		else return '';
	} catch(err) { return ''; /* IE fix */ }
}

function add_sel_options(s, list, sel_val, o_style) {
	if(s.custom_select) {
		s.set_options(list)
		if(sel_val) s.inp.value = sel_val;
		return;
	}
	if(s.inp)s = s.inp;
	for(var i=0, len=list.length; i<len; i++) {
		var o = new Option(list[i], list[i], false, (list[i]==sel_val? true : false));
		if(o_style) $y(o, o_style);
		s.options[s.options.length] = o;	
	}
}

var $n = '\n';
function set_title(t) {
	document.title = (wn.title_prefix ? (wn.title_prefix + ' - ') : '') + t;
}

function $a(parent, newtag, className, cs, innerHTML, onclick) {
	if(parent && parent.substr)parent = $i(parent);
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
	if(cs)$y(c,cs);
	if(innerHTML) c.innerHTML = innerHTML;
	if(onclick) c.onclick = onclick;
	return c;
}
function $a_input(p, in_type, attributes, cs) {
	if(!attributes) attributes = {};
	
	var $input = $(p).append('<input type="'+ in_type +'">').find('input:last');
	for(key in attributes)
		$input.attr(key, attributes[key]);
		
	var input = $input.get(0);
	if(cs)
		$y(input,cs);
	return input;
}

function $dh(d) { 
	if(d && d.substr)d=$i(d); 
	if(d && d.style.display.toLowerCase() != 'none') d.style.display = 'none'; 
}
function $ds(d) { 
	if(d && d.substr)d=$i(d); 
	var t = 'block';
	if(d && in_list(['span','img','button'], d.tagName.toLowerCase())) 
		t = 'inline'
	if(d && d.style.display.toLowerCase() != t) 
		d.style.display = t; 
}
function $di(d) { if(d && d.substr)d=$i(d); if(d)d.style.display = 'inline'; }
function $i(id) { 
	if(!id) return null; 
	if(id && id.appendChild)return id; // already an element
	return document.getElementById(id); 
}
function $w(e,w) { if(e && e.style && w)e.style.width = w; }
function $h(e,h) { if(e && e.style && h)e.style.height = h; }
function $bg(e,w) { if(e && e.style && w)e.style.backgroundColor = w; }

function $y(ele, s) { 
	if(ele && s) { 
		for(var i in s) ele.style[i]=s[i]; 
	}; 
	return ele;
}

function $yt(tab, r, c, s) { /// set style on tables with wildcards
	var rmin = r; var rmax = r;
	if(r=='*') { rmin = 0; rmax = tab.rows.length-1; }
	if(r.search && r.search('-')!= -1) {
	  r = r.split('-');
	  rmin = cint(r[0]); rmax = cint(r[1]);
	}

	var cmin = c; var cmax = c;
	if(c=='*') { cmin = 0; cmax = tab.rows[0].cells.length-1; }
	if(c.search && c.search('-')!= -1) {
	  c = c.split('-');
	  rmin = cint(c[0]); rmax = cint(c[1]);
	}
	
	for(var ri = rmin; ri<=rmax; ri++) {
		for(var ci = cmin; ci<=cmax; ci++)
			$y($td(tab,ri,ci),s);
	}
}

// Make table

function make_table(parent, nr, nc, table_width, widths, cell_style, table_style) {
	var t = $a(parent, 'table');
	t.style.borderCollapse = 'collapse';
	if(table_width) t.style.width = table_width;
	if(cell_style) t.cell_style=cell_style;
	for(var ri=0;ri<nr;ri++) {
		var r = t.insertRow(ri);
		for(var ci=0;ci<nc;ci++) {
			var c = r.insertCell(ci);
			if(ri==0 && widths && widths[ci]) {
				// set widths
				c.style.width = widths[ci];
			}
			if(cell_style) {
			  for(var s in cell_style) c.style[s] = cell_style[s];
			}
		}
	}
	t.append_row = function() { return append_row(this); }
	if(table_style) $y(t, table_style);
	return t;
}

function append_row(t, at, style) {
	var r = t.insertRow(at ? at : t.rows.length);
	if(t.rows.length>1) {
		for(var i=0;i<t.rows[0].cells.length;i++) {
			var c = r.insertCell(i);
			if(style) $y(c, style);
		}
	}
	return r
}

function $td(t,r,c) { 
	if(r<0)r=t.rows.length+r;
	if(c<0)c=t.rows[0].cells.length+c;
	return t.rows[r].cells[c]; 
}

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
		var url= window.location.href.split('#')[0].split('?')[0].split('app.html')[0];
		if(url.substr(url.length-1, 1)=='/') url = url.substr(0, url.length-1)
		return url
	}	
}

get_url_arg = wn.urllib.get_arg;
get_url_dict = wn.urllib.get_dict;
