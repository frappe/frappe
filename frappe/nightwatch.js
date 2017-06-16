const fs = require('fs');

const ci_mode = get_cli_arg('env') === 'ci_server';
const site_name = get_cli_arg('site');

const app_name = get_cli_arg('app');
if(!app_name) {
	console.log('Please specify app to run tests');
	return;
}

if(!ci_mode && !site_name) {
	console.log('Please specify site to run tests');
	return;
}

let site_url;
if(site_name) {
	site_url = 'http://' + site_name + ':' + get_port();
}


const config = {
	"src_folders": [
		`apps/${app_name}/${app_name}/tests/ui`
	],
	"globals_path" : 'apps/frappe/frappe/nightwatch.global.js',
	"selenium": {
		"start_process": false
	},
	"test_settings": {
		"default": {
			"launch_url": site_url || 'http://localhost:8000',
			"selenium_port": 9515,
			"selenium_host": "127.0.0.1",
			"default_path_prefix": "",
			"silent": true,
			// "screenshots": {
			// 	"enabled": true,
			// 	"path": SCREENSHOT_PATH
			// },
			"globals": {
				"waitForConditionTimeout": 15000
			},
			"desiredCapabilities": {
				"browserName": "chrome",
				"chromeOptions": {
					"args": ["--no-sandbox", "--start-maximized"]
				},
				"javascriptEnabled": true,
				"acceptSslCerts": true
			}
		},
		"ci_server": {
			"launch_url": 'http://localhost:8000'
		}
	}
}
module.exports = config;

function get_cli_arg(key) {
	var args = process.argv;
	var i = args.indexOf('--' + key);
	if(i === -1) {
		return null;
	}
	return args[i + 1];
}

function get_port() {
	var bench_config = JSON.parse(fs.readFileSync('sites/common_site_config.json'));
	return bench_config.webserver_port;
}