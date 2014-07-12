// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// My HTTP Request

frappe.provide('frappe.request');
frappe.request.url = '/';

// generic server call (call page, object)
frappe.call = function(opts) {
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

	return frappe.request.call({
		type: opts.type || "POST",
		args: args,
		success: opts.callback,
		error: opts.error,
		btn: opts.btn,
		freeze: opts.freeze,
		show_spinner: !opts.no_spinner,
		progress_bar: opts.progress_bar,
		async: opts.async
	});
}


frappe.request.call = function(opts) {
	frappe.request.prepare(opts);

	// all requests will be post, set _type as POST for commit
	opts.args._type = opts.type;

	var ajax_args = {
		url: opts.url || frappe.request.url,
		data: opts.args,
		type: 'POST',
		dataType: opts.dataType || 'json',
		statusCode: {
			200: function(data, xhr) {
				if(typeof data === "string") data = JSON.parse(data);
				opts.success && opts.success(data, xhr.responseText);
			},
			404: function(xhr) {
				msgprint(__("Not found"));
			},
			403: function(xhr) {
				msgprint(__("Not permitted"));
			},
			417: function(data, xhr) {
				if(typeof data === "string") data = JSON.parse(data);
				opts.error && opts.error(data, xhr.responseText);
			},
			501: function(data, xhr) {
				if(typeof data === "string") data = JSON.parse(data);
				opts.error && opts.error(data, xhr.responseText);
			},
			500: function(xhr) {
				msgprint(__("Server Error: Please check your server logs or contact tech support."))
				opts.error && opts.error();
				frappe.request.report_error(xhr, opts);
			}
		},
		async: opts.async
	};

	frappe.last_request = ajax_args.data;

	if(opts.progress_bar) {
		var interval = null;
		$.extend(ajax_args, {
			xhr: function() {
				var xhr = jQuery.ajaxSettings.xhr();
				interval = setInterval(function() {
					if(xhr.readyState > 2) {
				    	var total = parseInt(xhr.getResponseHeader('Original-Length') || 0) ||
							parseInt(xhr.getResponseHeader('Content-Length'));
				    	var completed = parseInt(xhr.responseText.length);
						var percent = (100.0 / total * completed).toFixed(2);
						opts.progress_bar.css('width', (percent < 10 ? 10 : percent) + '%');
					}
				}, 50);
				frappe.last_xhr = xhr;
				return xhr;
			},
			complete: function() {
				opts.progress_bar.css('width', '100%');
				clearInterval(interval);
			}
		})
	}

	return $.ajax(ajax_args)
	.fail(function(xhr, textStatus) {
		opts.error && opts.error(xhr)
	})
	.always(function(data) {
		if(typeof data==="string") {
			data = JSON.parse(data);
		}
		if(data.responseText) {
			data = JSON.parse(data.responseText);
		}
		frappe.request.cleanup(opts, data);
	});
}

// call execute serverside request
frappe.request.prepare = function(opts) {
	// btn indicator
	if(opts.btn) $(opts.btn).set_working();

	// navbar indicator
	if(opts.show_spinner) frappe.set_loading();

	// freeze page
	if(opts.freeze) frappe.dom.freeze();

	// stringify args if required
	for(key in opts.args) {
		if(opts.args[key] && ($.isPlainObject(opts.args[key]) || $.isArray(opts.args[key]))) {
			opts.args[key] = JSON.stringify(opts.args[key]);
		}
	}

	// no cmd?
	if(!opts.args.cmd) {
		console.log(opts)
		throw "Incomplete Request";
	}

}

frappe.request.cleanup = function(opts, r) {
	// stop button indicator
	if(opts.btn) $(opts.btn).done_working();

	// hide button indicator
	if(opts.show_spinner) frappe.done_loading();

	// un-freeze page
	if(opts.freeze) frappe.dom.unfreeze();

	// session expired? - Guest has no business here!
	if(r.session_expired || frappe.get_cookie("sid")==="Guest") {
		if(!frappe.app.logged_out) {
			msgprint(__('Session Expired. Logging you out'));
			frappe.app.logout();
		}
		return;
	}

	// show messages
	if(r._server_messages) {
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
		console.log("-")
		console.log("-")
		console.log("-")
		if(opts.args) {
			console.log("<<<< arguments ");
			console.log(opts.args);
			console.log(">>>>")
		}
		$.each(JSON.parse(r._debug_messages), function(i, v) { console.log(v); });
		console.log("<<<< response");
		delete r._debug_messages;
		console.log(r);
		console.log(">>>>")
		console.log("-")
		console.log("-")
		console.log("-")
	}

	if(r.docs || r.docinfo) {
		r.docs = frappe.model.sync(r);
	}
	if(r.__messages) {
		$.extend(frappe._messages, r.__messages);
	}

	frappe.last_response = r;
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
		var error_message = '<div><a class="report-btn"><i class="icon-fixed-width icon-envelope"></i> '
			+ __("Report this issue") + '</a>'
			+ '<pre style="max-height: 300px; margin-top: 7px;">' + exc + '</pre></div>';

		var msg_dialog = msgprint(error_message);

		msg_dialog.msg_area.find(".report-btn")
			.toggle(error_report_email ? true : false)
			.on("click", function() {
				var error_report_message = [
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
					subject: 'Error Report',
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
