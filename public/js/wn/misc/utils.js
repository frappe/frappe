wn.provide('wn.utils');

wn.utils.comma_or = function(list) {
	return wn.utils.comma_sep(list, " or ");
}

wn.utils.comma_and = function(list) {
	return wn.utils.comma_sep(list, " and ");
}

wn.utils.comma_sep = function(list, sep) {
	if(list instanceof Array) {
		if(list.length==0) {
			return "";
		} else if (list.length==1) {
			return list[0];
		} else {
			return list.slice(0, list.length-1).join(", ") + sep + list.slice(-1)[0];
		}
	} else {
		return list;
	}
}