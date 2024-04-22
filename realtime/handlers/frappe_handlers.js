const { frappe_request } = require("../utils");
const log = console.log;

const WEBSITE_ROOM = "website";
const SITE_ROOM = "all";

function frappe_handlers(realtime, socket) {
	socket.join(user_room(socket.user));
	socket.join(WEBSITE_ROOM);

	if (socket.user_type == "System User") {
		socket.join(SITE_ROOM);
	}

	socket.on("ping", () => {
		socket.emit("pong");
	});

	socket.on("doctype_subscribe", function (doctype) {
		can_subscribe_doctype({
			socket,
			doctype,
			callback: () => {
				socket.join(doctype_room(doctype));
			},
		});
	});

	socket.on("doctype_unsubscribe", function (doctype) {
		socket.leave(doctype_room(doctype));
	});

	socket.on("task_subscribe", function (task_id) {
		const room = task_room(task_id);
		socket.join(room);
	});

	socket.on("task_unsubscribe", function (task_id) {
		const room = task_room(task_id);
		socket.leave(room);
	});

	socket.on("progress_subscribe", function (task_id) {
		const room = task_room(task_id);
		socket.join(room);
	});

	socket.on("doc_subscribe", function (doctype, docname) {
		can_subscribe_doc({
			socket,
			doctype,
			docname,
			callback: () => {
				let room = doc_room(doctype, docname);
				socket.join(room);
			},
		});
	});

	socket.on("doc_unsubscribe", function (doctype, docname) {
		let room = doc_room(doctype, docname);
		socket.leave(room);
	});

	socket.on("doc_open", function (doctype, docname) {
		can_subscribe_doc({
			socket,
			doctype,
			docname,
			callback: () => {
				let room = open_doc_room(doctype, docname);
				socket.join(room);
				if (!socket.subscribed_documents) socket.subscribed_documents = [];
				socket.subscribed_documents.push([doctype, docname]);

				// show who is currently viewing the form
				notify_subscribed_doc_users({
					socket: socket,
					doctype: doctype,
					docname: docname,
				});
			},
		});
	});

	socket.on("doc_close", function (doctype, docname) {
		// remove this user from the list of 'who is currently viewing the form'
		let room = open_doc_room(doctype, docname);
		socket.leave(room);

		if (socket.subscribed_documents) {
			socket.subscribed_documents = socket.subscribed_documents.filter(([dt, dn]) => {
				!(dt == doctype && dn == docname);
			});
		}

		notify_subscribed_doc_users({
			socket: socket,
			doctype: doctype,
			docname: docname,
		});
	});

	socket.on("disconnect", () => {
		notify_disconnected_documents(socket);
	});
}

function notify_disconnected_documents(socket) {
	if (socket.subscribed_documents) {
		socket.subscribed_documents.forEach(([doctype, docname]) => {
			notify_subscribed_doc_users({ socket, doctype, docname });
		});
	}
}

function can_subscribe_doctype(args) {
	if (!args) return;
	if (!args.doctype) return;
	frappe_request("/api/method/frappe.realtime.can_subscribe_doctype", args.socket)
		.type("form")
		.query({
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

function notify_subscribed_doc_users(args) {
	if (!(args && args.doctype && args.docname)) {
		return;
	}
	const socket = args.socket;
	const room = open_doc_room(args.doctype, args.docname);

	const clients = Array.from(socket.nsp.adapter.rooms.get(room) || []);

	let users = [];

	socket.nsp.sockets.forEach((sock) => {
		if (clients.includes(sock.id)) {
			users.push(sock.user);
		}
	});

	// dont send update to self. meaningless.
	if (users.length == 1 && users[0] == args.socket.user) return;

	// notify
	socket.nsp.to(room).emit("doc_viewers", {
		doctype: args.doctype,
		docname: args.docname,
		users: Array.from(new Set(users)),
	});
}

function can_subscribe_doc(args) {
	if (!args) return;
	if (!args.doctype || !args.docname) return;
	frappe_request("/api/method/frappe.realtime.can_subscribe_doc", args.socket)
		.type("form")
		.query({
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

const doc_room = (doctype, docname) => "doc:" + doctype + "/" + docname;
const open_doc_room = (doctype, docname) => "open_doc:" + doctype + "/" + docname;
const user_room = (user) => "user:" + user;
const doctype_room = (doctype) => "doctype:" + doctype;
const task_room = (task_id) => "task_progress:" + task_id;

module.exports = frappe_handlers;
