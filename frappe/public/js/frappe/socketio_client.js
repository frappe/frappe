frappe.socket = {
	open_tasks: {},
	open_docs: [],
	init: function() {
		if (frappe.boot.disable_async) {
			return;
		}

		//Enable secure option when using HTTPS
		if (window.location.protocol == "https:") {
   			frappe.socket.socket = io.connect(frappe.socket.get_host(), {secure: true});
		}
		else if (window.location.protocol == "http:") {
			frappe.socket.socket = io.connect(frappe.socket.get_host());
		}

		if (!frappe.socket.socket) {
			console.log("Unable to connect to " + frappe.socket.get_host());
			return;
		}

		frappe.socket.socket.on('msgprint', function(message) {
			frappe.msgprint(message);
		});

		frappe.socket.setup_listeners();
		frappe.socket.setup_reconnect();

		$(document).on('form-load form-rename', function(e, frm) {
			if (frm.is_new()) {
				return;
			}

			for (var i=0, l=frappe.socket.open_docs.length; i<l; i++) {
				var d = frappe.socket.open_docs[i];
				if (frm.doctype==d.doctype && frm.docname==d.name) {
					// already subscribed
					return false;
				}
			}

			frappe.socket.doc_subscribe(frm.doctype, frm.docname);
		});

		$(document).on("form_refresh", function(e, frm) {
			frappe.socket.doc_open(frm.doctype, frm.docname);
		});

		$(document).on('form-unload', function(e, frm) {
			// frappe.socket.doc_unsubscribe(frm.doctype, frm.docname);
			frappe.socket.doc_close(frm.doctype, frm.docname);
		});

		window.onbeforeunload = function() {
			// if tab/window is closed, notify other users
			if (cur_frm && cur_frm.doc) {
				frappe.socket.doc_close(cur_frm.doctype, cur_frm.docname);
			}
		}
	},
	get_host: function() {
		var host = frappe.urllib.get_base_url();
		if(frappe.boot.dev_server) {
			parts = host.split(":");
			if(parts.length > 2) {
				host = parts[0] + ":" + parts[1];
			}
			host = host + ":3000";
		}
		return host;
	},
	subscribe: function(task_id, opts) {
		frappe.socket.socket.emit('task_subscribe', task_id);
		frappe.socket.socket.emit('progress_subscribe', task_id);

		frappe.socket.open_tasks[task_id] = opts;
	},
	doc_subscribe: function(doctype, docname) {
		frappe.socket.socket.emit('doc_subscribe', doctype, docname);
		frappe.socket.open_docs.push({doctype: doctype, docname: docname});
	},
	doc_unsubscribe: function(doctype, docname) {
		frappe.socket.socket.emit('doc_unsubscribe', doctype, docname);
		frappe.socket.open_docs = $.filter(frappe.socket.open_docs, function(d) {
			if(d.doctype===doctype && d.name===docname) {
				return null;
			} else {
				return d;
			}
		})
	},
	doc_open: function(doctype, docname) {
		// notify that the user has opened this doc
		frappe.socket.socket.emit('doc_open', doctype, docname);
	},
	doc_close: function(doctype, docname) {
		// notify that the user has closed this doc
		frappe.socket.socket.emit('doc_close', doctype, docname);
	},
	setup_listeners: function() {
		frappe.socket.socket.on('task_status_change', function(data) {
			frappe.socket.process_response(data, data.status.toLowerCase());
		});
		frappe.socket.socket.on('task_progress', function(data) {
		  frappe.socket.process_response(data, "progress");
		});
	},
	setup_reconnect: function() {
		// subscribe again to open_tasks
		frappe.socket.socket.on("connect", function() {
			// wait for 5 seconds before subscribing again
			// because it takes more time to start python server than nodejs server
			// and we use validation requests to python server for subscribing
			setTimeout(function() {
				$.each(frappe.socket.open_tasks, function(task_id, opts) {
					frappe.socket.subscribe(task_id, opts);
				});

				// re-connect open docs
				$.each(frappe.socket.open_docs, function(d) {
					if(locals[d.doctype] && locals[d.doctype][d.name]) {
						frappe.socket.doc_subscribe(d.doctype, d.name);
					}
				});

				if (cur_frm && cur_frm.doc) {
					frappe.socket.doc_open(cur_frm.doc.doctype, cur_frm.doc.name);
				}
			}, 5000);
		});

	},
	process_response: function(data, method) {
		if(!data) {
			return;
		}

		// success
		if(data) {
			var opts = frappe.socket.open_tasks[data.task_id];
			if(opts[method]) opts[method](data);

			// "callback" is std frappe term
			if(method==="success") {
				if(opts.callback) opts.callback(data);
			}
		}

		// always
		frappe.request.cleanup(opts, data);
		if(opts.always) {
			opts.always(data);
		}

		// error
		if(data.status_code && data.status_code > 400 && opts.error) {
			opts.error(data);
		}
	}
}

frappe.provide("frappe.realtime");
frappe.realtime.on = function(event, callback) {
	if(frappe.socket.socket) {
		frappe.socket.socket.on(event, callback);
	}
}

frappe.realtime.publish = function(event, message) {
	if(frappe.socket.socket) {
		frappe.socket.socket.emit(event, message);
	}
}
