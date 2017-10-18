import assert from 'assert';
import frappe from '../src/frappe.js';

describe('Meta', () => {
	it('should get init from json file', (done) => {
		frappe.get_meta('ToDo').then(
			todo => {
				assert.equal(todo.issingle, 0);
				done();
			});
	});
});