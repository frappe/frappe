const pify = require('pify');
const importCwd = require('import-cwd');
const path = require('path');

const getFileName = filepath => path.basename(filepath);

function loadModule(moduleId) {
	// Trying to load module normally (relative to plugin directory)
	try {
		return require(moduleId);
	} catch (_) {
		// Ignore error
	}

	// Then, trying to load it relative to CWD
	return importCwd.silent(moduleId);
}

module.exports = {
	name: 'less',
	test: /\.less$/,
	async process({
		code
	}) {
		const less = loadModule('less');
		if (!less) {
			throw new Error('You need to install "less" packages in order to process Less files');
		}

		let {
			css,
			map,
			imports
		} = await pify(less.render.bind(less))(code, {
			...this.options,
			sourceMap: this.sourceMap && { outputSourceFiles: true },
			filename: this.id
		});

		for (const dep of imports) {
			this.dependencies.add(dep);
		}

		if (map) {
			map = JSON.parse(map);
			map.sources = map.sources.map(source => getFileName(source));
		}

		return {
			code: css,
			map
		};
	}
};