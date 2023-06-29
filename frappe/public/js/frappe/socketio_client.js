import { io } from "socket.io-client";

class SocketIOCient {
	constructor() {
		this.open_tasks = {};
		this.open_docs = [];
		this.emit_queue = [];
	}

	init(port = 3000) {
		if (frappe.boot.disable_async) {
			return;
		}

		if (frappe.socketio.socket) {
			return;
		}

		// Enable secure option when using HTTPS
		if (window.location.protocol == "https:") {
			frappe.socketio.socket = io.connect(frappe.socketio.get_host(port), {
				secure: true,
				withCredentials: true,
				reconnectionAttempts: 3,
			});
		} else if (window.location.protocol == "http:") {
			frappe.socketio.socket = io.connect(frappe.socketio.get_host(port), {
				withCredentials: true,
				reconnectionAttempts: 3,
			});
		}

		if (!frappe.socketio.socket) {
			console.log("Unable to connect to " + frappe.socketio.get_host(port));
			return;
		}

		frappe.socketio.socket.on("msgprint", function (message) {
			frappe.msgprint(message);
		});

		frappe.socketio.socket.on("progress", function (data) {
			if (data.progress) {
				data.percent = (flt(data.progress[0]) / data.progress[1]) * 100;
			}
			if (data.percent) {
				frappe.show_progress(
					data.title || __("Progress"),
					data.percent,
					100,
					data.description,
					true
				);
			}
		});

		frappe.socketio.setup_listeners();

		$(document).on("form-load form-rename", function (e, frm) {
			if (!frm.doc || frm.is_new()) {
				return;
			}

			for (var i = 0, l = frappe.socketio.open_docs.length; i < l; i++) {
				var d = frappe.socketio.open_docs[i];
				if (frm.doctype == d.doctype && frm.docname == d.name) {
					// already subscribed
					return false;
				}
			}

			frappe.socketio.doc_subscribe(frm.doctype, frm.docname);
		});

		$(document).on("form-refresh", function (e, frm) {
			if (!frm.doc || frm.is_new()) {
				return;
			}

			frappe.socketio.doc_open(frm.doctype, frm.docname);
		});

		$(document).on("form-unload", function (e, frm) {
			if (!frm.doc || frm.is_new()) {
				return;
			}

			// frappe.socketio.doc_unsubscribe(frm.doctype, frm.docname);
			frappe.socketio.doc_close(frm.doctype, frm.docname);
		});

		$(document).on("form-typing", function (e, frm) {
			frappe.socketio.form_typing(frm.doctype, frm.docname);
		});

		$(document).on("form-stopped-typing", function (e, frm) {
			frappe.socketio.form_stopped_typing(frm.doctype, frm.docname);
		});

		window.addEventListener("beforeunload", () => {
			if (!cur_frm || !cur_frm.doc || cur_frm.is_new()) {
				return;
			}

			frappe.socketio.doc_close(cur_frm.doctype, cur_frm.docname);
		});
	}

	get_host(port = 3000) {
		var host = window.location.origin;
		if (window.dev_server) {
			var parts = host.split(":");
			port = frappe.boot.socketio_port || port.toString() || "3000";
			if (parts.length > 2) {
				host = parts[0] + ":" + parts[1];
			}
			host = host + ":" + port;
		}
		return host;
	}

	subscribe(task_id, opts) {
		// TODO DEPRECATE

		frappe.socketio.socket.emit("task_subscribe", task_id);
		frappe.socketio.socket.emit("progress_subscribe", task_id);

		frappe.socketio.open_tasks[task_id] = opts;
	}
	task_subscribe(task_id) {
		frappe.socketio.socket.emit("task_subscribe", task_id);
	}
	task_unsubscribe(task_id) {
		frappe.socketio.socket.emit("task_unsubscribe", task_id);
	}
	doctype_subscribe(doctype) {
		frappe.socketio.socket.emit("doctype_subscribe", doctype);
	}
	doctype_unsubscribe(doctype) {
		frappe.socketio.socket.emit("doctype_unsubscribe", doctype);
	}
	doc_subscribe(doctype, docname) {
		if (frappe.flags.doc_subscribe) {
			console.log("throttled");
			return;
		}

		frappe.flags.doc_subscribe = true;

		// throttle to 1 per sec
		setTimeout(function () {
			frappe.flags.doc_subscribe = false;
		}, 1000);

		frappe.socketio.socket.emit("doc_subscribe", doctype, docname);
		frappe.socketio.open_docs.push({ doctype: doctype, docname: docname });
	}
	doc_unsubscribe(doctype, docname) {
		frappe.socketio.socket.emit("doc_unsubscribe", doctype, docname);
		frappe.socketio.open_docs = $.filter(frappe.socketio.open_docs, function (d) {
			if (d.doctype === doctype && d.name === docname) {
				return null;
			} else {
				return d;
			}
		});
	}
	doc_open(doctype, docname) {
		frappe.socketio.socket.emit("doc_open", doctype, docname);
	}
	doc_close(doctype, docname) {
		frappe.socketio.socket.emit("doc_close", doctype, docname);
	}
	setup_listeners() {
		frappe.socketio.socket.on("task_status_change", function (data) {
			frappe.socketio.process_response(data, data.status.toLowerCase());
		});
		frappe.socketio.socket.on("task_progress", function (data) {
			frappe.socketio.process_response(data, "progress");
		});
	}
	process_response(data, method) {
		if (!data) {
			return;
		}

		// success
		var opts = frappe.socketio.open_tasks[data.task_id];
		if (opts[method]) {
			opts[method](data);
		}

		// "callback" is std frappe term
		if (method === "success") {
			if (opts.callback) opts.callback(data);
		}

		// always
		frappe.request.cleanup(opts, data);
		if (opts.always) {
			opts.always(data);
		}

		// error
		if (data.status_code && data.status_code > 400 && opts.error) {
			opts.error(data);
		}
	}
}

frappe.socketio = new SocketIOCient();

frappe.provide("frappe.realtime");
frappe.realtime.on = function (event, callback) {
	frappe.socketio.socket && frappe.socketio.socket.on(event, callback);
};

frappe.realtime.off = function (event, callback) {
	frappe.socketio.socket && frappe.socketio.socket.off(event, callback);
};

frappe.realtime.publish = function (event, message) {
	if (frappe.socketio.socket) {
		frappe.socketio.socket.emit(event, message);
	}
};
