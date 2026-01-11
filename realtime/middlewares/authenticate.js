const cookie = require("cookie");
const request = require("superagent");
const { get_url } = require("../utils");

const { get_conf } = require("../../node_utils");
const conf = get_conf();

function authenticate_with_frappe(socket, next) {
    let namespace = socket.nsp.name;
    namespace = namespace.slice(1, namespace.length); // remove leading `/`

    if (namespace != get_site_name(socket)) {
        next(new Error("Invalid namespace"));
        return;
    }

    // DEVELOPER MODE: Relaxed origin validation for reverse proxy support
    if (conf.developer_mode) {
        const host = get_hostname(socket.request.headers.host);
        const origin = get_hostname(socket.request.headers.origin);

        // Compare hostnames only (ignore ports/protocols)
        if (origin && host !== origin) {
            console.warn("[socketio dev] Origin mismatch:", {
                host: socket.request.headers.host,
                origin: socket.request.headers.origin,
                x_forwarded_host: socket.request.headers["x-forwarded-host"],
                x_forwarded_proto: socket.request.headers["x-forwarded-proto"],
            });

            next(new Error("Invalid origin"));
            return;
        }
    } else {
        // PRODUCTION MODE: Original strict validation
        if (get_hostname(socket.request.headers.host) != get_hostname(socket.request.headers.origin)) {
            next(new Error("Invalid origin"));
            return;
        }
    }

    if (!socket.request.headers.cookie && !socket.request.headers.authorization) {
        next(new Error("No cookie or authorization header transmitted."));
        return;
    }

    let cookies = cookie.parse(socket.request.headers.cookie || "");
    let authorization_header = socket.request.headers.authorization;

    if (!cookies.sid && !authorization_header) {
        next(new Error("No authentication method used. Use cookie or authorization header."));
        return;
    }

    let auth_req = request.get(get_url(socket, "/api/method/frappe.realtime.get_user_info"));
    if (authorization_header) {
        auth_req = auth_req.set("Authorization", authorization_header);
    } else if (cookies.sid) {
        auth_req = auth_req.query({ sid: cookies.sid });
    }

    auth_req
        .type("form")
        .then((res) => {
            socket.user = res.body.message.user;
            socket.user_type = res.body.message.user_type;
            socket.sid = cookies.sid;
            socket.authorization_header = authorization_header;
            next();
        })
        .catch((e) => {
            next(new Error(`Unauthorized: ${e}`));
        });
}

function get_site_name(socket) {
    if (socket.site_name) {
        return socket.site_name;
    } else if (socket.request.headers["x-frappe-site-name"]) {
        socket.site_name = get_hostname(socket.request.headers["x-frappe-site-name"]);
    } else if (
        conf.default_site &&
        ["localhost", "127.0.0.1"].indexOf(get_hostname(socket.request.headers.host)) !== -1
    ) {
        socket.site_name = conf.default_site;
    } else if (socket.request.headers.origin) {
        socket.site_name = get_hostname(socket.request.headers.origin);
    } else {
        socket.site_name = get_hostname(socket.request.headers.host);
    }
    return socket.site_name;
}

function get_hostname(url) {
    if (!url) return undefined;
    if (url.indexOf("://") > -1) {
        url = url.split("/")[2];
    }
    return url.match(/:/g) ? url.slice(0, url.indexOf(":")) : url;
}

module.exports = authenticate_with_frappe;