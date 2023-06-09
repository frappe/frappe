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

async function get_redis_subscriber(kind = "redis_socketio", options = {}) {
	const conf = get_conf();
	const connStr = conf[kind] || conf.redis_async_broker_port;
	let client;
	// TODO: revise after https://github.com/redis/node-redis/issues/2530
	// is solved for a more elegant implementation
	if (connStr.startsWith("unix://")) {
		client = redis.createClient({
			socket: { path: connStr.replace("unix://", "") },
			...options,
		});
	} else {
		client = redis.createClient({ url: connStr, ...options });
	}
	await client.connect();
	return client;
}

module.exports = {
	get_conf,
	get_redis_subscriber,
};
