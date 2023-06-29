const cookie = require("cookie");
const request = require("superagent");
const { get_hostname, get_url } = require("../utils");

function authenticate_with_frappe(socket, next) {
	if (get_hostname(socket.request.headers.host) != get_hostname(socket.request.headers.origin)) {
		next(new Error("Invalid origin"));
		return;
	}

	if (!socket.request.headers.cookie) {
		next(new Error("No cookie transmitted."));
		return;
	}

	let cookies = cookie.parse(socket.request.headers.cookie);

	if (!cookies.sid) {
		next(new Error("No sid transmitted."));
		return;
	}

	request
		.get(get_url(socket, "/api/method/frappe.realtime.get_user_info"))
		.type("form")
		.query({
			sid: cookies.sid,
		})
		.then((res) => {
			socket.user = res.body.message.user;
			socket.user_type = res.body.message.user_type;
			socket.sid = cookies.sid;
			socket.subscribed_documents = [];
			next();
		})
		.catch((e) => {
			next(new Error(`Unauthorized: ${e}`));
		});
}

module.exports = authenticate_with_frappe;
