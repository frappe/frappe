// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

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

var $n = '\n';

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
	}
	return ele;
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

frappe.urllib = {

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
		// var url= (frappe.base_url || window.location.href).split('#')[0].split('?')[0].split('desk')[0];
		var url = (frappe.base_url || window.location.origin)
		if(url.substr(url.length-1, 1)=='/') url = url.substr(0, url.length-1)
		return url
	},

	// returns absolute url
	get_full_url: function(url) {
		if(url.indexOf("http://")===0 || url.indexOf("https://")===0) {
			return url;
		}
		return url.substr(0,1)==="/" ?
			(frappe.urllib.get_base_url() + url) :
			(frappe.urllib.get_base_url() + "/" + url);
	}
}

window.get_url_arg = frappe.urllib.get_arg;
window.get_url_dict = frappe.urllib.get_dict;
