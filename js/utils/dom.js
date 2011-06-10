function addEvent(ev, fn) {
	if(isIE) {
		document.attachEvent('on'+ev, function() { 
			fn(window.event, window.event.srcElement); 
		});
	} else {
		document.addEventListener(ev, function(e) { fn(e, e.target); }, true);
	}
}

// widget styles
// ====================================

// normal
// --------------------

$wid_normal = function(ele) {
	if(ele.disabled) return;
	$y(ele, {border:'1px solid #AAC', color:'#446'}); $gr(ele,'#FFF','#D8D8E2');
	if(ele.no_left_border) $y(ele, {borderLeft:'0px'})
	if(ele.wid_color=='green') {
		$y(ele, {color:'#FFF', border:'1px solid #4B4'}); $gr(ele,'#9C9','#4A4');
	}
}

$wid_make = function(ele,color) { 
	if(ele.disabled) return;
	fsize = ele.style.fontSize ? ele.style.fontSize : '11px';
	
	$y(ele, {padding:'2px 8px', cursor:'pointer',fontSize:fsize}); 
	$br(ele,'2px'); 
	$bs(ele, '0.5px 0.5px 2px #EEE');
	
	ele.wid_color = color ? color : 'normal';

	$wid_normal(ele);
}

// disabled
// --------------------

$wid_disabled = function(ele) { 
	ele.disabled = 1;
	$y(ele, {border:'1px solid #AAA'}); $bg(ele,'#E8E8EA'); $fg(ele,'#AAA');
}



// active (mouseover)
// --------------------

$wid_active = function(ele) {
	if(ele.disabled) return;
	$y(ele, {border:'1px solid #446', color:'#446'}); $gr(ele,'#FFF','#EEF');
	if(ele.no_left_border) $y(ele, {borderLeft:'0px'})
	if(ele.wid_color=='green') {
		$y(ele, {color:'#FFF', border:'1px solid #292'}); $gr(ele,'#AFA','#7C7');
	}
}

// pressed
// --------------------

$wid_pressed = function(ele) {
	if(ele.disabled) return;
	$y(ele, {border:'1px solid #444'}); $gr(ele,'#EEF','#DDF');
	if(ele.wid_color=='green') {
		$y(ele, {color:'#FFF', border:'1px solid #292'}); $gr(ele,'#7C7','#2A2');
	}
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
}


// join buttons
// ------------------------------------

function $btn_join(btn1, btn2) {
	$br(btn1, '0px', [0,1,1,0]);
	$br(btn2, '0px', [1,0,0,1]);
	$y(btn1, {marginRight:'0px'});
	$y(btn2, {marginLeft:'0px', borderLeft:'0px'});
	btn2.no_left_border = 1;
}


// standard input pattern
// has a standard text that clears on change
// and if onchange the value is empty, shows the text

(function($) {
	$.fn.add_default_text = function(txt) {
		return this.each(function() {
			$(this).attr('default_text', txt).bind('focus', function() {
				if(this.value==$(this).attr('default_text')) {
					$(this).val('').css('color', '#000');
				}
			}).bind('blur', function() {
				if(!this.value) {
					$(this).val($(this).attr('default_text')).css('color', '#888');
				}
			}).blur();
		});
	};
})(jQuery);

// Select
// ====================================



function validate_email(id) { if(strip(id).search("[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?")==-1) return 0; else return 1; }
function validate_spl_chars(txt) { if(txt.search(/^[a-zA-Z0-9_\- ]*$/)==-1) return 1; else return 0; }
	
function d2h(d) {return cint(d).toString(16);}
function h2d(h) {return parseInt(h,16);} 

function get_darker_shade(col, factor) {
	if(!factor) factor = 0.5;
	rgb = get_rgb(col)
	return "" + d2h(cint(rgb[0]*factor)) + d2h(cint(rgb[1]*factor)) + d2h(cint(rgb[2]*factor));
}

function get_rgb(col) {
	if(col.length==3) { return [h2d(col[0]), h2d(col[1]), h2d(col[2])] }
	else if(col.length==6) { return [h2d(col.substr(0,2)), h2d(col.substr(2,2)), h2d(col.substr(4,2))] }
	else return [];	
}

var $n = '\n';
var $f_lab = '<div style="padding: 4px; color: #888;">Fetching...</div>';

var my_title = 'Home'; var title_prefix = '';
function set_title(t) {
	document.title = (title_prefix ? (title_prefix + ' - ') : '') + t;
}




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

// add css classes etc

function set_style(txt) {
	var se = document.createElement('style');
	se.type = "text/css";
	if (se.styleSheet) {
		se.styleSheet.cssText = txt;
	} else {
		se.appendChild(document.createTextNode(txt));
	}
	document.getElementsByTagName('head')[0].appendChild(se);	
}

// sum of values in a table column
function $sum(t, cidx) {
	var s = 0;
	if(cidx<1)cidx = t.rows[0].cells.length + cidx;
	for(var ri=0; ri<t.rows.length; ri++) {
		var c = t.rows[ri].cells[cidx];
		if(c.div) s += flt(c.div.innerHTML);
		else if(c.value) s+= flt(c.value);
		else s += flt(c.innerHTML);
	}
	return s;
}



// add space holder
add_space_holder = function(parent,cs){
	if(!cs) cs = {margin:'170px 0px'}	
	$y(space_holder_div,cs);
	parent.appendChild(space_holder_div);
}

// remove space holder
remove_space_holder = function(){
	if(space_holder_div.parentNode)
		space_holder_div.parentNode.removeChild(space_holder_div);
};


