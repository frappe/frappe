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

// on socket connection
io.on("connection", function (socket) {
	if (get_hostname(socket.request.headers.host) != get_hostname(socket.request.headers.origin)) {
		return;
	}

	if (!socket.request.headers.cookie) {
		return;
	}

	const sid = cookie.parse(socket.request.headers.cookie).sid;
	if (!sid) {
		return;
	}

	socket.user = cookie.parse(socket.request.headers.cookie).user_id;

	socket.on("task_subscribe", function (task_id) {
		var room = get_task_room(socket, task_id);
		socket.join(room);
	});

	let retries = 0;
	let join_user_room = () => {
		request
			.get(get_url(socket, "/api/method/frappe.realtime.get_user_info"))
			.type("form")
			.query({
				sid: sid,
			})
			.then((res) => {
				const room = get_user_room(socket, res.body.message.user);
				socket.join(room);
				socket.join(get_site_room(socket));
			})
			.catch((e) => {
				if (e.code === "ECONNREFUSED" && retries < 5) {
					// retry after 1s
					retries += 1;
					return setTimeout(join_user_room, 1000);
				}
				log(`Unable to join user room. ${e}`);
			});
	};

	join_user_room();

	socket.on("task_unsubscribe", function (task_id) {
		var room = get_task_room(socket, task_id);
		socket.leave(room);
	});

	socket.on("task_unsubscribe", function (task_id) {
		var room = "task:" + task_id;
		socket.leave(room);
	});

	socket.on("progress_subscribe", function (task_id) {
		var room = get_task_room(socket, task_id);
		socket.join(room);
		send_existing_lines(task_id, socket);
	});

	socket.on("doc_subscribe", function (doctype, docname) {
		can_subscribe_doc({
			socket,
			sid,
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
			sid,
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

function send_existing_lines(task_id, socket) {
	var room = get_task_room(socket, task_id);
	subscriber.hgetall("task_log:" + task_id, function (_err, lines) {
		io.to(room).emit("task_progress", {
			task_id: task_id,
			message: {
				lines: lines,
			},
		});
	});
}

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
	return get_site_name(socket) + ":user:" + user;
}

function get_site_room(socket) {
	return get_site_name(socket) + ":all";
}

function get_task_room(socket, task_id) {
	return get_site_name(socket) + ":task_progress:" + task_id;
}

function get_site_name(socket) {
	var hostname_from_host = get_hostname(socket.request.headers.host);

	if (socket.request.headers["x-frappe-site-name"]) {
		return get_hostname(socket.request.headers["x-frappe-site-name"]);
	} else if (
		["localhost", "127.0.0.1"].indexOf(hostname_from_host) !== -1 &&
		conf.default_site
	) {
		// from currentsite.txt since host is localhost
		return conf.default_site;
	} else if (socket.request.headers.origin) {
		return get_hostname(socket.request.headers.origin);
	} else {
		return get_hostname(socket.request.headers.host);
	}
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
			sid: args.sid,
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
