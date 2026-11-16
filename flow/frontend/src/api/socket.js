import { io } from "socket.io-client";

// Frappe's socketio process authenticates the site cookie and namespaces by site name.
// Behind a web server it shares the page's origin; in development it has its own port. A page
// that gives no port (desk v2 renders no Desk boot) is taken to share its origin.
export function connectSocket({ site_name, socketio_port }) {
	const { protocol, hostname, port, origin: pageOrigin } = window.location;
	const site = site_name || hostname;
	const origin = port && socketio_port ? `${protocol}//${hostname}:${socketio_port}` : pageOrigin;
	return io(`${origin}/${site}`, { withCredentials: true });
}
