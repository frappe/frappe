// Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// for translation
nts._ = function (txt, replace, context = null) {
	if (!txt) return txt;
	if (typeof txt != "string") return txt;

	let translated_text = "";

	let key = txt; // txt.replace(/\n/g, "");
	if (context) {
		translated_text = nts._messages[`${key}:${context}`];
	}

	if (!translated_text) {
		translated_text = nts._messages[key] || txt;
	}

	if (replace && typeof replace === "object") {
		translated_text = $.format(translated_text, replace);
	}
	return translated_text;
};

window.__ = nts._;

nts.get_languages = function () {
	if (!nts.languages) {
		nts.languages = [];
		$.each(nts.boot.lang_dict, function (lang, value) {
			nts.languages.push({ label: lang, value: value });
		});
		nts.languages = nts.languages.sort(function (a, b) {
			return a.value < b.value ? -1 : 1;
		});
	}
	return nts.languages;
};
