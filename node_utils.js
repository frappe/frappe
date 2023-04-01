const fs = require("fs");
const path = require("path");
const redis = require("redis");
const bench_path = path.resolve(__dirname, "..", "..");

function get_conf() {
	// defaults
	var conf = {
		redis_async_broker_port: "redis://localhost:12311",
		socketio_port: 3000,
	};

	var read_config = function (file_path) {
		const full_path = path.resolve(bench_path, file_path);

		if (fs.existsSync(full_path)) {
			var bench_config = JSON.parse(fs.readFileSync(full_path));
			for (var key in bench_config) {
				if (bench_config[key]) {
					conf[key] = bench_config[key];
				}
			}
		}
	};

	// get ports from bench/config.json
	read_config("config.json");
	read_config("sites/common_site_config.json");

	// set default site
	if (process.env.FRAPPE_SITE) {
		conf.default_site = process.env.FRAPPE_SITE;
	}
	if (fs.existsSync("sites/currentsite.txt")) {
		conf.default_site = fs.readFileSync("sites/currentsite.txt").toString().trim();
	}

	return conf;
}

function get_redis_subscriber(kind = "redis_socketio", options = {}) {
	const conf = get_conf();
	let redisSock = {
		redis_cache:
			process.env.FRAPPE_REDIS_CACHE_SOCKET || conf[kind] || conf.redis_async_broker_port,
		redis_queue:
			process.env.FRAPPE_REDIS_QUEUE_SOCKET || conf[kind] || conf.redis_async_broker_port,
		redis_socketio:
			process.env.FRAPPE_REDIS_SOCKETIO_SOCKET || conf[kind] || conf.redis_async_broker_port,
	};
	let sockStr = redisSock[kind];
	if (sockStr.startsWith("/")) {
		return redis.createClient({ socket: { path: sockStr }, ...options });
	} else {
		return redis.createClient({ url: sockStr, ...options });
	}
}

module.exports = {
	get_conf,
	get_redis_subscriber,
};
