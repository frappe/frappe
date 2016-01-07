// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// My HTTP Request

frappe.provide('frappe.request');
frappe.request.url = '/';
frappe.request.ajax_count = 0;
frappe.request.waiting_for_ajax = [];

// generic server call (call page, object)
frappe.call = function(opts) {
	if(opts.quiet)
		opts.no_spinner = true;
	var args = $.extend({}, opts.args);

	// cmd
	if(opts.module && opts.page) {
		args.cmd = opts.module+'.page.'+opts.page+'.'+opts.page+'.'+opts.method;
	} else if(opts.doc) {
		$.extend(args, {
			cmd: "runserverobj",
			docs: frappe.get_doc(opts.doc.doctype, opts.doc.name),
			method: opts.method,
			args: opts.args,
		});
	} else if(opts.method) {
		args.cmd = opts.method;
	}

	var callback = function(data, response_text) {
		if(data.task_id) {
			// async call, subscribe
			frappe.socket.subscribe(data.task_id, opts);

			if(opts.queued) {
				opts.queued(data);
			}
		}
		else if (opts.callback) {
			// ajax
			return opts.callback(data, response_text);
		}
	}

	return frappe.request.call({
		type: opts.type || "POST",
		args: args,
		success: callback,
		error: opts.error,
		always: opts.always,
		btn: opts.btn,
		freeze: opts.freeze,
		freeze_message: opts.freeze_message,
		// show_spinner: !opts.no_spinner,
		async: opts.async,
		url: opts.url || frappe.request.url,
	});
}


frappe.request.call = function(opts) {
	frappe.request.prepare(opts);

	var statusCode = {
		200: function(data, xhr) {
			if(typeof data === "string") data = JSON.parse(data);
			opts.success_callback && opts.success_callback(data, xhr.responseText);
		},
		401: function(xhr) {
			msgprint(__("You have been logged out"));
			frappe.app.logout();
		},
		404: function(xhr) {
			msgprint(__("Not found"));
		},
		403: function(xhr) {
			if (xhr.responseJSON && xhr.responseJSON._server_messages) {
				var _server_messages = JSON.parse(xhr.responseJSON._server_messages);

				// avoid double messages
				if (_server_messages.indexOf(__("Not permitted"))!==-1) {
					return;
				}
			}

			frappe.utils.play_sound("error");
			msgprint(__("Not permitted"));
		},
		508: function(xhr) {
			frappe.utils.play_sound("error");
			msgprint(__("Another transaction is blocking this one. Please try again in a few seconds."));
		},
		413: function(data, xhr) {
			msgprint(__("File size exceeded the maximum allowed size of {0} MB",
				[(frappe.boot.max_file_size || 5242880) / 1048576]));
		},
		417: function(xhr) {
			var r = xhr.responseJSON;
			if (!r) {
				try {
					r = JSON.parse(xhr.responseText);
				} catch (e) {
					r = xhr.responseText;
				}
			}

			opts.error_callback && opts.error_callback(r);
		},
		501: function(data, xhr) {
			if(typeof data === "string") data = JSON.parse(data);
			opts.error_callback && opts.error_callback(data, xhr.responseText);
		},
		500: function(xhr) {
			frappe.utils.play_sound("error");
			msgprint(__("Server Error: Please check your server logs or contact tech support."))
			opts.error_callback && opts.error_callback();
			frappe.request.report_error(xhr, opts);
		},
		504: function(xhr) {
			msgprint(__("Request Timed Out"))
			opts.error_callback && opts.error_callback();
		}
	};

	var ajax_args = {
		url: opts.url || frappe.request.url,
		data: opts.args,
		type: opts.type,
		dataType: opts.dataType || 'json',
		async: opts.async,
		headers: { "X-Frappe-CSRF-Token": frappe.csrf_token },
		cache: false
	};

	frappe.last_request = ajax_args.data;

	return $.ajax(ajax_args)
		.always(function(data, textStatus, xhr) {
			if(typeof data==="string") {
				data = JSON.parse(data);
			}
			if(data.responseText) {
				var xhr = data;
				data = JSON.parse(data.responseText);
			}
			frappe.request.cleanup(opts, data);
			if(opts.always) {
				opts.always(data);
			}
		})
		.done(function(data, textStatus, xhr) {
			var status_code_handler = statusCode[xhr.statusCode().status];
			if (status_code_handler) {
				status_code_handler(data, xhr);
			}
		})
		.fail(function(xhr, textStatus) {
			var status_code_handler = statusCode[xhr.statusCode().status];
			if (status_code_handler) {
				status_code_handler(xhr);
			} else {
				// if not handled by error handler!
				opts.error_callback && opts.error_callback(xhr);
			}
		});
}

// call execute serverside request
frappe.request.prepare = function(opts) {
	frappe.request.ajax_count++;

	$("body").attr("data-ajax-state", "triggered");

	// btn indicator
	if(opts.btn) $(opts.btn).prop("disabled", true);

	// freeze page
	if(opts.freeze) frappe.dom.freeze(opts.freeze_message);

	// stringify args if required
	for(key in opts.args) {
		if(opts.args[key] && ($.isPlainObject(opts.args[key]) || $.isArray(opts.args[key]))) {
			opts.args[key] = JSON.stringify(opts.args[key]);
		}
	}

	// no cmd?
	if(!opts.args.cmd && !opts.url) {
		console.log(opts)
		throw "Incomplete Request";
	}

	opts.success_callback = opts.success;
	opts.error_callback = opts.error;
	delete opts.success;
	delete opts.error;

}

