wn.provide('wn.utils');

wn.utils = {
	filter_dict: function(dict, filters) {
		var ret = [];
		if(typeof filters=='string') {
			return [dict[filters]]
		}
		$.each(dict, function(i, d) {
			for(key in filters) {
				if(d[key]!=filters[key]) return;
			}
			ret.push(d);
		});
		return ret;
	},
	comma_or: function(list) {
		return wn.utils.comma_sep(list, " or ");
	},
	comma_and: function(list) {
		return wn.utils.comma_sep(list, " and ");
	},
	comma_sep: function(list, sep) {
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
}