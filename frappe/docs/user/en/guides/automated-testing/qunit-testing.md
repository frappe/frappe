# UI Testing with Frappe API

You can either write integration tests, or directly write tests in Javascript using [QUnit](http://api.qunitjs.com/)

QUnit helps you write UI tests using the UQuit framework and native frappe API. As you might have guessed, this is a much faster way of writing tests.

### Test Runner

To write QUnit based tests, add your tests in the `tests/ui` folder of your application. Your test files must begin with `test_` and end with `.js` extension.

To run your files, you can use the **Test Runner**. The **Test Runner** gives a user interface to load all your QUnit tests and run them in the browser.

In the CI, all QUnit tests are run by the **Test Runner** using `frappe/tests/test_test_runner.py`

<img src="{{docs_base_url}}/assets/img/app-development/test-runner.png" class="screenshot">

### Example QUnit Test

Here is the example of the To Do test in QUnit

    QUnit.test("test quick entry", function(assert) {
        assert.expect(2);
        let done = assert.async();
        let random = frappe.utils.get_random(10);

        frappe.set_route('List', 'ToDo')
            .then(() => {
                return frappe.new_doc('ToDo');
            })
            .then(() => {
                frappe.quick_entry.dialog.set_value('description', random);
                return frappe.quick_entry.insert();
            })
            .then((doc) => {
                assert.ok(doc && !doc.__islocal);
                return frappe.set_route('Form', 'ToDo', doc.name);
            })
            .then(() => {
                assert.ok(cur_frm.doc.description.includes(random));
                done();
            });
    });

### Writing Test Friendly Code with Promises

Promises are a great way to write test-friendly code. If your method calls an aysnchronous call (ajax), then you should return an `Promise` object. While writing tests, if you encounter a function that does not return a `Promise` object, you should update the code to return a `Promise` object.
