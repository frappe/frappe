const fs = require("fs");
const path = require("path");
const redis = require("@redis/client");
let bench_path;
if (process.env.nts_BENCH_ROOT) {
	bench_path = process.env.nts_BENCH_ROOT;
} else {
	bench_path = path.resolve(__dirname, "..", "..");
}

const dns = require("dns");

// Since node17, node resolves to ipv6 unless system is configured otherwise.
// In nts context using ipv4 - 127.0.0.1 is fine.
dns.setDefaultResultOrder("ipv4first");

function get_conf() {
	// defaults
	var conf = {
		socketio_port: 9000,
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

	// set overrides from environment
	if (process.env.nts_SITE) {
		conf.default_site = process.env.nts_SITE;
	}
	if (process.env.nts_REDIS_CACHE) {
		conf.redis_cache = process.env.nts_REDIS_CACHE;
	}
	if (process.env.nts_REDIS_QUEUE) {
		conf.redis_queue = process.env.nts_REDIS_QUEUE;
	}
	if (process.env.nts_SOCKETIO_PORT) {
		conf.socketio_port = process.env.nts_SOCKETIO_PORT;
	}
	if (process.env.nts_SOCKETIO_UDS) {
		conf.socketio_uds = process.env.nts_SOCKETIO_UDS;
	}
	return conf;
}

function get_redis_subscriber(kind = "redis_queue", options = {}) {
	const conf = get_conf();
	const connStr = conf[kind];
	let client;
	// TODO: revise after https://github.com/redis/node-redis/issues/2530
	// is solved for a more elegant implementation
	if (connStr && connStr.startsWith("unix://")) {
		client = redis.createClient({
			socket: { path: connStr.replace("unix://", "") },
			...options,
		});
	} else {
		client = redis.createClient({ url: connStr, ...options });
	}
	return client;
}

module.exports = {
	get_conf,
	get_redis_subscriber,
};
