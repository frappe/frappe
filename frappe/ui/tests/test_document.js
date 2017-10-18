import assert from 'assert';
import Document from '../src/document.js';

describe('Document', () => {
	it('should get a value', () => {
		assert.equal(test_doc().get('subject'), 'test subject');
	});

	it('should set a value', () => {
		let doc = test_doc();
		doc.set('subject', 'test subject 1')
		assert.equal(doc.get('subject'), 'test subject 1');
	});

});

const test_doc = () => {
	return new Document({
		doctype: 'ToDo',
		subject: 'test subject',
		description: 'testing...'
	});
}