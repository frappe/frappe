var app = require('express')();
var server = require('http').Server(app);
var io = require('socket.io')(server);
var cookie = require('cookie');
var request = require('superagent');
var { get_conf, get_redis_subscriber } = require('./node_utils');

const log = console.log; // eslint-disable-line

var conf = get_conf();
var subscriber = get_redis_subscriber();

// serve socketio
server.listen(conf.socketio_port, function () {
	log('listening on *:', conf.socketio_port); //eslint-disable-line
});

<<<<<<< HEAD
// on socket connection
io.on('connection', function (socket) {
=======
io.use((socket, next) => {
>>>>>>> 4de9c39bb8 (refactor: SocketIO)
	if (get_hostname(socket.request.headers.host) != get_hostname(socket.request.headers.origin)) {
		next(new Error("Invalid origin"));
		return;
	}

	if (!socket.request.headers.cookie) {
		next(new Error("No cookie transmitted."));
		return;
	}

	const cookies = cookie.parse(socket.request.headers.cookie);

	if (!cookies.sid) {
		next(new Error("No sid transmitted."));
		return;
	}
	socket.sid = cookies.sid;
	socket.user = cookies.user_id;

<<<<<<< HEAD
	socket.user = cookie.parse(socket.request.headers.cookie).user_id;

	// frappe.chat
	socket.on("frappe.chat.room:subscribe", function (rooms) {
		if (!Array.isArray(rooms)) {
			rooms = [rooms];
		}

		for (var room of rooms) {
			log('frappe.chat: Subscribing ' + socket.user + ' to room ' + room);
			room = get_chat_room(socket, room);

			log('frappe.chat: Subscribing ' + socket.user + ' to event ' + room);
			socket.join(room);
		}
	});

	socket.on("frappe.chat.message:typing", function (data) {
		const user = data.user;
		const room = get_chat_room(socket, data.room);

		log('frappe.chat: Dispatching ' + user + ' typing to room ' + room);

		io.to(room).emit('frappe.chat.room:typing', {
			room: data.room,
			user: user
		});
	});
	// end frappe.chat

	let retries = 0;
	let join_chat_room = () => {
		request.get(get_url(socket, '/api/method/frappe.realtime.get_user_info'))
			.type('form')
			.query({
				sid: sid
			})
			.then(res => {
				const room = get_user_room(socket, res.body.message.user);
				socket.join(room);
				socket.join(get_site_room(socket));
			})
			.catch(e => {
				if (e.code === 'ECONNREFUSED' && retries < 5) {
					// retry after 1s
					retries += 1;
					return setTimeout(join_chat_room, 1000);
				}
				log(`Unable to join chat room. ${e}`);
			});
	};

	join_chat_room();
=======
	request
		.get(get_url(socket, "/api/method/frappe.realtime.get_user_info"))
		.type("form")
		.query({
			sid: socket.sid,
		})
		.then((res) => {
			socket.user = res.body.message.user;
			socket.user_type = res.body.message.user_type;
		})
		.catch((e) => {
			next(new Error(`Unauthorized: ${e}`));
			return;
		});

	next();
});

// on socket connection
io.on("connection", function (socket) {
	const room = get_user_room(socket);
	socket.join(room);

	if (socket.user_type == "System User") {
		socket.join(get_site_room(socket));
	}
>>>>>>> 4de9c39bb8 (refactor: SocketIO)

<<<<<<< HEAD
	socket.on('task_subscribe', function (task_id) {
=======
	socket.on("list_update", function (doctype) {
		can_subscribe_list({
			socket,
			doctype,
			callback: () => {
				socket.join(get_doctype_room(socket, doctype));
			},
		});
	});

	socket.on("task_subscribe", function (task_id) {
>>>>>>> 9931c3af04 (refactor(socketio)!: list_update)
		var room = get_task_room(socket, task_id);
		socket.join(room);
	});

	socket.on('task_unsubscribe', function (task_id) {
		var room = get_task_room(socket, task_id);
		socket.leave(room);
	});

	socket.on('progress_subscribe', function (task_id) {
		var room = get_task_room(socket, task_id);
		socket.join(room);
		send_existing_lines(task_id, socket);
	});

<<<<<<< HEAD
<<<<<<< HEAD
	socket.on('doc_subscribe', function (doctype, docname) {
=======
	socket.on("docinfo_update", function (doctype, docname) {
		can_subscribe_doc({
			socket,
			doctype,
			docname,
			callback: () => {
				var room = get_docinfo_room(socket, doctype, docname);
				socket.join(room);
			},
		});
	});

=======
>>>>>>> 3a8fa6cbd5 (refactor(socketio): Use same room for doc & info events)
	socket.on("doc_subscribe", function (doctype, docname) {
>>>>>>> 97d2eab3e2 (refactor(socketio): docinfo_update)
		can_subscribe_doc({
			socket,
			doctype,
			docname,
			callback: () => {
				var room = get_doc_room(socket, doctype, docname);
				socket.join(room);
			}
		});
	});

	socket.on('doc_unsubscribe', function (doctype, docname) {
		var room = get_doc_room(socket, doctype, docname);
		socket.leave(room);
	});

	socket.on('task_unsubscribe', function (task_id) {
		var room = 'task:' + task_id;
		socket.leave(room);
	});

	socket.on('doc_open', function (doctype, docname) {
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
					'view'
				);

				// show who is currently typing on the form
				send_users(
					{
						socket: socket,
						doctype: doctype,
						docname: docname,
					},
					'type'
				);
			}
		});
	});

	socket.on('doc_close', function (doctype, docname) {
		// remove this user from the list of 'who is currently viewing the form'
		var room = get_open_doc_room(socket, doctype, docname);
		socket.leave(room);
		send_users(
			{
				socket: socket,
				doctype: doctype,
				docname: docname,
			},
			'view'
		);
	});

	socket.on('doc_typing', function (doctype, docname) {
		// show users that are currently typing on the form
		const room = get_typing_room(socket, doctype, docname);
		socket.join(room);

		send_users(
			{
				socket: socket,
				doctype: doctype,
				docname: docname,
			},
			'type'
		);
	});

	socket.on('doc_typing_stopped', function (doctype, docname) {
		// remove this user from the list of users currently typing on the form'
		const room = get_typing_room(socket, doctype, docname);
		socket.leave(room);

		send_users(
			{
				socket: socket,
				doctype: doctype,
				docname: docname,
			},
			'type'
		);
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
	subscriber.hgetall('task_log:' + task_id, function (_err, lines) {
		io.to(room).emit('task_progress', {
			"task_id": task_id,
			"message": {
				"lines": lines
			}
		});
	});
}

function get_doc_room(socket, doctype, docname) {
	return get_site_name(socket) + ':doc:' + doctype + '/' + docname;
}

function get_open_doc_room(socket, doctype, docname) {
	return get_site_name(socket) + ':open_doc:' + doctype + '/' + docname;
}

function get_typing_room(socket, doctype, docname) {
	return get_site_name(socket) + ':typing:' + doctype + '/' + docname;
}

function get_user_room(socket, user) {
<<<<<<< HEAD
	return get_site_name(socket) + ':user:' + user;
=======
	return get_site_name(socket) + ":user:" + user || socket.user;
>>>>>>> 4de9c39bb8 (refactor: SocketIO)
}

function get_site_room(socket) {
	return get_site_name(socket) + ':all';
}

function get_doctype_room(socket, doctype) {
	return get_site_name(socket) + ":doctype:" + doctype;
}

function get_task_room(socket, task_id) {
	return get_site_name(socket) + ':task_progress:' + task_id;
}

// frappe.chat
// If you're thinking on multi-site or anything, please
// update frappe.async as well.
function get_chat_room(socket, room) {
	var room = get_site_name(socket) + ":room:" + room;

	return room
}

function get_site_name(socket) {
<<<<<<< HEAD
	var hostname_from_host = get_hostname(socket.request.headers.host);

	if (socket.request.headers['x-frappe-site-name']) {
		return get_hostname(socket.request.headers['x-frappe-site-name']);
	} else if (['localhost', '127.0.0.1'].indexOf(hostname_from_host) !== -1 &&
		conf.default_site) {
=======
	if (socket.site_name) {
		return socket.site_name;
	} else if (socket.request.headers["x-frappe-site-name"]) {
		socket.site_name = get_hostname(socket.request.headers["x-frappe-site-name"]);
	} else if (
		conf.default_site &&
		["localhost", "127.0.0.1"].indexOf(get_hostname(socket.request.headers.host)) !== -1
	) {
>>>>>>> 54bf617d09 (perf(socketio): get_site_name)
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
		url = url.split('/')[2];
	}
	return (url.match(/:/g)) ? url.slice(0, url.indexOf(":")) : url
}

function get_url(socket, path) {
	if (!path) {
		path = '';
	}
	return socket.request.headers.origin + path;
}

function can_subscribe_doc(args) {
	if (!args) return;
	if (!args.doctype || !args.docname) return;
	request.get(get_url(args.socket, '/api/method/frappe.realtime.can_subscribe_doc'))
		.type('form')
		.query({
			sid: args.socket.sid,
			doctype: args.doctype,
			docname: args.docname
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

<<<<<<< HEAD
=======
function can_subscribe_list(args) {
	if (!args) return;
	if (!args.doctype) return;
	request
		.get(get_url(args.socket, "/api/method/frappe.realtime.can_subscribe_list"))
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
				args?.callback(err, res);
				return true;
			}
			log("ERROR (can_subscribe_list): ", err, res);
		});
}
>>>>>>> 9931c3af04 (refactor(socketio)!: list_update)

function send_users(args, action) {
	if (!(args && args.doctype && args.docname)) {
		return;
	}

	const open_doc_room = get_open_doc_room(args.socket, args.doctype, args.docname);

	const room = action == 'view' ? open_doc_room: get_typing_room(args.socket, args.doctype, args.docname);

	const socketio_room = io.sockets.adapter.rooms[room] || {};
	// for compatibility with both v1.3.7 and 1.4.4
	const clients_dict = ('sockets' in socketio_room) ? socketio_room.sockets : socketio_room;

	// socket ids connected to this room
	const clients = Object.keys(clients_dict || {});

	let users = [];
	for (let i in io.sockets.sockets) {
		const s = io.sockets.sockets[i];
		if (clients.indexOf(s.id) !== -1) {
			// this socket is connected to the room
			users.push(s.user);
		}
	}

	const emit_event = action == 'view' ? 'doc_viewers' : 'doc_typers';

	// notify
	io.to(open_doc_room).emit(emit_event, {
		doctype: args.doctype,
		docname: args.docname,
		users: Array.from(new Set(users))
	});
}
