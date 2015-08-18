frappe.socket = {
    open_tasks: {},
	open_docs: [],
	init: function() {
		if (frappe.boot.disable_async) {
			return;
		}
    	var socketio_server = frappe.boot.dev_server? '//' + document.domain + ':3000' : '//' + document.domain + ':' + window.location.port;
    	frappe.socket.socket = io.connect(socketio_server);
    	frappe.socket.socket.on('msgprint', function(message) {
    	  frappe.msgprint(message)
    	});

    	frappe.socket.setup_listeners();
    	frappe.socket.setup_reconnect();
    	$(document).on('form-load', function(e, frm) {
    		frappe.socket.doc_subscribe(frm.doctype, frm.docname);
    	});

    	// $(document).on('form-unload', function(e, frm) {
    	// 	frappe.socket.doc_unsubscribe(frm.doctype, frm.docname);
    	// });
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

$(frappe.socket.init);

frappe.provide("frappe.realtime");
frappe.realtime.on = function(event, callback) {
	frappe.socket.socket.on(event, callback);
}
