var app = require('express')();
var http = require('http').Server(app);
var io = require('socket.io')(http);
var cookie = require('cookie')
var fs = require('fs');
var redis = require("redis");
var request = require('superagent');

var conf = get_conf();
var subscriber = redis.createClient(conf.redis_socketio || conf.redis_async_broker_port);

// serve socketio
http.listen(conf.socketio_port, function () {
	console.log('listening on *:', conf.socketio_port);
});

// test route
app.get('/', function (req, res) {
	res.sendfile('index.html');
});

// on socket connection
io.on('connection', function (socket) {
	if (get_hostname(socket.request.headers.host) != get_hostname(socket.request.headers.origin)) {
		return;
	}

	// console.log("connection!");
	var sid = cookie.parse(socket.request.headers.cookie).sid
	if (!sid) {
		return;
	}

	socket.user = cookie.parse(socket.request.headers.cookie).user_id;
	var _url = get_url(socket, '/api/method/frappe.async.get_user_info');
	// console.log("firing get_user_info");
	request.get(_url)
		.type('form')
		.query({
			sid: sid
		})
		.end(function (err, res) {
			if (err) {
				console.log(err);
				return;
			}
			if (res.status == 200) {
				var room = get_user_room(socket, res.body.message.user);
				socket.join(room);
				socket.join(get_site_room(socket));
			}
		});

	socket.on('task_subscribe', function (task_id) {
		var room = get_task_room(socket, task_id);
		socket.join(room);
	});

	socket.on('join_room', function (room_name) {
		socket.join(room_name);
		socket.emit('joined_room', 'joined_room');
	});

	socket.on('leave_room', function (room_name) {
		socket.leave(room_name)
		socket.emit('left_room', 'left_room');
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
		// console.log('trying to subscribe', doctype, docname)
		can_subscribe_doc({
			socket: socket,
			sid: sid,
			doctype: doctype,
			docname: docname,
			callback: function (err, res) {
				var room = get_doc_room(socket, doctype, docname);
				// console.log('joining', room)
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
			callback: function (err, res) {
				var room = get_open_doc_room(socket, doctype, docname);
				// console.log('joining', room)
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

	// socket.on('disconnect', function (arguments) {
	// 	console.log("user disconnected", arguments);
	// });
});


subscriber.on("message", function (channel, message) {
	message = JSON.parse(message);
	console.log(message.room);
	io.to(message.room).emit(message.event, message.message);
});

subscriber.subscribe("events");

function send_existing_lines(task_id, socket) {
	var room = get_task_room(socket, task_id);
	subscriber.hgetall('task_log:' + task_id, function (err, lines) {
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

function get_site_name(socket) {
	if (socket.request.headers['x-frappe-site-name']) {
		return get_hostname(socket.request.headers['x-frappe-site-name']);
	}
	else if (['localhost', '127.0.0.1'].indexOf(socket.request.headers.host) !== -1
		&& conf.default_site) {
		// from currentsite.txt since host is localhost
		return conf.default_site;
	}
	else if (socket.request.headers.origin) {
		return get_hostname(socket.request.headers.origin);
	}
	else {
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
	var _url = socket.request.headers.origin.split(':');
	if (_url.length > 2) {
		return _url[0] + ':' + _url[1] + ':8000' + path;
	}

	return socket.request.headers.origin + path;
}

function can_subscribe_doc(args) {
	if (!args) return;
	request.get(get_url(args.socket, '/api/method/frappe.async.can_subscribe_doc'))
		.type('form')
		.query({
			sid: args.sid,
			doctype: args.doctype,
			docname: args.docname
		})
		.end(function (err, res) {
			if (!res) {
				console.log("No response for doc_subscribe");

			} else if (res.status == 403) {
				return;

			} else if (err) {
				console.log(err);

			} else if (res.status == 200) {
				args.callback(err, res);

			} else {
				console.log("Something went wrong", err, res);
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

function get_conf() {
	// defaults
	var conf = {
		redis_async_broker_port: 12311,
		socketio_port: 3000
	};

	var read_config = function (path) {
		if (fs.existsSync(path)) {
			var bench_config = JSON.parse(fs.readFileSync(path));
			for (var key in bench_config) {
				if (bench_config[key]) {
					conf[key] = bench_config[key];
				}
			}
		}
	}

	// get ports from bench/config.json
	read_config('config.json');
	read_config('sites/common_site_config.json');

	// detect current site
	if (fs.existsSync('sites/currentsite.txt')) {
		conf.default_site = fs.readFileSync('sites/currentsite.txt').toString().trim();
	}

	return conf;
}


