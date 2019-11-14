/* HOW-TO

Razorpay Payment 

1. 	Include checkout script in your code 
	<script type="text/javascript" src="/assets/js/checkout.min.js"></script>

2.	Create the Order controller in your backend 
	def get_razorpay_order(self):
		controller = get_payment_gateway_controller("Razorpay")
		
		payment_details = {
			"amount": 300,
			...
			"reference_doctype": "Conference Participant",
			"reference_docname": self.name,
			...
			"receipt": self.name
		}

		return controller.create_order(**payment_details)

3. 	Inititate the payment in client using checkout API
	function make_payment(ticket) {
		var options = {
			"name": "<CHECKOUT MODAL TITLE>",
			"description": "<CHECKOUT MODAL DESCRIPTION>",
			"image": "<CHECKOUT MODAL LOGO>",
		    "prefill": {
				"name": "<CUSTOMER NAME>",
				"email": "<CUSTOMER EMAIL>",
				"contact": "<CUSTOMER PHONE>"
		    },
		    "theme": {
				"color": "<MODAL COLOR>"
		    },
		    "doctype": "<REFERENCE DOCTYPE>",
		    "docname": "<REFERENCE DOCNAME"
		};

		razorpay = new frappe.checkout.razorpay(options)
		razorpay.onOpen = () => {
			<SCRIPT TO RUN WHEN MODAL OPENS>
		}
		razorpay.onSuccess = () => {
			<SCRIPT TO RUN ON PAYMENT SUCCESS>
		}
		razorpay.onFail = () => {
			<SCRIPT TO RUN ON PAYMENT FAILURE>
		}
		razorpay.init() // Creates the order and opens the modal
	}
*/

frappe.provide("frappe.checkout")

frappe.require('https://checkout.razorpay.com/v1/checkout.js').then(() => {
	frappe.checkout.razorpay = class RazorpayCheckout {
		constructor(opts) {
			Object.assign(this, opts);
		}

		init() {
			frappe.run_serially([
				() => this.getKey(),
				() => this.makeOrder(),
				() => this.prepareOptions(),
				() => this.setupHandler(),
				() => this.show()
			])
		}

		show(callback=null) {
			this.razorpay = new Razorpay(this.options);
			this.razorpay.once('ready', (response) => {
  				this.onOpen && this.onOpen(response);
			})
    		this.razorpay.open();
		}

		getKey() {
			return new Promise(resolve => {
				frappe.call("frappe.integrations.doctype.razorpay_settings.razorpay_settings.get_api_key").then(res => {
					this.key = res.message
					resolve(true);
				})
			});
		}

		makeOrder() {
			return new Promise(resolve => {
				frappe.call("frappe.integrations.doctype.razorpay_settings.razorpay_settings.get_order", {
					doctype: this.doctype,
					docname: this.docname
				}).then(res => {
					this.order = res.message
					resolve(true);
				})
			});
		}

		orderSuccess(response) {
			frappe.call("frappe.integrations.doctype.razorpay_settings.razorpay_settings.order_payment_success", {
				integration_request: this.order.integration_request,
				params: {
					razorpay_payment_id: response.razorpay_payment_id,
					razorpay_order_id: response.razorpay_order_id,
					razorpay_signature: response.razorpay_signature
				}
			})
		}

		orderFail() {
			frappe.call( "frappe.integrations.doctype.razorpay_settings.razorpay_settings.order_payment_failure", {
				integration_request: this.order.integration_request,
				params: response
			})
		}

		prepareOptions() {
			this.options = {
				"key": this.key,
				"amount": this.order.amount_due, 
				"currency": this.order.currency,
				"name": this.name,
				"description": this.description,
				"image": this.image,
				"order_id": this.order.id,
				"prefill": this.prefill,
				"theme": this.theme,
				"modal": this.modal
			};
		}

		setupHandler() {
			this.options.handler = (response) => {
				if (response.error) {
					this.orderFail(response);
					this.onFail && this.onFail(response);
				}
				else if (response.razorpay_payment_id) {
					this.orderSuccess(response);	
					this.onSuccess && this.onSuccess(response);
				}
			}
		}
	}
})