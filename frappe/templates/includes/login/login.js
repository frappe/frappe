// login.js
// don't remove this line (used in test)

window.disable_signup = {{ disable_signup and "true" or "false" }};

window.login = {};

login.bind_events = function() {
	$(window).on("hashchange", function() {
		login.route();
	});

	$(".form-login").on("submit", function(event) {
		event.preventDefault();
		var args = {};
		args.cmd = "login";
		args.usr = ($("#login_email").val() || "").trim();
		args.pwd = $("#login_password").val();
		args.device = "desktop";
		if(!args.usr || !args.pwd) {
			frappe.msgprint(__("Both login and password required"));
			return false;
		}
		login.call(args);
		return false;
	});

	$(".form-signup").on("submit", function(event) {
		event.preventDefault();
		var args = {};
		args.cmd = "frappe.core.doctype.user.user.sign_up";
		args.email = ($("#signup_email").val() || "").trim();
		args.full_name = ($("#signup_fullname").val() || "").trim();
		if(!args.email || !valid_email(args.email) || !args.full_name) {
			frappe.msgprint(__("Valid email and name required"));
			return false;
		}
		login.call(args);
		return false;
	});

	$(".form-forgot").on("submit", function(event) {
		event.preventDefault();
		var args = {};
		args.cmd = "frappe.core.doctype.user.user.reset_password";
		args.user = ($("#forgot_email").val() || "").trim();
		if(!args.user) {
			frappe.msgprint(__("Valid Login id required."));
			return false;
		}
		login.call(args);
		return false;
	});
}


login.route = function() {
	var route = window.location.hash.slice(1);
	if(!route) route = "login";
	login[route]();
}

login.login = function() {
	$("form").toggle(false);
	$(".form-login").toggle(true);
}

login.forgot = function() {
	$("form").toggle(false);
	$(".form-forgot").toggle(true);
}

login.signup = function() {
	$("form").toggle(false);
	$(".form-signup").toggle(true);
}


// Login
login.call = function(args) {
	return frappe.call({
		type: "POST",
		args: args,
		freeze: true,
		statusCode: login.login_handlers
	});
}

login.login_handlers = (function() {
	var get_error_handler = function(default_message) {
		return function(xhr, data) {
			if(xhr.responseJSON) {
				data = xhr.responseJSON;
			}

			var message = default_message;
			if (data._server_messages) {
				message = ($.map(JSON.parse(data._server_messages || '[]'), function() {
					// temp fix for messages sent as dict
					try {
						return JSON.parse(v).message;
					} catch (e) {
						return v;
					}
				}) || []).join('<br>') || default_message;
			}

			frappe.msgprint(message);
		};
	}

	var login_handlers = {
		200: function(data) {
			if(data.message=="Logged In") {
				window.location.href = get_url_arg("redirect-to") || data.home_page;
			} else if(data.message=="No App") {
				if(localStorage) {
					var last_visited =
						localStorage.getItem("last_visited")
						|| get_url_arg("redirect-to");
					localStorage.removeItem("last_visited");
				}

				if(last_visited && last_visited != "/login") {
					window.location.href = last_visited;
				} else {
					window.location.href = data.home_page;
				}
			} else if(["#signup", "#forgot"].indexOf(window.location.hash)!==-1) {
				frappe.msgprint(data.message);
			}
		},
		401: get_error_handler(__("Invalid Login")),
		417: get_error_handler(__("Oops! Something went wrong"))
	};

	return login_handlers;
})();

frappe.ready(function() {
	login.bind_events();

	if (!window.location.hash) {
		window.location.hash = "#login";
	} else {
		$(window).trigger("hashchange");
	}

	$(".form-signup, .form-forgot").removeClass("hide");
	$(document).trigger('login_rendered');
});
