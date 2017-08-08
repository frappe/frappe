# UI Testing with Frappé API

You can either write integration tests, or directly write tests in Javascript using [QUnit](http://api.qunitjs.com/)

QUnit helps you write UI tests using the UQuit framework and native frappe API. As you might have guessed, this is a much faster way of writing tests.

### Test Runner

To write QUnit based tests, add your tests in the `tests/ui` folder of your application. Your test files must begin with `test_` and end with `.js` extension.

To run your files, you can use the **Test Runner**. The **Test Runner** gives a user interface to load all your QUnit tests and run them in the browser.

In the CI, all QUnit tests are run by the **Test Runner** using `frappe/tests/test_test_runner.py`

<img src="/docs/assets/img/app-development/test-runner.png" class="screenshot">

### Running Tests

To run a Test Runner based test, use the `run-ui-tests` bench command by passing the name of the file you want to run.

	bench run-ui-tests --test frappe/tests/ui/test_list.js

This will pass the filename to `test_test_runner.py` that will load the required JS in the browser and execute the tests

### Debugging Tests

To debug a test, you can open it in the **Test Runner** from your UI and run it manually to see where it is exactly failing.

### Test Sequence

In Frappé UI tests are run in a fixed sequence to ensure dependencies.

The sequence in which the tests will be run will be in `tests/ui/tests.txt`
file.

### Running All UI Tests

To run all UI tests together for your app run

	bench run-ui-tests --app [app_name]

This will run all the files in your `tests/ui` folder one by one.

### Example QUnit Test

Here is the example of the To Do test in QUnit

	QUnit.test("Test quick entry", function(assert) {
		assert.expect(2);
		let done = assert.async();
		let random_text = frappe.utils.get_random(10);

		frappe.run_serially([
			() => frappe.set_route('List', 'ToDo'),
			() => frappe.new_doc('ToDo'),
			() => frappe.quick_entry.dialog.set_value('description', random_text),
			() => frappe.quick_entry.insert(),
			(doc) => {
				assert.ok(doc && !doc.__islocal);
				return frappe.set_route('Form', 'ToDo', doc.name);
			},
			() => assert.ok(cur_frm.doc.description.includes(random_text)),

			// Delete the created ToDo
			() => frappe.tests.click_page_head_item('Menu'),
			() => frappe.tests.click_dropdown_item('Delete'),
			() => frappe.tests.click_page_head_item('Yes'),

			() => done()
		]);
	});

### Writing Test Friendly Code with Promises

Promises are a great way to write test-friendly code. If your method calls an aysnchronous call (ajax), then you should return an `Promise` object. While writing tests, if you encounter a function that does not return a `Promise` object, you should update the code to return a `Promise` object.
