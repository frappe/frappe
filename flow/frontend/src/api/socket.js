import { io } from "socket.io-client";

const ASK_AGAIN_AFTER = 3000;

// Frappe's socketio process authenticates the site cookie and namespaces by site name.
// Behind a web server it shares the page's origin; in development it has its own port.
export function connectSocket({ site_name, socketio_port }) {
	const { protocol, hostname, port } = window.location;
	const site = site_name || hostname;
	const origin = port ? `${protocol}//${hostname}:${socketio_port}` : `${protocol}//${hostname}`;
	return askingAgain(io(`${origin}/${site}`, { withCredentials: true }));
}

// The relay refuses a socket while the web server cannot say whose it is, as during a
// restart, and socket.io stops trying once refused. So it asks again, until the page
// disconnects it.
export function askingAgain(socket) {
	let timer = null;
	socket.on("connect_error", () => {
		if (socket.active) return; // not refused: socket.io is still trying
		clearTimeout(timer);
		timer = setTimeout(() => socket.connect(), ASK_AGAIN_AFTER);
	});
	const disconnect = socket.disconnect.bind(socket);
	socket.disconnect = () => {
		clearTimeout(timer);
		return disconnect();
	};
	return socket;
}