frappe.request.cleanup = function(opts, r) {
	// stop button indicator
	if(opts.btn) $(opts.btn).prop("disabled", false);

	$("body").attr("data-ajax-state", "complete");

	// un-freeze page
	if(opts.freeze) frappe.dom.unfreeze();

	// session expired? - Guest has no business here!
	if(r.session_expired || frappe.get_cookie("sid")==="Guest") {
		if(!frappe.app.logged_out) {
			localStorage.setItem("session_last_route", location.hash);
			msgprint(__('Session Expired. Logging you out'));
			frappe.app.logout();
		}
		return;
	}

	// show messages
	if(r._server_messages && !opts.silent) {
		r._server_messages = JSON.parse(r._server_messages)
		msgprint(r._server_messages);
	}

	// show errors
	if(r.exc) {
		r.exc = JSON.parse(r.exc);
		if(r.exc instanceof Array) {
			$.each(r.exc, function(i, v) {
				if(v) {
					console.log(v);
				}
			})
		} else {
			console.log(r.exc);
		}
	};

	// debug messages
	if(r._debug_messages) {
		if(opts.args) {
			console.log("======== arguments ========");
			console.log(opts.args);
			console.log("========")
		}
		$.each(JSON.parse(r._debug_messages), function(i, v) { console.log(v); });
		console.log("======== response ========");
		delete r._debug_messages;
		console.log(r);
		console.log("========");
	}

	if(r.docs || r.docinfo) {
		frappe.model.sync(r);
	}
	if(r.__messages) {
		$.extend(frappe._messages, r.__messages);
	}

	frappe.last_response = r;

	frappe.request.ajax_count--;
	if(!frappe.request.ajax_count) {
		$.each(frappe.request.waiting_for_ajax || [], function(i, fn) {
			fn();
		});
		frappe.request.waiting_for_ajax = [];
	}
}

frappe.after_ajax = function(fn) {
	if(frappe.request.ajax_count) {
		frappe.request.waiting_for_ajax.push(fn);
	} else {
		fn();
	}
}

frappe.request.report_error = function(xhr, request_opts) {
	var data = JSON.parse(xhr.responseText);
	if (data.exc) {
		var exc = (JSON.parse(data.exc) || []).join("\n");
		delete data.exc;
	} else {
		var exc = "";
	}

	if (exc) {
		var error_report_email = (frappe.boot.error_report_email || []).join(", ");
		var error_message = '<div>\
			<pre style="max-height: 300px; margin-top: 7px;">' + exc + '</pre>'
			+'<p class="text-right"><a class="btn btn-default report-btn">\
				<i class="icon-fixed-width icon-envelope"></i> '
			+ __("Report this issue") + '</a></p>'
			+'</div>';

		request_opts = frappe.request.cleanup_request_opts(request_opts);

		var msg_dialog = msgprint(error_message);

		msg_dialog.msg_area.find(".report-btn")
			.toggle(error_report_email ? true : false)
			.on("click", function() {
				var error_report_message = [
					'<h5>Please type some additional information that could help us reproduce this issue:</h5>',
					'<div style="min-height: 100px; border: 1px solid #bbb; \
						border-radius: 5px; padding: 15px; margin-bottom: 15px;"></div>',
					'<hr>',
					'<h5>App Versions</h5>',
					'<pre>' + JSON.stringify(frappe.boot.versions, null, "\t") + '</pre>',
					'<h5>Route</h5>',
					'<pre>' + frappe.get_route_str() + '</pre>',
					'<hr>',
					'<h5>Error Report</h5>',
					'<pre>' + exc + '</pre>',
					'<hr>',
					'<h5>Request Data</h5>',
					'<pre>' + JSON.stringify(request_opts, null, "\t") + '</pre>',
					'<hr>',
					'<h5>Response JSON</h5>',
					'<pre>' + JSON.stringify(data, null, '\t')+ '</pre>'
				].join("\n");

				var communication_composer = new frappe.views.CommunicationComposer({
					subject: 'Error Report [' + frappe.datetime.nowdate() + ']',
					recipients: error_report_email,
					message: error_report_message,
					doc: {
						doctype: "User",
						name: user
					}
				});
				communication_composer.dialog.$wrapper.css("z-index", cint(msg_dialog.$wrapper.css("z-index")) + 1);
			});
	}
};

frappe.request.cleanup_request_opts = function(request_opts) {
	var doc = (request_opts.args || {}).doc;
	if (doc) {
		doc = JSON.parse(doc);
		$.each(Object.keys(doc), function(i, key) {
			if (key.indexOf("password")!==-1 && doc[key]) {
				// mask the password
				doc[key] = "*****";
			}
		});
		request_opts.args.doc = JSON.stringify(doc);
	}
	return request_opts;
};
