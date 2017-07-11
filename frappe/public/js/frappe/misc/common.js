// common file between desk and website

frappe.avatar = function(user, css_class, title) {
	if(user) {
		// desk
		var user_info = frappe.user_info(user);
	} else {
		// website
		user_info = {
			image: frappe.get_cookie("user_image"),
			fullname: frappe.get_cookie("full_name"),
			abbr: frappe.get_abbr(frappe.get_cookie("full_name")),
			color: frappe.get_palette(frappe.get_cookie("full_name"))
		}
	}

	if(!title) {
		title = user_info.fullname;
	}

	if(!css_class) {
		css_class = "avatar-small";
	}

	if(user_info.image) {

		var image = (window.cordova && user_info.image.indexOf('http')===-1) ?
			frappe.base_url + user_info.image : user_info.image;

		return repl('<span class="avatar %(css_class)s" title="%(title)s">\
			<span class="avatar-frame" style="background-image: url(%(image)s)"\
			title="%(title)s"></span></span>', {
				image: image,
				title: title,
				abbr: user_info.abbr,
				css_class: css_class
			});
	} else {
		var abbr = user_info.abbr;
		if(css_class==='avatar-small' || css_class=='avatar-xs') {
			abbr = abbr.substr(0, 1);
		}
		return repl('<span class="avatar %(css_class)s" title="%(title)s">\
			<div class="standard-image" style="background-color: %(color)s;">%(abbr)s</div></span>', {
				title: title,
				abbr: abbr,
				css_class: css_class,
				color: user_info.color
			})
	}
}


frappe.get_palette = function(txt) {
	return '#fafbfc';
	// //return '#8D99A6';
	// if(txt==='Administrator') return '#36414C';
	// // get color palette selection from md5 hash
	// var idx = cint((parseInt(md5(txt).substr(4,2), 16) + 1) / 5.33);
	// if(idx > 47) idx = 47;
	// return frappe.palette[idx][0]
}

frappe.get_abbr = function(txt, max_length) {
	if (!txt) return "";
	var abbr = "";
	$.each(txt.split(" "), function(i, w) {
		if (abbr.length >= (max_length || 2)) {
			// break
			return false;

		} else if (!w.trim().length) {
			// continue
			return true;
		}

		abbr += w.trim()[0];
	});

	return abbr || "?";
}

frappe.gravatars = {};
frappe.get_gravatar = function(email_id, size = 0) {
	var param = size ? ('s=' + size) : 'd=retro';
	if(!frappe.gravatars[email_id]) {
		// TODO: check if gravatar exists
		frappe.gravatars[email_id] = "https://secure.gravatar.com/avatar/" + md5(email_id) + "?" + param;
	}
	return frappe.gravatars[email_id];
}

// string commons

function repl(s, dict) {
	if(s==null)return '';
	for(var key in dict) {
		s = s.split("%("+key+")s").join(dict[key]);
	}
	return s;
}

function replace_all(s, t1, t2) {
	return s.split(t1).join(t2);
}

function strip_html(txt) {
	return txt.replace(/<[^>]*>/g, "");
}

var strip = function(s, chars) {
	if (s) {
		var s= lstrip(s, chars)
		s = rstrip(s, chars);
		return s;
	}
}

var lstrip = function(s, chars) {
	if(!chars) chars = ['\n', '\t', ' '];
	// strip left
	var first_char = s.substr(0,1);
	while(in_list(chars, first_char)) {
		var s = s.substr(1);
		first_char = s.substr(0,1);
	}
	return s;
}

var rstrip = function(s, chars) {
	if(!chars) chars = ['\n', '\t', ' '];
	var last_char = s.substr(s.length-1);
	while(in_list(chars, last_char)) {
		var s = s.substr(0, s.length-1);
		last_char = s.substr(s.length-1);
	}
	return s;
}

function getCookie(name) {
	return getCookies()[name];
}

frappe.get_cookie = getCookie;

function getCookies() {
	var c = document.cookie, v = 0, cookies = {};
	if (document.cookie.match(/^\s*\$Version=(?:"1"|1);\s*(.*)/)) {
		c = RegExp.$1;
		v = 1;
	}
	if (v === 0) {
		c.split(/[,;]/).map(function(cookie) {
			var parts = cookie.split(/=/, 2),
				name = decodeURIComponent(parts[0].trimLeft()),
				value = parts.length > 1 ? decodeURIComponent(parts[1].trimRight()) : null;
			if(value && value.charAt(0)==='"') {
				value = value.substr(1, value.length-2);
			}
			cookies[name] = value;
		});
	} else {
		c.match(/(?:^|\s+)([!#$%&'*+\-.0-9A-Z^`a-z|~]+)=([!#$%&'*+\-.0-9A-Z^`a-z|~]*|"(?:[\x20-\x7E\x80\xFF]|\\[\x00-\x7F])*")(?=\s*[,;]|$)/g).map(function($0, $1) {
			var name = $0,
				value = $1.charAt(0) === '"'
						? $1.substr(1, -1).replace(/\\(.)/g, "$1")
						: $1;
			cookies[name] = value;
		});
	}
	return cookies;
}

if (typeof String.prototype.trimLeft !== "function") {
	String.prototype.trimLeft = function() {
		return this.replace(/^\s+/, "");
	};
}
if (typeof String.prototype.trimRight !== "function") {
	String.prototype.trimRight = function() {
		return this.replace(/\s+$/, "");
	};
}
if (typeof Array.prototype.map !== "function") {
	Array.prototype.map = function(callback, thisArg) {
		for (var i=0, n=this.length, a=[]; i<n; i++) {
			if (i in this) a[i] = callback.call(thisArg, this[i]);
		}
		return a;
	};
}


frappe.palette = [
	['#FFC4C4', 0],
	['#FFE8CD', 0],
	['#FFD2C2', 0],
	['#FF8989', 0],
	['#FFD19C', 0],
	['#FFA685', 0],
	['#FF4D4D', 1],
	['#FFB868', 0],
	['#FF7846', 1],
	['#A83333', 1],
	['#A87945', 1],
	['#A84F2E', 1],
	['#D2D2FF', 0],
	['#F8D4F8', 0],
	['#DAC7FF', 0],
	['#A3A3FF', 0],
	['#F3AAF0', 0],
	['#B592FF', 0],
	['#7575FF', 0],
	['#EC7DEA', 0],
	['#8E58FF', 1],
	['#4D4DA8', 1],
	['#934F92', 1],
	['#5E3AA8', 1],
	['#EBF8CC', 0],
	['#FFD7D7', 0],
	['#D2F8ED', 0],
	['#D9F399', 0],
	['#FFB1B1', 0],
	['#A4F3DD', 0],
	['#C5EC63', 0],
	['#FF8989', 1],
	['#77ECCA', 0],
	['#7B933D', 1],
	['#A85B5B', 1],
	['#49937E', 1],
	['#FFFACD', 0],
	['#D2F1FF', 0],
	['#CEF6D1', 0],
	['#FFF69C', 0],
	['#A6E4FF', 0],
	['#9DECA2', 0],
	['#FFF168', 0],
	['#78D6FF', 0],
	['#6BE273', 0],
	['#A89F45', 1],
	['#4F8EA8', 1],
	['#428B46', 1]
]

frappe.is_mobile = function() {
	return $(document).width() < 768;
}

