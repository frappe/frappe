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

function copy_dict(d) {
	var n = {};
	for(var k in d) n[k] = d[k];
	return n;
}

function validate_email(txt) {
	return frappe.utils.validate_type(txt, "email");
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


Object.assign(window, {
	fmt_money,
	toTitle,
	is_null,
	copy_dict,
	validate_email,
	cstr,
	nth,
	has_words,
	has_common,
});