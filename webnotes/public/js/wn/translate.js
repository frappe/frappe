// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// for translation
wn._messages = {};
wn._ = function(txt, replace) {
	if(!txt) return txt;
	if(typeof(txt) != "string") return txt;
	return wn._messages[txt.replace(/\n/g, "")] || txt;
};