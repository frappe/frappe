/* globals describe it */
var boot = require('../boot');
var assert = require('assert');

describe('Boot', function () {
	describe('#get_desktop_icons', function () {
		it('should return desktop icons from config/desktop.json', function () {
			const icons = boot.get_desktop_icons();
			const module_names = icons.map(i => i.module_name);
			assert.ok(module_names.includes('Setup'));
		});
	});
});
