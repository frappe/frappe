/* globals describe it */
var frappe = require('../frappe');
var assert = require('assert');

describe('frappe', function () {
	describe('#get_apps', function () {
		it('should return all apps', function () {
			const apps = frappe.get_apps();
			assert.ok(apps.includes('frappe'));
			assert.ok(!apps.includes('.DS_Store'));
		});
	});
});

