// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// for translation
frappe._messages = {};
frappe._ = function(txt, replace) {
	if(!txt)
		return txt;
	if(typeof(txt) != "string")
		return txt;
	ret = frappe._messages[txt.replace(/\n/g, "")] || txt;
	if(replace && typeof(replace) === "object") {
		ret = $.format(ret, replace);
	}
	return ret;
};
window.__ = frappe._

frappe.get_languages_dict = function() {
	var lang_dict = []
	$.each(frappe.boot.lang_dict, function(lang, val){
		lang_dict.push({'label': lang, 'value': val})
	})
	return lang_dict
};
