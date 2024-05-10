// login.js
// don't remove this line (used in test)

window.disable_signup = {{ disable_signup and "true" or "false" }};

window.login = {};

window.verify = {};

login.bind_events = function () {
	$(window).on("hashchange", function () {
		login.route();
	});

	var allow_login_using_mobile_number = true;
	$(".form-login").on("submit", function (event) {
		event.preventDefault();
	
		// Check if mobile number login is not allowed
		// if (!allow_login_using_mobile_number) {
			var args = {};
			args.cmd = "login";
			args.usr = frappe.utils.xss_sanitise(($("#login_email").val() || "").trim());
			args.pwd = $("#login_password").val();
	
			// Check if both login and password are provided
			if (!args.usr || !args.pwd) {
				// frappe.msgprint('{{ _("Both login and password required") }}');
				return false;
			}
	
			// Perform the login using the standard credentials
			login.call(args, null, "/login");
		// } 
	
		return false;
	});
	

	$(".form-signup").on("submit", function (event) {
		event.preventDefault();
		var args = {};
		args.cmd = "frappe.core.doctype.user.user.sign_up";
		args.email = ($("#signup_email").val() || "").trim();
		args.redirect_to = frappe.utils.sanitise_redirect(frappe.utils.get_url_arg("redirect-to"));
		args.full_name = frappe.utils.xss_sanitise(($("#signup_fullname").val() || "").trim());
		if (!args.email || !validate_email(args.email) || !args.full_name) {
			login.set_status('{{ _("Valid email and name required") }}', 'red');
			return false;
		}
		login.call(args);
		return false;
	});

	$(".form-forgot").on("submit", function (event) {
		event.preventDefault();
		var args = {};
		args.cmd = "frappe.core.doctype.user.user.reset_password";
		args.user = ($("#forgot_email").val() || "").trim();
		if (!args.user) {
			login.set_status('{{ _("Valid Login id required.") }}', 'red');
			return false;
		}
		login.call(args);
		return false;
	});

	$(".form-login-with-email-link").on("submit", function (event) {
		event.preventDefault();
		var args = {};
		args.cmd = "frappe.www.login.send_login_link";
		args.email = ($("#login_with_email_link_email").val() || "").trim();
		if (!args.email) {
			login.set_status('{{ _("Valid Login id required.") }}', 'red');
			return false;
		}
		login.call(args).then(() => {
			login.set_status('{{ _("Login link sent to your email") }}', 'blue');
			$("#login_with_email_link_email").val("");
		}).catch(() => {
			login.set_status('{{ _("Send login link") }}', 'blue');
		});

		return false;
	});

	$(".toggle-password").click(function () {
		var input = $($(this).attr("toggle"));
		if (input.attr("type") == "password") {
			input.attr("type", "text");
			$(this).text('{{ _("Hide") }}')
		} else {
			input.attr("type", "password");
			$(this).text('{{ _("Show") }}')
		}
	});

	{% if ldap_settings and ldap_settings.enabled %}
	$(".btn-ldap-login").on("click", function () {
		var args = {};
		args.cmd = "{{ ldap_settings.method }}";
		args.usr = ($("#login_email").val() || "").trim();
		args.pwd = $("#login_password").val();
		if (!args.usr || !args.pwd) {
			login.set_status('{{ _("Both login and password required") }}', 'red');
			return false;
		}
		login.call(args);
		return false;
	});
	{% endif %}
}


login.route = function () {
	var route = window.location.hash.slice(1);
	if (!route) route = "login";
	route = route.replaceAll("-", "_");
	login[route]();
}

login.reset_sections = function (hide) {
	if (hide || hide === undefined) {
		$("section.for-login").toggle(false);
		$("section.for-email-login").toggle(false);
		$("section.for-forgot").toggle(false);
		$("section.for-login-with-email-link").toggle(false);
		$("section.for-signup").toggle(false);
	}
	$('section:not(.signup-disabled) .indicator').each(function () {
		$(this).removeClass().addClass('indicator').addClass('blue')
			.text($(this).attr('data-text'));
	});
}

login.login = function () {
	login.reset_sections();
	$(".for-login").toggle(true);
}

login.email = function () {
	login.reset_sections();
	$(".for-email-login").toggle(true);
	$("#login_email").focus();
}

login.steptwo = function () {
	login.reset_sections();
	$(".for-login").toggle(true);
	$("#login_email").focus();
}

login.forgot = function () {
	login.reset_sections();
	if ($("#login_email").val()) {
		$("#forgot_email").val($("#login_email").val());
	}
	$(".for-forgot").toggle(true);
	$("#forgot_email").focus();
}

login.login_with_email_link = function () {
	login.reset_sections();
	if ($("#login_email").val()) {
		$("#login_with_email_link_email").val($("#login_email").val());
	}
	$(".for-login-with-email-link").toggle(true);
	$("#login_with_email_link_email").focus();
}

login.signup = function () {
	login.reset_sections();
	$(".for-signup").toggle(true);
	$("#signup_fullname").focus();
}


