// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt 

wn.utils.full_name = function(fn, ln) { 
	return fn + (ln ? ' ' : '') + (ln ? ln : '') 
}

function fmt_money(v, format){
	return format_number(v, format);
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

function set_value_in(ele, v, ftype, fopt, doc) { 
	$(ele).html(wn.format(v, {fieldtype:ftype, options:fopt}, null, doc));
	return;
}
var $s = set_value_in; // used in print formats

function copy_dict(d) {
	var n = {};
	for(var k in d) n[k] = d[k];
	return n;
}

function replace_newlines(t) {
	return t?t.replace(/\n/g, '<br>'):'';
}

function validate_email(txt) { 
	return wn.utils.validate_type(txt, "email");
}
function validate_spl_chars(txt) { 
	return wn.utils.validate_type(txt, "alphanum")
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

function esc_quotes(s) { 
	if(s==null)s=''; 
	return s.replace(/'/, "\'");
}

var crop = function(s, len) {
	if(s.length>len)
		return s.substr(0, len-3) + '...';
	else 
		return s;
}

var strip = function(s, chars) {
	if (s) {
		var s= lstrip(s, chars)
		s = rstrip(s, chars);
		return s;
	}
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

function repl(s, dict) {
	if(s==null)return '';
	for(key in dict) {
		s = s.split("%("+key+")s").join(dict[key]);
	}
	return s;
}

var $r = repl;

function replace_all(s, t1, t2) {
	return s.split(t1).join(t2);
}

function keys(obj) { 
	var mykeys=[];
	for (var key in obj) mykeys[mykeys.length]=key;
	return mykeys;
}
function values(obj) { 
	var myvalues=[];
	for (var key in obj) myvalues[myvalues.length]=obj[key];
	return myvalues;
}

function has_words(list, item) {
	if(!item) return true;
	if(!list) return false;
	for(var i=0, j=list.length; i<j; i++) {
		if(item.indexOf(list[i])!=-1)
			return true;
	}
	return false;
}

function has_common(list1, list2) {
	if(!list1 || !list2) return false;
	for(var i=0, j=list1.length; i<j; i++) {
		if(in_list(list2, list1[i]))return true;
	}
	return false;
}

var inList = in_list; // bc
function add_lists(l1, l2) {
	return [].concat(l1).concat(l2);
}

function docstring(obj)  {
	return JSON.stringify(obj);
}
