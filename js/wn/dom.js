// add a new dom element
wn.provide('wn.dom');

wn.dom.by_id = function(id) {
	return document.getElementById(id);
}

wn.dom.eval = function(txt) {
	var el = document.createElement('script');
	el.appendChild(document.createTextNode(txt));
	// execute the script globally
	document.getElementsByTagName('head')[0].appendChild(el);
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

wn.dom.hide = function(ele) {
	ele.style.display = 'none';
}

wn.dom.show = function(ele, value) {
	if(!value) value = 'block';
	ele.style.display = value;
}	