// Login
login.call = function (args, callback, url="/") {
	login.set_status('{{ _("Verifying...") }}', 'blue');

	return frappe.call({
		type: "POST",
		url: url,
		args: args,
		callback: callback,
		freeze: true,
		statusCode: login.login_handlers
	});
}

login.set_status = function (message, color) {
	$('section:visible .btn-primary').text(message)
	if (color == "red") {
		$('section:visible .page-card-body').addClass("invalid");
	}
}

login.set_invalid = function (message) {
	$(".login-content.page-card").addClass('invalid-login');
	setTimeout(() => {
		$(".login-content.page-card").removeClass('invalid-login');
	}, 500)
	login.set_status(message, 'red');
	$("#login_password").focus();
}

login.login_handlers = (function () {
	var get_error_handler = function (default_message) {
		return function (xhr, data) {
			if (xhr.responseJSON) {
				data = xhr.responseJSON;
			}

			var message = default_message;
			if (data._server_messages) {
				message = ($.map(JSON.parse(data._server_messages || '[]'), function (v) {
					// temp fix for messages sent as dict
					try {
						return JSON.parse(v).message;
					} catch (e) {
						return v;
					}
				}) || []).join('<br>') || default_message;
			}

			if (message === default_message) {
				login.set_invalid(message);
			} else {
				login.reset_sections(false);
			}

		};
	}

	var login_handlers = {
		200: function (data) {
			if (data.message == 'Logged In') {
				login.set_status('{{ _("Success") }}', 'green');
				document.body.innerHTML = `{% include "templates/includes/splash_screen.html" %}`;
				window.location.href = frappe.utils.sanitise_redirect(frappe.utils.get_url_arg("redirect-to")) || data.home_page;
			} else if (data.message == 'Password Reset') {
				window.location.href = frappe.utils.sanitise_redirect(data.redirect_to);
			} else if (data.message == "No App") {
				login.set_status("{{ _('Success') }}", 'green');
				if (localStorage) {
					var last_visited =
						localStorage.getItem("last_visited")
						|| frappe.utils.sanitise_redirect(frappe.utils.get_url_arg("redirect-to"));
					localStorage.removeItem("last_visited");
				}

				if (data.redirect_to) {
					window.location.href = frappe.utils.sanitise_redirect(data.redirect_to);
				}

				if (last_visited && last_visited != "/login") {
					window.location.href = last_visited;
				} else {
					window.location.href = data.home_page;
				}
			} else if (window.location.hash === '#forgot') {
				if (data.message === 'not found') {
					login.set_status('{{ _("Not a valid user") }}', 'red');
				} else if (data.message == 'not allowed') {
					login.set_status('{{ _("Not Allowed") }}', 'red');
				} else if (data.message == 'disabled') {
					login.set_status('{{ _("Not Allowed: Disabled User") }}', 'red');
				} else {
					login.set_status('{{ _("Instructions Emailed") }}', 'green');
				}


			} else if (window.location.hash === '#signup') {
				if (cint(data.message[0]) == 0) {
					login.set_status(data.message[1], 'red');
				} else {
					login.set_status('{{ _("Success") }}', 'green');
					frappe.msgprint(data.message[1])
				}
				//login.set_status(__(data.message), 'green');
			}

			//OTP verification
			if (data.verification && data.message != 'Logged In') {
				login.set_status('{{ _("Success") }}', 'green');

				document.cookie = "tmp_id=" + data.tmp_id;

				if (data.verification.method == 'OTP App') {
					continue_otp_app(data.verification.setup, data.verification.qrcode);
				} else if (data.verification.method == 'SMS') {
					continue_sms(data.verification.setup, data.verification.prompt);
				} else if (data.verification.method == 'Email') {
					continue_email(data.verification.setup, data.verification.prompt);
				}
			}
		},
		401: get_error_handler('{{ _("Invalid Login. Try again.") }}'),
		417: get_error_handler('{{ _("Oops! Something went wrong.") }}'),
		404: get_error_handler('{{ _("User does not exist.")}}'),
		500: get_error_handler('{{ _("Something went wrong.") }}')
	};

	return login_handlers;
})();

frappe.ready(function () {

	login.bind_events();

	if (!window.location.hash) {
		window.location.hash = "#login";
	} else {
		$(window).trigger("hashchange");
	}

	$(".form-signup, .form-forgot, .form-login-with-email-link").removeClass("hide");
	$(document).trigger('login_rendered');
});

var verify_token = function (event) {
	$(".form-verify").on("submit", function (eventx) {
		eventx.preventDefault();
		var args = {};
		args.cmd = "login";
		args.otp = $("#login_token").val();
		args.tmp_id = frappe.get_cookie('tmp_id');
		if (!args.otp) {
			frappe.msgprint('{{ _("Login token required") }}');
			return false;
		}
		login.call(args);
		return false;
	});
}

