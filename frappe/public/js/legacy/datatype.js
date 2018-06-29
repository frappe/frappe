// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.utils.full_name = function(fn, ln) {
	return fn + (ln ? ' ' : '') + (ln ? ln : '')
}

function fmt_money(v, format){
	// deprecated!
	// for backward compatibility
	return format_currency(v, format);
}


// to title case
function toTitle(str){
	var word_in = str.split(" ");
	var word_out = [];

	for(var w in word_in){
		word_out[w] = word_in[w].charAt(0).toUpperCase() + word_in[w].slice(1);
	}

	return word_out.join(" ");
}

function is_null(v) {
	if(v===null || v===undefined || cstr(v).trim()==="") return true;
}

function set_value_in(ele, v, ftype, fopt, doc) {
	$(ele).html(frappe.format(v, {fieldtype:ftype, options:fopt}, null, doc));
	return;
}
var $s = set_value_in; // used in print formats

function copy_dict(d) {
	var n = {};
	for(var k in d) n[k] = d[k];
	return n;
}

function validate_email(txt) {
	return frappe.utils.validate_type(txt, "email");
}
function validate_spl_chars(txt) {
	return frappe.utils.validate_type(txt, "alphanum")
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

function add_lists(l1, l2) {
	return [].concat(l1).concat(l2);
}

function docstring(obj)  {
	return JSON.stringify(obj);
}

function remove_from_list(list, val) {
	if(list.indexOf(val)!==-1) {
		list.splice(list.indexOf(val), 1);
	}
	return list
}

Object.assign(window, {
	fmt_money,
	toTitle,
	is_null,
	set_value_in,
	copy_dict,
	validate_email,
	validate_spl_chars,
	cstr,
	nth,
	esc_quotes,
	has_words,
	has_common,
	add_lists,
	docstring,
	remove_from_list,
});