In Web applications Client initiates the request, server accept the request, process it and sends response back to client.

<img class="screenshot" src="{{docs_base_url}}/assets/img/client_server_communication.png">

In frappe framework, `frappe.call` calls an AJAX request on the specified white listed server method.

This can be used while scripting forms or building custom UI on the Desk. 

Sample use cases are:

- Querying data from the server using REST API
- Calling whitelisted server methods

## Basic Structure of frappe.call

	frappe.call({
		type: opts.type || "POST",
		args: args,
		success: callback,
		error: opts.error,
		always: opts.always,
		btn: opts.btn,
		freeze: opts.freeze,
		freeze_message: opts.freeze_message,
		async: opts.async,
		url: opts.url || frappe.request.url,
	})

##### Parameter description :
- type: String parameter, http request type "GET", "POST", "PUT", "DELETE". Default set to "POST".
- args: associative array, arguments that will pass with request.
- success: Function parameter, code snippet, will after successful execution of request
- error: Function parameter, code snippet, will execute after request failure
- always: Function parameter, code snipper, will execute in either case
- btn: Object parameter, triggering object
- freeze: Boolean parameter, if set freeze the instance util it receives response
- freeze_message: String parameter, message will populate to screen while screen is in freeze state.
- async: Boolean parameter, default set to true. So each frappe.call is asynchronous. To make call synchronous set parameter value as false
- url: String parameter, location from where hitting the request


## Example

### Without server access
frappe.call() design supports, request making without having access to server script.

- Param description:
	- doctype: name of doctype for which you want to pull information
	- filters: condition specifier
	- fieldname: you can specify fields in array that you want back in response

			frappe.call({
				method: 'frappe.client.get_value',
				args: {
					'doctype': 'Item',
					'filters': {'name': item_code},
					'fieldname': [
						'item_name',
						'web_long_description',
						'description',
						'image',
						'thumbnail'
					]
				},
				callback: function(r) {
					if (!r.exc) {
						// code snippet
					}
				}
			});
	
### With server access
- Code client side

		frappe.call({
			method: "frappe.core.doctype.user.user.get_all_roles", //dotted path to server method
			callback: function(r) {
				// code snippet
			}
		})

- Code at server side

		@frappe.whitelist()
		def get_all_roles():
			// business logic
			return value

Note: While accessing any server side method via frappe.call(), you need to whitelist server side method by using decorator `@frappe.whitelist`