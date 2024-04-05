// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// for translation
frappe._ = function (txt, replace, context = null) {
	if (!txt) return txt;
	if (typeof txt != "string") return txt;

	let translated_text = "";

	let key = txt; // txt.replace(/\n/g, "");
	if (context) {
		translated_text = frappe._messages[`${key}:${context}`];
	}

	if (!translated_text) {
		translated_text = frappe._messages[key] || txt;
	}

	if (replace && typeof replace === "object") {
		translated_text = format(translated_text, replace); // eslint-disable-line no-undef
	}
	return translated_text;
};

window.__ = frappe._;

frappe.get_languages = function () {
	if (!frappe.languages) {
		frappe.languages = [];
		Object.entries(frappe.boot.lang_dict).forEach(([lang, value]) => {
			frappe.languages.push({ label: lang, value: value });
		});
		frappe.languages = frappe.languages.sort(function (a, b) {
			return a.value < b.value ? -1 : 1;
		});
	}
	return frappe.languages;
};
