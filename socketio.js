const cookie = require("cookie");
const request = require("superagent");

const { get_conf, get_redis_subscriber } = require("./node_utils");
const conf = get_conf();
const log = console.log; // eslint-disable-line
const subscriber = get_redis_subscriber();

const io = require("socket.io")(conf.socketio_port, {
	cors: {
		// Should be fine since we are ensuring whether hostname and origin are same before adding setting listeners for s socket
		origin: true,
		credentials: true,
	},
});

io.use((socket, next) => {
	if (get_hostname(socket.request.headers.host) != get_hostname(socket.request.headers.origin)) {
		next(new Error("Invalid origin"));
		return;
	}

	if (!socket.request.headers.cookie) {
		next(new Error("No cookie transmitted."));
		return;
	}

	let cookies = cookie.parse(socket.request.headers.cookie);

	if (!cookies.sid) {
		next(new Error("No sid transmitted."));
		return;
	}

	request
		.get(get_url(socket, "/api/method/frappe.realtime.get_user_info"))
		.type("form")
		.query({
			sid: cookies.sid,
		})
		.then((res) => {
			socket.user = res.body.message.user;
			socket.user_type = res.body.message.user_type;
			socket.sid = cookies.sid;
			next();
		})
		.catch((e) => {
			next(new Error(`Unauthorized: ${e}`));
		});
});

// on socket connection
io.on("connection", function (socket) {
	socket.join(get_user_room(socket, socket.user));
	socket.join(get_website_room(socket));

	if (socket.user_type == "System User") {
		socket.join(get_site_room(socket));
	}

	socket.on("doctype_subscribe", function (doctype) {
		can_subscribe_doctype({
			socket,
			doctype,
			callback: () => {
				socket.join(get_doctype_room(socket, doctype));
			},
		});
	});

	socket.on("doctype_unsubscribe", function (doctype) {
		socket.leave(get_doctype_room(socket, doctype));
	});

	socket.on("task_subscribe", function (task_id) {
		var room = get_task_room(socket, task_id);
		socket.join(room);
	});

	socket.on("task_unsubscribe", function (task_id) {
		var room = get_task_room(socket, task_id);
		socket.leave(room);
	});

	socket.on("progress_subscribe", function (task_id) {
		var room = get_task_room(socket, task_id);
		socket.join(room);
	});

	socket.on("doc_subscribe", function (doctype, docname) {
		can_subscribe_doc({
			socket,
			doctype,
			docname,
			callback: () => {
				var room = get_doc_room(socket, doctype, docname);
				socket.join(room);
			},
		});
	});

	socket.on("doc_unsubscribe", function (doctype, docname) {
		var room = get_doc_room(socket, doctype, docname);
		socket.leave(room);
	});

	socket.on("doc_open", function (doctype, docname) {
		can_subscribe_doc({
			socket,
			doctype,
			docname,
			callback: () => {
				var room = get_open_doc_room(socket, doctype, docname);
				socket.join(room);

				// show who is currently viewing the form
				send_users(
					{
						socket: socket,
						doctype: doctype,
						docname: docname,
					},
					"view"
				);

				// show who is currently typing on the form
				send_users(
					{
						socket: socket,
						doctype: doctype,
						docname: docname,
					},
					"type"
				);
			},
		});
	});

	socket.on("doc_close", function (doctype, docname) {
		// remove this user from the list of 'who is currently viewing the form'
		var room = get_open_doc_room(socket, doctype, docname);
		socket.leave(room);
		send_users(
			{
				socket: socket,
				doctype: doctype,
				docname: docname,
			},
			"view"
		);
	});

	socket.on("doc_typing", function (doctype, docname) {
		// show users that are currently typing on the form
		const room = get_typing_room(socket, doctype, docname);
		socket.join(room);

		send_users(
			{
				socket: socket,
				doctype: doctype,
				docname: docname,
			},
			"type"
		);
	});

	socket.on("doc_typing_stopped", function (doctype, docname) {
		// remove this user from the list of users currently typing on the form'
		const room = get_typing_room(socket, doctype, docname);
		socket.leave(room);

		send_users(
			{
				socket: socket,
				doctype: doctype,
				docname: docname,
			},
			"type"
		);
	});

	socket.on("open_in_editor", (data) => {
		let s = get_redis_subscriber("redis_socketio");
		s.publish("open_in_editor", JSON.stringify(data));
	});
});

