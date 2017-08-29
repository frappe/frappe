const path = require('path');
const fs = require('fs');

module.exports = {

	get_apps() {
		const dirs = fs.readdirSync('apps');
		return dirs.filter(dir => {
			const app_path = path.resolve('apps', dir);
			return fs.lstatSync(app_path).isDirectory &&
				fs.existsSync(path.resolve(app_path, 'setup.py'));
		});
	}

}