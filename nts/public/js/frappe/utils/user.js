nts.user_info = function (uid) {
	if (!uid) uid = nts.session.user;

	let user_info;
	if (!(nts.boot.user_info && nts.boot.user_info[uid])) {
		user_info = { fullname: uid || "Unknown" };
	} else {
		user_info = nts.boot.user_info[uid];
	}

	user_info.abbr = nts.get_abbr(user_info.fullname);
	user_info.color = nts.get_palette(user_info.fullname);

	return user_info;
};

nts.update_user_info = function (user_info) {
	for (let user in user_info) {
		if (nts.boot.user_info[user]) {
			Object.assign(nts.boot.user_info[user], user_info[user]);
		} else {
			nts.boot.user_info[user] = user_info[user];
		}
	}
};

nts.provide("nts.user");

$.extend(nts.user, {
	name: "Guest",
	full_name: function (uid) {
		return uid === nts.session.user
			? __(
					"You",
					null,
					"Name of the current user. For example: You edited this 5 hours ago."
			  )
			: nts.user_info(uid).fullname;
	},
	image: function (uid) {
		return nts.user_info(uid).image;
	},
	abbr: function (uid) {
		return nts.user_info(uid).abbr;
	},
	has_role: function (rl) {
		if (typeof rl == "string") rl = [rl];
		for (var i in rl) {
			if ((nts.boot ? nts.boot.user.roles : ["Guest"]).indexOf(rl[i]) != -1)
				return true;
		}
	},
	get_desktop_items: function () {
		// hide based on permission
		var modules_list = $.map(nts.boot.allowed_modules, function (icon) {
			var m = icon.module_name;
			var type = nts.modules[m] && nts.modules[m].type;

			if (nts.boot.user.allow_modules.indexOf(m) === -1) return null;

			var ret = null;
			if (type === "module") {
				if (nts.boot.user.allow_modules.indexOf(m) != -1 || nts.modules[m].is_help)
					ret = m;
			} else if (type === "page") {
				if (nts.boot.allowed_pages.indexOf(nts.modules[m].link) != -1) ret = m;
			} else if (type === "list") {
				if (nts.model.can_read(nts.modules[m]._doctype)) ret = m;
			} else if (type === "view") {
				ret = m;
			} else if (type === "setup") {
				if (
					nts.user.has_role("System Manager") ||
					nts.user.has_role("Administrator")
				)
					ret = m;
			} else {
				ret = m;
			}

			return ret;
		});

		return modules_list;
	},

	is_report_manager: function () {
		return nts.user.has_role(["Administrator", "System Manager", "Report Manager"]);
	},

	get_formatted_email: function (email) {
		var fullname = nts.user.full_name(email);

		if (!fullname) {
			return email;
		} else {
			// to quote or to not
			var quote = "";

			// only if these special characters are found
			// why? To make the output same as that in python!
			if (fullname.search(/[\[\]\\()<>@,:;".]/) !== -1) {
				quote = '"';
			}

			return repl("%(quote)s%(fullname)s%(quote)s <%(email)s>", {
				fullname: fullname,
				email: email,
				quote: quote,
			});
		}
	},

	get_emails: () => {
		return Object.keys(nts.boot.user_info).map((key) => nts.boot.user_info[key].email);
	},

	/* Normally nts.user is an object
	 * having properties and methods.
	 * But in the following case
	 *
	 * if (nts.user === 'Administrator')
	 *
	 * nts.user will cast to a string
	 * returning nts.user.name
	 */
	toString: function () {
		return this.name;
	},
});

nts.session_alive = true;
$(document).bind("mousemove", function () {
	if (nts.session_alive === false) {
		$(document).trigger("session_alive");
	}
	nts.session_alive = true;
	if (nts.session_alive_timeout) clearTimeout(nts.session_alive_timeout);
	nts.session_alive_timeout = setTimeout("nts.session_alive=false;", 30000);
});
