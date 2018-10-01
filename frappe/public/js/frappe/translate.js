// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// for translation
frappe._messages = {};
frappe._ = function(txt, replace) {
	if(!txt)
		return txt;
	if(typeof(txt) != "string")
		return txt;
	var ret = frappe._messages[txt.replace(/\n/g, "")] || txt;
	if(replace && typeof(replace) === "object") {
		ret = $.format(ret, replace);
	}
	return ret;
};
window.__ = frappe._

frappe.get_languages = function() {
	if(!frappe.languages) {
		frappe.languages = []
		$.each(frappe.boot.lang_dict, function(lang, value){
			frappe.languages.push({'label': lang, 'value': value})
		});
		frappe.languages = frappe.languages.sort(function(a, b) { return (a.value < b.value) ? -1 : 1 });
	}
	return frappe.languages;
};
