var disable_signup = {{ disable_signup and "true" or "false" }};
var login = {};

$(document).ready(function(wrapper) {
	login.show_login();
	
	$('#login_btn').click(login.do_login);
		
	$('#pass').keypress(function(ev){
		if(ev.which==13 && $('#pass').val()) {
			$("#login_btn").click();
		}
	});
	$(document).trigger('login_rendered');
})

// Login
login.do_login = function(){
	var args = {};
	if(window.is_sign_up) {
		args.cmd = "core.doctype.profile.profile.sign_up";
		args.email = ($("#login_id").val() || "").trim();
		args.full_name = ($("#full_name").val() || "").trim();

		if(!args.email || !valid_email(args.email) || !args.full_name) {
			login.set_message("Valid email and name required.");
			return false;
		}
	} else if(window.is_forgot) {
		args.cmd = "reset_password";
		args.user = ($("#login_id").val() || "").trim();
		
		if(!args.user) {
			login.set_message("Valid Login Id required.");
			return false;
		}

	} else {
		args.cmd = "login"
		args.usr = ($("#login_id").val() || "").trim();
		args.pwd = $("#pass").val();

		if(!args.usr || !args.pwd) {
			login.set_message("Both login and password required.");
			return false;
		}	
	}

	$('#login_btn').attr("disabled", "disabled");
	$("#login-spinner").toggle(true);
	$('#login_message').toggle(false);
	
	$.ajax({
		type: "POST",
		url: "server.py",
		data: args,
		dataType: "json",
		success: function(data) {
			$("#login-spinner").toggle(false);
			$('#login_btn').attr("disabled", false);
			if(data.message=="Logged In") {
				window.location.href = "app.html";
			} else if(data.message=="No App") {
				if(localStorage) {
					window.location.href = localStorage.getItem("last_visited") || "index";
					localStorage.removeItem("last_visited");
				} else {
					window.location.href = "index";
				}
			} else {
				login.set_message(data.message);
			}
		}
	})
	
	return false;
}

login.show_login = function() {
	$("#login_wrapper h3").html("Login");
	$("#login-label").html("Email Id");
	$("#password-row").toggle(true);
	$("#full-name-row, #login_message").toggle(false);
	$("#login_btn").html("Login").removeClass("btn-success");
	$("#switch-view").html('<a \
		onclick="return login.show_forgot_password()">Forgot Password?</a>');
	
	if(!disable_signup) {
		$("#switch-view").append('<hr><div>\
			New User? <button class="btn btn-success" style="margin-left: 10px; margin-top: -2px;"\
				onclick="return login.show_sign_up()">Sign Up</button></div>');
	}

	window.is_login = true;
	window.is_sign_up = false;
	window.is_forgot = false;
}

login.show_sign_up = function() {
	$("#login_wrapper h3").html("Sign Up");
	$("#login-label").html("Email Id");
	$("#password-row, #login_message").toggle(false);
	$("#full-name-row").toggle(true);
	$("#login_btn").html("Sign Up").addClass("btn-success");
	$("#switch-view").html("<a onclick='return login.show_login()' href='#'>Login</a>");
	window.is_sign_up = true;
}

login.show_forgot_password = function() {
	$("#login_wrapper h3").html("Forgot");
	$("#login-label").html("Email Id");
	$("#password-row, #login_message, #full-name-row").toggle(false);
	$("#login_btn").html("Send Password").removeClass("btn-success");
	$("#switch-view").html("<a onclick='return login.show_login()' href='#'>Login</a>");
	window.is_forgot = true;
	window.is_sign_up = false;
}

login.set_message = function(message, color) {
	$('#login_message').html(message).toggle(true);	
}