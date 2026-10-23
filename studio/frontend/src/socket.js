import { io } from "socket.io-client"
import { socketio_port } from "../../../../../sites/common_site_config.json"

let socket = null
export function initSocket() {
	let { protocol, hostname, port } = window.location
	let host = port ? `${hostname}:${socketio_port}` : hostname
	let url = `${protocol}//${host}/${window.site_name}`

	socket = io(url, {
		withCredentials: true,
		reconnectionAttempts: 5,
	})
	return socket
}

export function useSocket() {
	return socket
}
