// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// for translation
wn._messages = {};
wn._ = function(txt, replace) {
	if(!txt) return txt;
	if(typeof(txt) != "string") return txt;
	preformat = wn._messages[txt.replace(/\n/g, "")] || txt;
    if(!replace) return preformat;
    if(replace instanceof Array) return vsprintf(preformat, replace);
    return repl(preformat, replace);
};
wn.translate = function(obj, keys) {
	$.each(keys, function(i, key) {
		obj["_" + key] = wn._(obj[key]);
	})
}
