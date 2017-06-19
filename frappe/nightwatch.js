const fs = require('fs');

const ci_mode = get_cli_arg('env') === 'ci_server';
const site_name = get_cli_arg('site');
let app_name = get_cli_arg('app');

if(!app_name) {
	console.log('Please specify app to run tests');
	return;
}

if(!ci_mode && !site_name) {
	console.log('Please specify site to run tests');
	return;
}

// site url
let site_url;
if(site_name) {
	site_url = 'http://' + site_name + ':' + get_port();
}

// multiple apps
if(app_name.includes(',')) {
	app_name = app_name.split(',');
} else {
	app_name = [app_name];
}

let test_folders = [];
let page_objects = [];
for(const app of app_name) {
	const test_folder = `apps/${app}/${app}/tests/ui`;
	const page_object = test_folder + '/page_objects';

	if(!fs.existsSync(test_folder)) {
		console.log(`No test folder found for "${app}"`);
		continue;
	}
	test_folders.push(test_folder);

	if(fs.existsSync(page_object)) {
		page_objects.push();
	}
}

const config = {
	"src_folders": test_folders,
	"globals_path" : 'apps/frappe/frappe/nightwatch.global.js',
	"page_objects_path": page_objects,
	"selenium": {
		"start_process": false
	},
	"test_settings": {
		"default": {
			"launch_url": site_url,
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