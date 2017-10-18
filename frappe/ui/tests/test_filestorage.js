import assert from 'assert';
import frappe from '../src/frappe.js';

describe('FileStorage', () => {
	it('should get todo json', (done) => {
		frappe.storage.get('DocType', 'ToDo')
			.then(todo => {
				assert.equal(todo.issingle, 0);
				done();
			});
	});
});