import { io } from "socket.io-client";

// Frappe's socketio process authenticates the site cookie and namespaces by site name.
// Behind a web server it shares the page's origin; in development it has its own port.
export function connectSocket({ site_name, socketio_port }) {
	const { protocol, hostname, port } = window.location;
	const site = site_name || hostname;
	const origin = port ? `${protocol}//${hostname}:${socketio_port}` : `${protocol}//${hostname}`;
	return io(`${origin}/${site}`, { withCredentials: true });
}
