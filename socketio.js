var app = require('express')();
var server = require('http').Server(app);
var io = require('socket.io')(server);
var cookie = require('cookie');
var fs = require('fs');
var path = require('path');
var request = require('superagent');
var { get_conf, get_redis_subscriber } = require('./node_utils');

const log = console.log; // eslint-disable-line

var conf = get_conf();
var files_struct = {
	name: null,
	type: null,
	size: 0,
	data: [],
	slice: 0,
	site_name: null,
	is_private: 0
};

var subscriber = get_redis_subscriber();

// serve socketio
server.listen(conf.socketio_port, function () {
	log('listening on *:', conf.socketio_port); //eslint-disable-line
});

// on socket connection
io.on('connection', function (socket) {
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
	socket.files = {};

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

	socket.on('disconnect', function () {
		delete socket.files;
	});

	socket.on('task_subscribe', function (task_id) {
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

	socket.on('doc_subscribe', function (doctype, docname) {
		can_subscribe_doc({
			socket,
			sid,
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
		// show who is currently viewing the form
		can_subscribe_doc({
			socket: socket,
			sid: sid,
			doctype: doctype,
			docname: docname,
			callback: () => {
				var room = get_open_doc_room(socket, doctype, docname);
				socket.join(room);

				send_viewers({
					socket: socket,
					doctype: doctype,
					docname: docname,
				});
			}
		});
	});

	socket.on('doc_close', function (doctype, docname) {
		// remove this user from the list of 'who is currently viewing the form'
		var room = get_open_doc_room(socket, doctype, docname);
		socket.leave(room);
		send_viewers({
			socket: socket,
			doctype: doctype,
			docname: docname,
		});
	});

	socket.on('upload-accept-slice', (data) => {
		try {
			if (!socket.files[data.name]) {
				socket.files[data.name] = Object.assign({}, files_struct, data);
				socket.files[data.name].data = [];
			}

			//convert the ArrayBuffer to Buffer
			data.data = new Buffer(new Uint8Array(data.data));
			//save the data
			socket.files[data.name].data.push(data.data);
			socket.files[data.name].slice++;

			if (socket.files[data.name].slice * 24576 >= socket.files[data.name].size) {
				// do something with the data
				var fileBuffer = Buffer.concat(socket.files[data.name].data);

				const file_url = path.join((socket.files[data.name].is_private ? 'private' : 'public'),
					'files', data.name);
				const file_path = path.join('sites', get_site_name(socket), file_url);

				fs.writeFile(file_path, fileBuffer, (err) => {
					delete socket.files[data.name];
					if (err) return socket.emit('upload error');
					socket.emit('upload-end', {
						file_url: '/' + file_url
					});
				});
			} else {
				socket.emit('upload-request-slice', {
					currentSlice: socket.files[data.name].slice
				});
			}
		} catch (e) {
			log(e);
			socket.emit('upload-error', {
				error: e.message
			});
		}
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

function get_user_room(socket, user) {
	return get_site_name(socket) + ':user:' + user;
}

function get_site_room(socket) {
	return get_site_name(socket) + ':all';
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
	if (socket.request.headers['x-frappe-site-name']) {
		return get_hostname(socket.request.headers['x-frappe-site-name']);
	} else if (['localhost', '127.0.0.1'].indexOf(socket.request.headers.host) !== -1 &&
		conf.default_site) {
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
			sid: args.sid,
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

function send_viewers(args) {
	// send to doc room, 'users currently viewing this document'
	if (!(args && args.doctype && args.docname)) {
		return;
	}

	// open doc room
	var room = get_open_doc_room(args.socket, args.doctype, args.docname);

	var socketio_room = io.sockets.adapter.rooms[room] || {};

	// for compatibility with both v1.3.7 and 1.4.4
	var clients_dict = ("sockets" in socketio_room) ? socketio_room.sockets : socketio_room;

	// socket ids connected to this room
	var clients = Object.keys(clients_dict || {});

	var viewers = [];
	for (var i in io.sockets.sockets) {
		var s = io.sockets.sockets[i];
		if (clients.indexOf(s.id) !== -1) {
			// this socket is connected to the room
			viewers.push(s.user);
		}
	}

	// notify
	io.to(room).emit("doc_viewers", {
		doctype: args.doctype,
		docname: args.docname,
		viewers: viewers
	});
}