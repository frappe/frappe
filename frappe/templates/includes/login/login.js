// login.js
// don't remove this line (used in test)

window.disable_signup = {{ disable_signup and "true" or "false" }};

window.login = {};

window.verify = {};

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
			frappe.msgprint("{{ _("Both login and password required") }}");
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
		args.redirect_to = get_url_arg("redirect-to") || '';
		args.full_name = ($("#signup_fullname").val() || "").trim();
		if(!args.email || !valid_email(args.email) || !args.full_name) {
			login.set_indicator("{{ _("Valid email and name required") }}", 'red');
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
			login.set_indicator("{{ _("Valid Login id required.") }}", 'red');
			return false;
		}
		login.call(args);
		return false;
	});

	$(".btn-ldap-login").on("click", function(){
		var args = {};
		args.cmd = "{{ ldap_settings.method }}";
		args.usr = ($("#login_email").val() || "").trim();
		args.pwd = $("#login_password").val();
		args.device = "desktop";
		if(!args.usr || !args.pwd) {
			login.set_indicator("{{ _("Both login and password required") }}", 'red');
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

login.reset_sections = function(hide) {
	if(hide || hide===undefined) {
		$("section").toggle(false);
	}
	$('section .indicator').each(function() {
		$(this).removeClass().addClass('indicator').addClass('blue')
			.text($(this).attr('data-text'));
	});
}

login.login = function() {
	login.reset_sections();
	$(".for-login").toggle(true);
}

login.steptwo = function() {
	login.reset_sections();
	$(".for-login").toggle(true);
}

login.forgot = function() {
	login.reset_sections();
	$(".for-forgot").toggle(true);
}

login.signup = function() {
	login.reset_sections();
	$(".for-signup").toggle(true);
}


// Login
login.call = function(args, callback) {
	login.set_indicator("{{ _('Verifying...') }}", 'blue');
	return frappe.call({
		type: "POST",
		args: args,
		callback: callback,
		freeze: true,
		statusCode: login.login_handlers
	});
}

login.set_indicator = function(message, color) {
	$('section:visible .indicator')
		.removeClass().addClass('indicator').addClass(color).text(message)
}

login.login_handlers = (function() {
	var get_error_handler = function(default_message) {
		return function(xhr, data) {
			if(xhr.responseJSON) {
				data = xhr.responseJSON;
			}

			var message = default_message;
			if (data._server_messages) {
				message = ($.map(JSON.parse(data._server_messages || '[]'), function(v) {
					// temp fix for messages sent as dict
					try {
						return JSON.parse(v).message;
					} catch (e) {
						return v;
					}
				}) || []).join('<br>') || default_message;
			}

			if(message===default_message) {
				login.set_indicator(message, 'red');
			} else {
				login.reset_sections(false);
			}

		};
	}

	var login_handlers = {
		200: function(data) {
			if(data.message == 'Logged In'){
				login.set_indicator("{{ _("Success") }}", 'green');
				window.location.href = get_url_arg("redirect-to") || data.home_page;
			} else if(data.message=="No App") {
				login.set_indicator("{{ _("Success") }}", 'green');
				if(localStorage) {
					var last_visited =
						localStorage.getItem("last_visited")
						|| get_url_arg("redirect-to");
					localStorage.removeItem("last_visited");
				}

				if(data.redirect_to) {
					window.location.href = data.redirect_to;
				}

				if(last_visited && last_visited != "/login") {
					window.location.href = last_visited;
				} else {
					window.location.href = data.home_page;
				}
			} else if(window.location.hash === '#forgot') {
				if(data.message==='not found') {
					login.set_indicator("{{ _("Not a valid user") }}", 'red');
				} else if (data.message=='not allowed') {
					login.set_indicator("{{ _("Not Allowed") }}", 'red');
				} else {
					login.set_indicator("{{ _("Instructions Emailed") }}", 'green');
				}


			} else if(window.location.hash === '#signup') {
				if(cint(data.message[0])==0) {
					login.set_indicator(data.message[1], 'red');
				} else {
					login.set_indicator("{{ _('Success') }}", 'green');
					frappe.msgprint(data.message[1])
				}
				//login.set_indicator(__(data.message), 'green');
			}

			//OTP verification
			if(data.verification) {
				login.set_indicator("{{ _("Success") }}", 'green');

				document.cookie = "tmp_id="+data.tmp_id;

				if (data.verification.method == 'OTP App'){
					continue_otp_app(data.verification.setup, data.verification.qrcode);
				} else if (data.verification.method == 'SMS'){
					continue_sms(data.verification.setup, data.verification.prompt);
				} else if (data.verification.method == 'Email'){
					continue_email(data.verification.setup, data.verification.prompt);
				}
			}
		},
		401: get_error_handler("{{ _("Invalid Login. Try again.") }}"),
		417: get_error_handler("{{ _("Oops! Something went wrong") }}")
	};

	return login_handlers;
} )();

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

var verify_token =  function(event) {
	$(".form-verify").on("submit", function(eventx) {
		eventx.preventDefault();
		var args = {};
		args.cmd = "login";
		args.otp = $("#login_token").val();
		args.tmp_id = frappe.get_cookie('tmp_id');
		if(!args.otp) {
			frappe.msgprint('{{ _("Login token required") }}');
			return false;
		}
		login.call(args);
		return false;
	});
}

var request_otp = function(r){
	$('.login-content').empty().append($('<div>').attr({'id':'twofactor_div'}).html(
		'<form class="form-verify">\
			<div class="page-card-head">\
				<span class="indicator blue" data-text="Verification">Verification</span>\
			</div>\
			<div id="otp_div"></div>\
			<input type="text" id="login_token" autocomplete="off" class="form-control" placeholder="Verification Code" required="" autofocus="">\
			<button class="btn btn-sm btn-primary btn-block" id="verify_token">Verify</button>\
		</form>'));
	// add event handler for submit button
	verify_token();
}

var continue_otp_app = function(setup, qrcode){
	request_otp();
	var qrcode_div = $('<div>').attr({'id':'qrcode_div','style':'text-align:center;padding-bottom:15px;'});

	if (!setup){
			direction = $('<div>').attr('id','qr_info').text('Scan QR Code and enter the resulting code displayed. \
				You can use apps such as Google Authenticator, Lastpass Authenticator, Authy, Duo Mobile and others.'),
			qrimg = $('<img>').attr({
				'src':'data:image/svg+xml;base64,' + qrcode,
				'style':'width:250px;height:250px;'});

		qrcode_div.append(direction);
		qrcode_div.append(qrimg);
		$('#otp_div').prepend(qrcode_div);
	} else {
		direction = $('<div>').attr('id','qr_info').text('Enter Code displayed in OTP App');
		qrcode_div.append(direction);
		$('#otp_div').prepend(qrcode_div);
	}
}

var continue_sms = function(setup, prompt){
	request_otp();
	var sms_div = $('<div>').attr({'id':'sms_div','style':'padding-bottom:15px;text-align:center;'});

	if (setup){
		direction = $('<div>').attr('id','sms_info').text('Enter phone number to send verification code');
		sms_div.append(direction);
		sms_div.append($('<div>').attr({'id':'sms_code_div'}).html(
				'<div class="form-group text-center">\
					<input type="text" id="phone_no" class="form-control" placeholder="2347001234567" required="" autofocus="">\
					<button class="btn btn-sm btn-primary" id="submit_phone_no" >Send SMS</button>\
				</div><hr>'));

		$('#otp_div').prepend(sms_div);

		$('#submit_phone_no').on('click',function(){
			frappe.call({
				method: "frappe.core.doctype.user.user.send_token_via_sms",
				args: {'phone_no': $('#phone_no').val(), 'tmp_id':data.tmp_id },
				freeze: true,
				callback: function(r) {
					if (r.message){
						$('#sms_div').empty().append(
							'<p class="lead">SMS sent.<br><small><small>Enter verification code received</small></small></p><hr>'
							);
					} else {
						$('#sms_div').empty().append(
							'<p class="lead">SMS not sent</p><hr>'
							);
					}
				}
			});
		})
	} else {
		direction = $('<div>').attr('id','qr_info').text(prompt || 'SMS not sent');
		sms_div.append(direction);
		$('#otp_div').prepend(sms_div)
	}
}

var continue_email = function(setup, prompt){
	request_otp();
	var email_div = $('<div>').attr({'id':'email_div','style':'padding-bottom:15px;text-align:center;'});

	if (setup){
		email_div.append('<p>Verification code email will be sent to registered email address. Enter code received below</p>')
		$('#otp_div').prepend(email_div);
		frappe.call({
			method: "frappe.core.doctype.user.user.send_token_via_email",
			args: {'tmp_id':data.tmp_id },
			callback: function(r) {
				if (r.message){
				} else {
					$('#email_div').empty().append(
						'<p>Email not sent</p><hr>'
						);
				}
			}
		});
	} else {
		var direction = $('<div>').attr('id','qr_info').text(prompt || 'Verification code email not sent');
		email_div.append(direction);
		$('#otp_div').prepend(email_div);
	}
}