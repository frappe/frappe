// common dom elements
wn.dom = {
	id_count: 0,
	
	// sets a unique id to an element
	set_unique_id: function(ele) {
		var id = 'unique-' + wn.dom.id_count;
		ele.setAttribute('id', id);
		wn.dom.id_count++;
		return id;
	}
}

/*
Shortcut functions for common dom actions
*/
$.extend(wn, {
	// getElementById
	by_id: function(id) {
		if(typeof(id)=='string') return document.getElementById(id);
		else return id;
	}
	
	// insert and append to parent
	add: function(parent, newtag, className, cs, innerHTML, onclick) {
		if(parent && parent.substr)parent = wn.ele(parent);
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
	},
	
	// IE friendly insert input
	add_input: function(p, in_type, attributes, cs) {
		if(!attributes) attributes = {};
		if(in_type) attributes.type = in_type 
		if(isIE) {
			var s= '<input ';
			for(key in attributes) s+= ' ' + key + '="'+ attributes[key] + '"';
			s+= '>'
			p.innerHTML = s
			var o = p.childNodes[0];
		} else {
			var o = wn.add(p, 'input'); 
			for(key in attributes) o.setAttribute(key, attributes[key]);
		}
		if(cs)$y(o,cs);
		return o;
	},
	
	// set style property, if key is a dict, it will set all the styles
	css: function(ele, key, val) {
		if(typeof(ele)=='string') 
			ele = $wn.by_id(ele); 
		if(typeof(key)=='string')
			if(ele) ele.style[key] = val;
		else {
			var s=key;
			if(ele && s) { 
				for(var i in s) {
					if(i.find('-')!=-1) $(ele).css(i, s[i]);
					else ele.style[i]=s[i]; 
				}
			}; 
		}
		return ele;
	}

	// hide element
	hide: function(ele) {
		wn.style(ele, 'display', 'none');
	},
	
	// show element, block for div, inline for span, img and button
	show: function(ele) {
		if(typeof(ele)=='string') ele = $wn.by_id(ele); 
		var t = 'block';
		if(d && in_list(['span','img','button'], ele.tagName.toLowerCase())) 
			t = 'inline'
		wn.style(ele, 'display', t);
	},
	
	show_inline: function() {
		wn.style(ele, 'display', 'inline')
	},
	
	// return table cell
	td: function(t, r, c) {
		if(r<0)r=t.rows.length+r;
		if(c<0)c=t.rows[0].cells.length+c;
		return t.rows[r].cells[c];		
	}
	
	// convert to integer
	cint: function(v) {
		v = parseInt(v)
		if(isNaN(v))v=def?def:0; return v;		
	}
})

// bc
$i = wn.by_id;
$a = wn.add;
$dh = wn.hide;
$ds = wn.show;
$di = wn.show_inline;
$a_input = wn.add_input;
$td = wn.td;
cint = wn.cint;

function $t(parent, txt) { 	if(parent.substr)parent = $i(parent); return parent.appendChild(document.createTextNode(txt)); }
function $w(e,w) { if(e && e.style && w)e.style.width = w; }
function $h(e,h) { if(e && e.style && h)e.style.height = h; }
function $bg(e,w) { if(e && e.style && w)e.style.backgroundColor = w; }
function $fg(e,w) { if(e && e.style && w)e.style.color = w; }
function $op(e,w) { if(e && e.style && w) { set_opacity(e,w); } }