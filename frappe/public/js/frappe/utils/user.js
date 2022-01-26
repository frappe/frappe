frappe.user_info = function(uid) {
	if(!uid)
		uid = frappe.session.user;

	if(!(frappe.boot.user_info && frappe.boot.user_info[uid])) {
		var user_info = {fullname: uid || "Unknown"};
	} else {
		var user_info = frappe.boot.user_info[uid];
	}

	user_info.abbr = frappe.get_abbr(user_info.fullname);
	user_info.color = frappe.get_palette(user_info.fullname);

	return user_info;
};

frappe.provide('frappe.user');

$.extend(frappe.user, {
	name: 'Guest',
	full_name: function(uid) {
		return uid === frappe.session.user ?
			__("You", null, "Name of the current user. For example: You edited this 5 hours ago.") :
			frappe.user_info(uid).fullname;
	},
	image: function(uid) {
		return frappe.user_info(uid).image;
	},
	abbr: function(uid) {
		return frappe.user_info(uid).abbr;
	},
	has_role: function(rl) {
		if(typeof rl=='string')
			rl = [rl];
		for(var i in rl) {
			if((frappe.boot ? frappe.boot.user.roles : ['Guest']).indexOf(rl[i])!=-1)
				return true;
		}
	},

	is_report_manager: function() {
		return frappe.user.has_role(['Administrator', 'System Manager', 'Report Manager']);
	},

	get_formatted_email: function(email) {
		var fullname = frappe.user.full_name(email);

		if (!fullname) {
			return email;
		} else {
			// to quote or to not
			var quote = '';

			// only if these special characters are found
			// why? To make the output same as that in python!
			if (fullname.search(/[\[\]\\()<>@,:;".]/) !== -1) {
				quote = '"';
			}

			return repl('%(quote)s%(fullname)s%(quote)s <%(email)s>', {
				fullname: fullname,
				email: email,
				quote: quote
			});
		}
	},

	get_emails: ( ) => {
		return Object.keys(frappe.boot.user_info).map(key => frappe.boot.user_info[key].email);
	},

	/* Normally frappe.user is an object
	 * having properties and methods.
	 * But in the following case
	 *
	 * if (frappe.user === 'Administrator')
	 *
	 * frappe.user will cast to a string
	 * returning frappe.user.name
	 */
	toString: function() {
		return this.name;
	}
});

frappe.session_alive = true;
$(document).bind('mousemove', function() {
	if(frappe.session_alive===false) {
		$(document).trigger("session_alive");
	}
	frappe.session_alive = true;
	if(frappe.session_alive_timeout)
		clearTimeout(frappe.session_alive_timeout);
	frappe.session_alive_timeout = setTimeout('frappe.session_alive=false;', 30000);
});
