// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

window.cstr = function (s) {
	if (s == null) return "";
	return s + "";
};

window.cint = function (v, def) {
	if (v === true) return 1;
	if (v === false) return 0;
	v = v + "";
	if (v !== "0") v = lstrip(v, ["0"]);
	v = parseInt(v); // eslint-ignore-line
	if (isNaN(v)) v = def === undefined ? 0 : def;
	return v;
};

// to title case
window.toTitle = function (str) {
	var word_in = str.split(" ");
	var word_out = [];

	for (var w in word_in) {
		word_out[w] = word_in[w].charAt(0).toUpperCase() + word_in[w].slice(1);
	}

	return word_out.join(" ");
};

window.is_null = function (v) {
	if (v === null || v === undefined || cstr(v).trim() === "") return true;
};

window.copy_dict = function (d) {
	var n = {};
	for (var k in d) n[k] = d[k];
	return n;
};

window.validate_email = function (txt) {
	return frappe.utils.validate_type(txt, "email");
};

window.validate_phone = function (txt) {
	return frappe.utils.validate_type(txt, "phone");
};

window.validate_name = function (txt) {
	return frappe.utils.validate_type(txt, "name");
};

window.validate_url = function (txt) {
	return frappe.utils.validate_type(txt, "url");
};

window.nth = function (number) {
	number = cint(number);
	var s = "th";
	if ((number + "").substr(-1) == "1") s = "st";
	if ((number + "").substr(-1) == "2") s = "nd";
	if ((number + "").substr(-1) == "3") s = "rd";
	return number + s;
};

window.has_words = function (list, item) {
	if (!item) return true;
	if (!list) return false;
	for (var i = 0, j = list.length; i < j; i++) {
		if (item.indexOf(list[i]) != -1) return true;
	}
	return false;
};

window.has_common = function (list1, list2) {
	if (!list1 || !list2) return false;
	for (var i = 0, j = list1.length; i < j; i++) {
		if (list2.includes(list1[i])) return true;
	}
	return false;
};
