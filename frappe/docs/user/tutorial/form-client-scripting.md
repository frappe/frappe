## Scripting Forms

Now we have created a basic system that works out of the box without us having to write any code. Let us now write some scripts to make the application richer and add validations so that the user does not enter wrong data.

### Client Side Scripting

In the **Library Transaction** DocType, we have only field for Member Name. We have not made two fields. Now this could well be two fields (and probably should), but for the sake of example, let us consider we have to implement this. To do this we would have to write a event handler for the event when the user selects the `library_member` field and then access the member resource from the server using REST API and set the values in the form.

To start the script, in the `library_management/doctype/library_transaction` folder, create a new file `library_transaction.js`. This file will be automatically executed when the first Library Transaction is opened by the user. So in this file, we can bind events and write other functions.

#### library_transaction.js

	frappe.ui.form.on("Library Transaction", "library_member",
		function(frm) {
			frappe.call({
				"method": "frappe.client.get",
				args: {
					doctype: "Library Member",
					name: frm.doc.library_member
				},
				callback: function (data) {
					frappe.model.set_value(frm.doctype,
						frm.docname, "member_name",
						data.message.first_name
						+ (data.message.last_name ?
							(" " + data.message.last_name) : ""))
				}
			})
		});

1. **frappe.ui.form.on(*doctype*, *fieldname*, *handler*)** is used to bind a handler to the event when the property library_member is set.
1. In the handler, we trigger an AJAX call to `frappe.client.get`. In response we get the requested object as JSON. [Learn more about the API](/help/rest_api).
1. Using **frappe.model.set_value(*doctype*, *name*, *fieldname*, *value*)** we set the value in the form.

**Note:** To check if your script works, remember to 'reload' the page before testing your script. Client script changes are not automatically picked up when you are in developer mode.

{next}