var request_otp = function (r) {
	$('.login-content').empty();
	$('.login-content:visible').append(
		`<div id="twofactor_div">
			<form class="form-verify">
				<div class="page-card-head">
					<span class="indicator blue" data-text="Verification">{{ _("Verification") }}</span>
				</div>
				<div id="otp_div"></div>
				<input type="text" id="login_token" autocomplete="off" class="form-control" placeholder={{ _("Verification Code") }} required="" autofocus="">
				<button class="btn btn-sm btn-primary btn-block mt-3" id="verify_token">{{ _("Verify") }}</button>
			</form>
		</div>`
	);
	// add event handler for submit button
	verify_token();
}

var continue_otp_app = function (setup, qrcode) {
	request_otp();
	var qrcode_div = $('<div class="text-muted" style="padding-bottom: 15px;"></div>');

	if (setup) {
		direction = $('<div>').attr('id', 'qr_info').html('{{ _("Enter Code displayed in OTP App.") }}');
		qrcode_div.append(direction);
		$('#otp_div').prepend(qrcode_div);
	} else {
		direction = $('<div>').attr('id', 'qr_info').html('{{ _("OTP setup using OTP App was not completed. Please contact Administrator.") }}');
		qrcode_div.append(direction);
		$('#otp_div').prepend(qrcode_div);
	}
}

var continue_sms = function (setup, prompt) {
	request_otp();
	var sms_div = $('<div class="text-muted" style="padding-bottom: 15px;"></div>');

	if (setup) {
		sms_div.append(prompt)
		$('#otp_div').prepend(sms_div);
	} else {
		direction = $('<div>').attr('id', 'qr_info').html(prompt || '{{ _("SMS was not sent. Please contact Administrator.") }}');
		sms_div.append(direction);
		$('#otp_div').prepend(sms_div)
	}
}

var continue_email = function (setup, prompt) {
	request_otp();
	var email_div = $('<div class="text-muted" style="padding-bottom: 15px;"></div>');

	if (setup) {
		email_div.append(prompt)
		$('#otp_div').prepend(email_div);
	} else {
		var direction = $('<div>').attr('id', 'qr_info').html(prompt || '{{ _("Verification code email not sent. Please contact Administrator.") }}');
		email_div.append(direction);
		$('#otp_div').prepend(email_div);
	}
}










$(document).ready(function () {
    $(".btn-login-mobile").on("click", function () {
        var button = $(this);

        // Get the mobile number from the input field
        var mobileNumber = $("#mobile").val();

        // Make an AJAX request to check if the mobile number exists in the user list
        frappe.call({
            method: "frappe.www.login.check_mobile",
            args: {
                mobile: mobileNumber,
            },
            callback: function (response) {
                if (response.message.status === "success") {
                    console.log(response.message.user_mobile);
                    // Mobile number exists, send OTP to the user's mobile
                    sendMobileOTP(response.message.user_mobile, button);
                } else {
                    // Mobile number not found, show an error message
                    frappe.msgprint("Mobile number not found in the user list");
                }
            },
            error: function (xhr, status, error) {
                // Handle AJAX error
                console.error("AJAX Error:", status, error);
            },
        });
    });
});

// Function to send OTP to the user's mobile
function sendMobileOTP(userMobile, button) {
    // Change button text to "Loading..."
    button.prop("disabled", true).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Loading...');

    // Make an AJAX request to send OTP to the user's mobile
    frappe.call({
        method: "frappe.www.login.send_mobile_otp",
        args: {
            mobile: userMobile,
        },
        callback: function (response) {
            // Restore the original button text
            button.prop("disabled", false).html('Send OTP');

            if (response.message.status === "success") {
                // OTP sent successfully, prompt the user to enter OTP
				frappe.msgprint(__("Verification code sent to mobile. Please enter the code."));
				localStorage.clear();
                window.location.href = "/verify_otp.html?user_mobile=" + userMobile;
            } else {
                // Failed to send OTP, show an error message
                frappe.msgprint("Failed to send OTP to mobile");
            }
        },
        error: function (xhr, status, error) {
            // Restore the original button text in case of an error
            button.prop("disabled", false).html('Send OTP');
            console.error("AJAX Error:", status, error);
        },
    });
}




// function verifyOTP(userMobile, enteredOTP) {
//     // Make an AJAX request to verify the entered OTP
//     frappe.call({
//         method: "frappe.www.login.verify_mobile_otp",
//         args: {
//             mobile: userMobile,
//             entered_otp: enteredOTP,
//         },
//         callback: function (response) {
//             if (response.message.status === "success") {
//                 // OTP verified successfully, proceed with mobile verification or login
//                 // continue_mobile(response.message.setup, response.message.prompt);
//                 alert("OTP verified. Logging in...");
//                 // Implement your logic to redirect or perform login actions
//             } else {
//                 // OTP verification failed, display an error message
//                 frappe.msgprint(response.message.message, __("Verification Failed"));
//             }
//         },
//         error: function (xhr, status, error) {
//             // Handle AJAX error
//             console.error("AJAX Error:", status, error);
//         },
//     });
// }