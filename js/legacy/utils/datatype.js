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

wn.utils.full_name = function(fn, ln) { return fn + (ln ? ' ' : '') + (ln ? ln : '') }


function fmt_money(v){
	if(v==null || v=='')return '0.00'; // no nulls
	v = (v+'').replace(/,/g, ''); // remove existing commas
	v = parseFloat(v);
	if(isNaN(v)) {
		return ''; // not a number
	} else {
		var cp = wn.control_panel;
		var val = 2; // variable used to differentiate other values from Millions
		if(cp.currency_format == 'Millions') val = 3;
		v = v.toFixed(2);
		var delimiter = ","; // replace comma if desired
		amount = v+'';
		var a = amount.split('.',2)
		var d = a[1];
		var i = parseInt(a[0]);
		if(isNaN(i)) { return ''; }
		var minus = '';
		if(v < 0) { minus = '-'; }
		i = Math.abs(i);
		var n = new String(i);
		var a = [];
		if(n.length > 3)
		{
			var nn = n.substr(n.length-3);
			a.unshift(nn);
			n = n.substr(0,n.length-3);			
			while(n.length > val)
			{
				var nn = n.substr(n.length-val);
				a.unshift(nn);
				n = n.substr(0,n.length-val);
			}
		}
		if(n.length > 0) { a.unshift(n); }
		n = a.join(delimiter);
		if(d.length < 1) { amount = n; }
		else { amount = n + '.' + d; }
		amount = minus + amount;
		return amount;
	}
}

// to title case
function toTitle(str){
	var word_in = str.split(" ");
	var word_out = [];
	
	for(w in word_in){
		word_out[w] = word_in[w].charAt(0).toUpperCase() + word_in[w].slice(1);
	}
	
	return word_out.join(" ");
}

function is_null(v) {
	if(v==null) {
		return 1
	} else if(v==0) {
		if((v+'').length>=1) return 0;
		else return 1;
	} else {
		return 0
	}
}

function $s(ele, v, ftype, fopt) { 	
	if(v==null)v='';
					
	if(ftype =='Text'|| ftype =='Small Text') {
		ele.innerHTML = v?v.replace(/\n/g, '<br>'):'';
	} else if(ftype =='Date') {
		v = dateutil.str_to_user(v);
		if(v==null)v=''
		ele.innerHTML = v;
	} else if(ftype =='Link' && fopt) {
		ele.innerHTML = '';
		doc_link(ele, fopt, v);
	} else if(ftype =='Currency') {
		ele.style.textAlign = 'right';
		if(is_null(v))
			ele.innerHTML = '';
		else
			ele.innerHTML = fmt_money(v);
	} else if(ftype =='Int') {
		ele.style.textAlign = 'right';
		ele.innerHTML = v;
	} else if(ftype == 'Check') {
		if(v) ele.innerHTML = '<img src="lib/images/ui/tick.gif">';
		else ele.innerHTML = '';
	} else {
		ele.innerHTML = v;
	}
}

function clean_smart_quotes(s) {
	if(s) {
	    s = s.replace( /\u2018/g, "'" );
	    s = s.replace( /\u2019/g, "'" );
	    s = s.replace( /\u201c/g, '"' );
	    s = s.replace( /\u201d/g, '"' );
	    s = s.replace( /\u2013/g, '-' );
	    s = s.replace( /\u2014/g, '--' );
	}
    return s;
}

function copy_dict(d) {
	var n = {};
	for(var k in d) n[k] = d[k];
	return n;
}

function $p(ele,top,left) {
 ele.style.position = 'absolute';
 ele.style.top = top+'px';
 ele.style.left = left+'px';
}
function replace_newlines(t) {
	return t?t.replace(/\n/g, '<br>'):'';
}

function cstr(s) {
	if(s==null)return '';
	return s+'';
}
function nth(number) {
	number = cint(number);
	var s = 'th';
	if((number+'').substr(-1)=='1') s = 'st';
	if((number+'').substr(-1)=='2') s = 'nd';
	if((number+'').substr(-1)=='3') s = 'rd';
	return number+s;
}

function flt(v,decimals) { 
	if(v==null || v=='')return 0;
	v=(v+'').replace(/,/g,'');

	v=parseFloat(v); 
	if(isNaN(v))
		v=0; 
	if(decimals!=null)
		return parseFloat(v.toFixed(decimals));
	return v; 
}

function esc_quotes(s) { if(s==null)s=''; return s.replace(/'/, "\'");}

var crop = function(s, len) {
	if(s.length>len)
		return s.substr(0, len-3) + '...';
	else 
		return s;
}

var strip = function(s, chars) {
	var s= lstrip(s, chars)
	s = rstrip(s, chars);
	return s;
}

var lstrip = function(s, chars) {
	if(!chars) chars = ['\n', '\t', ' '];
	// strip left
	var first_char = s.substr(0,1);
	while(in_list(chars, first_char)) {
		var s = s.substr(1);
		first_char = s.substr(0,1);
	}
	return s;
}

var rstrip = function(s, chars) {
	if(!chars) chars = ['\n', '\t', ' '];
	var last_char = s.substr(s.length-1);
	while(in_list(chars, last_char)) {
		var s = s.substr(0, s.length-1);
		last_char = s.substr(s.length-1);
	}
	return s;
}

function repl_all(s, s1, s2) {
	var idx = s.indexOf(s1);
	while (idx != -1){
		s = s.replace(s1, s2);
	 	idx = s.indexOf(s1);
	}
	return s;
}
function repl(s, dict) {
	if(s==null)return '';
	for(key in dict) s = repl_all(s, '%('+key+')s', dict[key]);
	return s;
}

///// dict type

function keys(obj) { 
	var mykeys=[];
	for (key in obj) mykeys[mykeys.length]=key;
	return mykeys;
}
function values(obj) { 
	var myvalues=[];
	for (key in obj) myvalues[myvalues.length]=obj[key];
	return myvalues;
}

function in_list(list, item) {
	for(var i=0; i<list.length; i++)
		if(list[i]==item) return true;
	return false;
}
function has_common(list1, list2) {
	if(!list1 || !list2) return false;
	for(var i=0; i<list1.length; i++) {
		if(in_list(list2, list1[i]))return true;
	}
	return false;
}

var inList = in_list; // bc
function add_lists(l1, l2) {
	var l = [];
	for(var k in l1) l.push(l1[k]);
	for(var k in l2) l.push(l2[k]);
	return l;
}

function docstring(obj)  {
	return JSON.stringify(obj);
}

function DocLink(p, doctype, name, onload) {
	var a = $a(p,'span','link_type'); a.innerHTML = a.dn = name; a.dt = doctype;
	a.onclick=function() { loaddoc(this.dt,this.dn,onload) }; return a;
}
var doc_link = DocLink;

function roundNumber(num, dec) {
	var result = Math.round(num*Math.pow(10,dec))/Math.pow(10,dec);
	return result;
}

