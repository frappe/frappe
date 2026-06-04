const { Server } = require("socket.io");
const http = require("node:http");

const fs = require("fs");
const path = require("path");
const { get_conf, get_redis_subscriber } = require("../node_utils");
const conf = get_conf();

const server = http.createServer((req, res) => {
	if (conf.in_memory && req.method === "POST" && req.url === "/_internal/publish_event") {
		let body = "";
		req.on("data", (chunk) => {
			body += chunk.toString();
		});
		req.on("end", () => {
			try {
				let message = JSON.parse(body);
				let namespace = "/" + message.namespace;
				if (message.room) {
					io.of(namespace).to(message.room).emit(message.event, message.message);
				} else {
					realtime.emit(message.event, message.message);
				}
				res.writeHead(200);
				res.end("OK");
			} catch (e) {
				console.error("Webhook parse error", e);
				res.writeHead(400);
				res.end("Bad Request");
			}
		});
		return;
	}
});

let io = new Server(server, {
	cors: {
		// Should be fine since we are ensuring whether hostname and origin are same before adding setting listeners for s socket
		origin: true,
		credentials: true,
	},
	cleanupEmptyChildNamespaces: true,
});

// Multitenancy implementation.
// allow arbitrary sitename as namespaces
// namespaces get validated during authentication.
const realtime = io.of(/^\/.*$/);

// load and register middlewares
const authenticate = require("./middlewares/authenticate");
realtime.use(authenticate);
// =======================

function on_connection(socket) {
	socket.installed_apps.forEach((app) => {
		let app_handler = get_app_handlers(app);
		try {
			app_handler && app_handler(socket);
		} catch (err) {
			console.warn(`failed to setup event handlers from ${app}`);
			console.warn(err);
		}
	});

	// ESBUild "open in editor" on error
	socket.on("open_in_editor", async (data) => {
		if (conf.in_memory) return;
		await subscriber.connect();
		subscriber.publish("open_in_editor", JSON.stringify(data));
	});
}

const _app_handlers = {};
function get_app_handlers(app) {
	if (app in _app_handlers) {
		return _app_handlers[app];
	}

	let file = `../../${app}/realtime/handlers.js`;
	let abs_path = path.resolve(__dirname, file);
	let handler = null;
	if (fs.existsSync(abs_path)) {
		try {
			handler = require(file);
		} catch (err) {
			console.warn(`failed to load event handlers from ${abs_path}`);
			console.warn(err);
		}
	}
	_app_handlers[app] = handler;
	return handler;
}

realtime.on("connection", on_connection);
// =======================

// Consume events sent from python via redis pub-sub channel.
let subscriber;
if (!conf.in_memory) {
	subscriber = get_redis_subscriber();

	(async () => {
		await subscriber.connect();
		subscriber.subscribe("events", (message) => {
			message = JSON.parse(message);
			let namespace = "/" + message.namespace;
			if (message.room) {
				io.of(namespace).to(message.room).emit(message.event, message.message);
			} else {
				// publish to ALL sites only used for things like build event.
				realtime.emit(message.event, message.message);
			}
		});
	})();
} else {
	console.log("Realtime service running in in_memory mode (HTTP Webhook)");
}
// =======================

let uds = conf.socketio_uds;
let port = conf.socketio_port;
server.listen(uds || port, () => {
	if (uds) {
		console.log(`Realtime service listening on UDS: ${uds}`);
	} else {
		console.log(`Realtime service listening on: ws://0.0.0.0:${port}`);
	}
});
