wn.provide('wn.utils');

wn.utils = {
	get_file_link: function(filename) {
		return wn.utils.is_url(filename) || (filename.indexOf("images/")!=-1) || (filename.indexOf("files/")!=-1)
			? filename : 'files/' + filename;
	},
	is_url: function(txt) {
		return txt.toLowerCase().substr(0,7)=='http://'
			|| txt.toLowerCase().substr(0,8)=='https://'
	},
	filter_dict: function(dict, filters) {
		var ret = [];
		if(typeof filters=='string') {
			return [dict[filters]]
		}
		$.each(dict, function(i, d) {
			for(key in filters) {
				if($.isArray(filters[key])) {
					if(filters[key][0]=="in") {
						if(filters[key][1].indexOf(d[key])==-1)
							return;
					} else if(filters[key][0]=="not in") {
						if(filters[key][1].indexOf(d[key])!=-1)
							return;
					}
				} else {
					if(d[key]!=filters[key]) return;
				}
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
	},
	set_intro: function(me, wrapper, txt) {
		if(!me.intro_area) {
			me.intro_area = $('<div class="alert form-intro-area" style="margin-top: 20px;">')
				.insertBefore(wrapper.firstChild);
		}
		if(txt) {
			if(txt.search(/<p>/)==-1) txt = '<p>' + txt + '</p>';
			me.intro_area.html(txt);
		} else {
			me.intro_area.remove();
			me.intro_area = null;
		}
	},
	set_footnote: function(me, wrapper, txt) {
		if(!me.footnote_area) {
			me.footnote_area = $('<div class="alert form-intro-area" style="margin-top: 20px;">')
				.insertAfter(wrapper.lastChild);
		}
		
		if(txt) {
			if(txt.search(/<p>/)==-1) txt = '<p>' + txt + '</p>';
			me.footnote_area.html(txt);
		} else {
			me.footnote_area.remove();
			me.footnote_area = null;
		}
	},
	get_args_dict_from_url: function(txt) {
		var args = {};
		$.each(decodeURIComponent(txt).split("&"), function(i, arg) {
			arg = arg.split("=");
			args[arg[0]] = arg[1]
		});
		return args;
	},
	get_url_from_dict: function(args) {
		return encodeURIComponent($.map(args, function(val, key)  { return key+"="+val; }).join("&") || "");
	}
};