subscriber.on("message", function (_channel, message) {
	message = JSON.parse(message);

	if (message.room) {
		io.to(message.room).emit(message.event, message.message);
	} else {
		io.emit(message.event, message.message);
	}
});

subscriber.subscribe("events");

function get_doc_room(socket, doctype, docname) {
	return get_site_name(socket) + ":doc:" + doctype + "/" + docname;
}

function get_open_doc_room(socket, doctype, docname) {
	return get_site_name(socket) + ":open_doc:" + doctype + "/" + docname;
}

function get_typing_room(socket, doctype, docname) {
	return get_site_name(socket) + ":typing:" + doctype + "/" + docname;
}

function get_user_room(socket, user) {
	return get_site_name(socket) + ":user:" + user || socket.user;
}

function get_site_room(socket) {
	return get_site_name(socket) + ":all";
}

function get_website_room(socket) {
	return get_site_name(socket) + ":website";
}

function get_doctype_room(socket, doctype) {
	return get_site_name(socket) + ":doctype:" + doctype;
}

function get_task_room(socket, task_id) {
	return get_site_name(socket) + ":task_progress:" + task_id;
}

function get_site_name(socket) {
	if (socket.site_name) {
		return socket.site_name;
	} else if (socket.request.headers["x-frappe-site-name"]) {
		socket.site_name = get_hostname(socket.request.headers["x-frappe-site-name"]);
	} else if (
		conf.default_site &&
		["localhost", "127.0.0.1"].indexOf(get_hostname(socket.request.headers.host)) !== -1
	) {
		// from currentsite.txt since host is localhost
		socket.site_name = conf.default_site;
	} else if (socket.request.headers.origin) {
		socket.site_name = get_hostname(socket.request.headers.origin);
	} else {
		socket.site_name = get_hostname(socket.request.headers.host);
	}
	return socket.site_name;
}

function get_hostname(url) {
	if (!url) return undefined;
	if (url.indexOf("://") > -1) {
		url = url.split("/")[2];
	}
	return url.match(/:/g) ? url.slice(0, url.indexOf(":")) : url;
}

function get_url(socket, path) {
	if (!path) {
		path = "";
	}
	return socket.request.headers.origin + path;
}

function can_subscribe_doc(args) {
	if (!args) return;
	if (!args.doctype || !args.docname) return;
	request
		.get(get_url(args.socket, "/api/method/frappe.realtime.can_subscribe_doc"))
		.type("form")
		.query({
			sid: args.socket.sid,
			doctype: args.doctype,
			docname: args.docname,
		})
		.end(function (err, res) {
			if (!res) {
				log("No response for doc_subscribe");
			} else if (res.status == 403) {
				return;
			} else if (err) {
				log(err);
			} else if (res.status == 200) {
				args.callback(err, res);
			} else {
				log("Something went wrong", err, res);
			}
		});
}

function can_subscribe_doctype(args) {
	if (!args) return;
	if (!args.doctype) return;
	request
		.get(get_url(args.socket, "/api/method/frappe.realtime.can_subscribe_doctype"))
		.type("form")
		.query({
			sid: args.socket.sid,
			doctype: args.doctype,
		})
		.end(function (err, res) {
			if (!res || res.status == 403 || err) {
				if (err) {
					log(err);
				}
				return false;
			} else if (res.status == 200) {
				args.callback && args.callback(err, res);
				return true;
			}
			log("ERROR (can_subscribe_doctype): ", err, res);
		});
}

function send_users(args, action) {
	if (!(args && args.doctype && args.docname)) {
		return;
	}

	const open_doc_room = get_open_doc_room(args.socket, args.doctype, args.docname);

	const room =
		action == "view"
			? open_doc_room
			: get_typing_room(args.socket, args.doctype, args.docname);

	const clients = Array.from(io.sockets.adapter.rooms.get(room) || []);

	let users = [];
	io.sockets.sockets.forEach((sock) => {
		if (clients.includes(sock.id)) {
			users.push(sock.user);
		}
	});

	const emit_event = action == "view" ? "doc_viewers" : "doc_typers";

	// notify
	io.to(open_doc_room).emit(emit_event, {
		doctype: args.doctype,
		docname: args.docname,
		users: Array.from(new Set(users)),
	});
}
