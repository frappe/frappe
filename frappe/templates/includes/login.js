if(!login) {
	var disable_signup = {{ disable_signup and "true" or "false" }};
	var login = {};

	$(document).ready(function() {
		window.location.hash = "#login";
		login.login();
	
		$(".btn-signup").click(function() {
			var args = {};
			args.cmd = "frappe.core.doctype.profile.profile.sign_up";
			args.email = ($("#signup_email").val() || "").trim();
			args.full_name = ($("#signup_fullname").val() || "").trim();

			if(!args.email || !valid_email(args.email) || !args.full_name) {
				login.set_message("Valid email and name required.");
				return false;
			}
			login.call(args);
		});
	
		$(".btn-login").click(function() {
			var args = {};
			args.cmd = "login";
			args.usr = ($("#login_email").val() || "").trim();
			args.pwd = $("#login_password").val();

			if(!args.usr || !args.pwd) {
				login.set_message("Both login and password required.");
				return false;
			}	
			login.call(args);
		});
	
		$(".btn-forgot").click(function() {
			var args = {};
			args.cmd = "frappe.core.doctype.profile.profile.reset_password";
			args.user = ($("#forgot_email").val() || "").trim();
		
			if(!args.user) {
				login.set_message("Valid Login id required.");
				return false;
			}

			login.call(args);
		});
		$(document).trigger('login_rendered');
	
	})

	$(window).on("hashchange", function() {
		login.route();
	});

	$(document).on("page_change", function() {
		if(location.pathname && location.pathname.split("/")[1].split(".")[0]==="login") 
			login.route();
	});

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
				window.location.href = "app";
			} else if(data.message=="No App") {
				if(localStorage) {
					var last_visited = localStorage.getItem("last_visited") || "/index";
					localStorage.removeItem("last_visited");
					window.location.href = last_visited;
				} else {
					window.location.href = "/index";
				}
			} else if(window.is_sign_up) {
				frappe.msgprint(data.message);
			}			
		},
		401: function(xhr, data) {
			login.set_message("Invalid Login");
		}
	}


	{% if fb_app_id is defined -%}
	// facebook login
	$(document).ready(function() {
	  var user_id = frappe.get_cookie("user_id");
	  var sid = frappe.get_cookie("sid");
  
	  // logged in?
	  if(!sid || sid==="Guest") {
		  // fallback on facebook login -- no login again
		  $(".btn-facebook").removeAttr("disabled");
	  } else {
		  // get private stuff (if access)
		  // app.setup_user({"user": user_id});
	  }
  
	});

	$(function() {
		$login = $(".btn-facebook").prop("disabled", true);
		$.getScript('//connect.facebook.net/en_UK/all.js', function() {
			$login.prop("disabled", false);
			FB.init({
			  appId: '{{ fb_app_id }}',
			}); 
			$login.click(function() {
				$login.prop("disabled", true).html("Logging In...");
				login.via_facebook();
			});
		});
	});

	login.via_facebook = function() {
		// not logged in to facebook either
		FB.login(function(response) {
		   if (response.authResponse) {
			   // yes logged in via facebook
			   console.log('Welcome!  Fetching your information.... ');
			   var fb_access_token = response.authResponse.accessToken;

			   // get user graph
			   FB.api('/me', function(response) {
				   response.fb_access_token = fb_access_token || "[none]";
				   $.ajax({
						url:"/",
						type: "POST",
						data: {
							cmd:"frappe.core.doctype.profile.profile.facebook_login",
							data: JSON.stringify(response)
						},
						statusCode: login.login_handlers
					})
				});
			} else {
				frappe.msgprint("You have denied access to this application via Facebook. \
					Please change your privacy settings in Facebook and try again. \
					If you do not want to use Facebook login, <a href='/login'>sign-up</a> here");
			}
		},{scope:"email"});	
	}
	{%- endif %}
}

