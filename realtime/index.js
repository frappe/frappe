const { Server } = require("socket.io");
const http = require("node:http");

const fs = require("fs");
const path = require("path");
const { get_conf, get_redis_subscriber } = require("../node_utils");
const conf = get_conf();

const server = http.createServer();

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

async function on_connection(socket) {
	for (const app of socket.installed_apps) {
		try {
			let app_handler = await get_app_handlers(app);
			app_handler && app_handler(socket);
		} catch (err) {
			console.warn(`failed to setup event handlers from ${app}`);
			console.warn(err);
		}
	}

	// ESBUild "open in editor" on error
	socket.on("open_in_editor", async (data) => {
		await subscriber.connect();
		subscriber.publish("open_in_editor", JSON.stringify(data));
	});
}

const _app_handlers = {};
async function get_app_handlers(app) {
	if (app in _app_handlers) {
		return _app_handlers[app];
	}

	let file = `../../${app}/realtime/handlers.js`;
	let abs_path = path.resolve(__dirname, file);
	let handler = null;
	if (fs.existsSync(abs_path)) {
		try {
			// Try dynamic import first (for ES modules)
			let file_url = `file://${abs_path}`;
			handler = await import(file_url).then((m) => m.default);
		} catch (err) {
			// Fall back to require (for CommonJS)
			try {
				handler = require(file);
			} catch (requireErr) {
				console.warn(err);
			}
		}
	}
	_app_handlers[app] = handler;
	return handler;
}

realtime.on("connection", on_connection);
// =======================

// Consume events sent from python via redis pub-sub channel.
const subscriber = get_redis_subscriber();

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
