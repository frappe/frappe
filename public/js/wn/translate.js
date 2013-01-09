// for translation
wn._messages = {};
wn._ = function(txt) {
	if(!txt) return txt;
	return wn._messages[txt.replace(/\n/g, "")] || txt;
};
wn.translate = function(obj, keys) {
	$.each(keys, function(i, key) {
		obj["_" + key] = wn._(obj[key]);
	})
}