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
		if(!args.usr || !args.pwd) {
			frappe.msgprint("Both login and password required.");
			return false;
		}	
		login.call(args);
	});

	$(".form-signup").on("submit", function() {
		event.preventDefault();
		var args = {};
		args.cmd = "frappe.core.doctype.user.user.sign_up";
		args.email = ($("#signup_email").val() || "").trim();
		args.full_name = ($("#signup_fullname").val() || "").trim();
		if(!args.email || !valid_email(args.email) || !args.full_name) {
			frappe.msgprint("Valid email and name required.");
			return false;
		}
		login.call(args);
	});

	$(".form-forgot").on("submit", function() {
		event.preventDefault();
		var args = {};
		args.cmd = "frappe.core.doctype.user.user.reset_password";
		args.user = ($("#forgot_email").val() || "").trim();
		if(!args.user) {
			frappe.msgprint("Valid Login id required.");
			return false;
		}
		login.call(args);
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
	$('.btn-primary').prop("disabled", true);

	$.ajax({
		type: "POST",
		url: "/",
		data: args,
		dataType: "json",
		statusCode: login.login_handlers
	}).always(function(){
		$('.btn-primary').prop("disabled", false);
	})
}

login.login_handlers = {
	200: function(data) {
		if(data.message=="Logged In") {
			window.location.href = "desk";
		} else if(data.message=="No App") {
			if(localStorage) {
				var last_visited = localStorage.getItem("last_visited") || "/index";
				localStorage.removeItem("last_visited");
				window.location.href = last_visited;
			} else {
				window.location.href = "/index";
			}
		} else if(["#signup", "#forgot"].indexOf(window.location.hash)!==-1) {
			frappe.msgprint(data.message);
		}			
	},
	401: function(xhr, data) {
		frappe.msgprint("Invalid Login");
	}
}

frappe.ready(function() {
	window.location.hash = "#login";
	login.bind_events();
	login.login();
	$(document).trigger('login_rendered');
});
