const fs = require("fs");
const path = require("path");
<<<<<<< HEAD
const redis = require("redis");
const bench_path = path.resolve(__dirname, "..", "..");
=======
const redis = require("@redis/client");
let bench_path;
if (process.env.FRAPPE_BENCH_ROOT) {
	bench_path = process.env.FRAPPE_BENCH_ROOT;
} else {
	bench_path = path.resolve(__dirname, "..", "..");
}
>>>>>>> 93bbe615ba (chore: use env variables in esbuilds)

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
	const host = conf[kind] || conf.redis_async_broker_port;
	return redis.createClient({ url: host, ...options });
}

module.exports = {
	get_conf,
	get_redis_subscriber,
};
