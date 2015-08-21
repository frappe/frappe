var app = require('express')();
var http = require('http').Server(app);
var io = require('socket.io')(http);
var cookie = require('cookie')
var fs = require('fs');

var redis = require("redis")
var subscriber = redis.createClient(12311);
var r = redis.createClient(12311);

var request = require('superagent')
var default_site;



if(fs.existsSync('sites/currentsite.txt')) {
	default_site = fs.readFileSync('sites/currentsite.txt').toString().trim();
}

app.get('/', function(req, res){
  res.sendfile('index.html');
});

io.on('connection', function(socket){
	if (get_hostname(socket.request.headers.host) != get_hostname(socket.request.headers.origin)) {
		return;
	}
	var sid = cookie.parse(socket.request.headers.cookie).sid
	if(!sid) {
		return;
	}
	request.post(get_url(socket, '/api/method/frappe.async.get_user_info'))
		.type('form')
		.send({
			sid: sid
		})
		.end(function(err, res) {
			if(err) {
				console.log(err);
				return;
			}
			if(res.status == 200) {
				var room = get_user_room(socket, res.body.message.user);
				// console.log('joining', room);
				socket.join(room);
				socket.join(get_site_room(socket));
			}
		})
	socket.on('task_subscribe', function(task_id) {
		var room = 'task:' + task_id;
		socket.join(room);
	})
	socket.on('progress_subscribe', function(task_id) {
		var room = 'task_progress:' + task_id;
		socket.join(room);
		send_existing_lines(task_id, socket);
	})
	socket.on('doc_subscribe', function(doctype, docname) {
		// console.log('trying to subscribe', doctype, docname)
		request.post(get_url(socket, '/api/method/frappe.async.can_subscribe_doc'))
			.type('form')
			.send({
				sid: sid,
				doctype: doctype,
				docname: docname
			})
			.end(function(err, res) {
				if(err) console.log(err);
				if(res.status == 200) {
					var room = get_doc_room(socket, doctype, docname);
					// console.log('joining', room)
					socket.join(room);
				}
			})
	});
	socket.on('doc_unsubscribe', function(doctype, docname) {
		var room = get_doc_room(socket, doctype, docname);
		socket.leave(room);
	});
});

function send_existing_lines(task_id, socket) {
	r.hgetall('task_log:' + task_id, function(err, lines) {
		socket.emit('task_progress', {
			"task_id": task_id,
			"message": {
				"lines": lines
			}
		})
	})
}


subscriber.on("message", function(channel, message) {
	message = JSON.parse(message);
	io.to(message.room).emit(message.event, message.message);
	// console.log(message.room, message.event, message.message)
});

subscriber.subscribe("events");

http.listen(3000, function(){
  console.log('listening on *:3000');
});

function get_doc_room(socket, doctype, docname) {
	return get_site_name(socket) + ':doc:'+ doctype + '/' + docname;
}

function get_user_room(socket, user) {
	return get_site_name(socket) + ':user:' + user;
}

function get_site_room(socket) {
	return get_site_name(socket) + ':all';
}

function get_site_name(socket) {
	if (default_site) {
		return default_site;
	}
	else if (socket.request.headers['x-frappe-site-name']) {
		return get_hostname(socket.request.headers['x-frappe-site-name']);
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
	return ( url.match(/:/g) ) ? url.slice( 0, url.indexOf(":") ) : url
}

function get_url(socket, path) {
	if (!path) {
		path = '';
	}
	return socket.request.headers.origin + path;
}
