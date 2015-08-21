frappe.socket = {
	open_tasks: {},
	open_docs: [],
	init: function() {
		if (frappe.boot.disable_async) {
			return;
		}

		frappe.socket.socket = io.connect(frappe.socket.get_host());

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

		// $(document).on('form-unload', function(e, frm) {
		// 	frappe.socket.doc_unsubscribe(frm.doctype, frm.docname);
		// });
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
	setup_listeners: function() {
		frappe.socket.socket.on('task_status_change', function(data) {
		  if(data.status==="Running") {
			frappe.socket.process_response(data, "running");
		  } else {
			// failed or finished
			  frappe.socket.process_response(data, "callback");
			// delete frappe.socket.open_tasks[data.task_id];
		  }
		});
		frappe.socket.socket.on('task_progress', function(data) {
		  frappe.socket.process_response(data, "progress");
		});
	},
	setup_reconnect: function() {
		// subscribe again to open_tasks
		frappe.socket.socket.on("connect", function() {
			$.each(frappe.socket.open_tasks, function(task_id, opts) {
				frappe.socket.subscribe(task_id, opts);
			});

			// re-connect open docs
			$.each(frappe.socket.open_docs, function(d) {
				if(locals[d.doctype] && locals[d.doctype][d.name]) {
					frappe.socket.doc_subscribe(d.doctype, d.name);
				}
			})
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
	frappe.socket.socket.on(event, callback);
}
