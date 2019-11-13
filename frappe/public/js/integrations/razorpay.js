frappe.provide("frappe.checkout")

frappe.require('https://checkout.razorpay.com/v1/checkout.js').then(() => {
	frappe.checkout.razorpay = class RazorpayCheckout {
		constructor(opts) {
			Object.assign(this, opts);
		}

		init() {
			frappe.run_serially([
				() => this.makeOrder(),
				() => this.prepareOptions(),
				() => this.setupHandler(),
				() => this.show()
			])
		}

		show(callback=null) {
			let razorpay = new Razorpay(this.options);
			razorpay.once('ready', function(response) {
  				this.onOpen && this.onOpen(response);
			})
    		razorpay.open();
		}

		makeOrder() {
			return new Promise(resolve => {
				frappe.call( "frappe.integrations.doctype.razorpay_settings.razorpay_settings.get_order", {
					doctype: this.doctype,
					docname: this.docname
				}).then(res => {
					this.order = res.message
					resolve(true);
				})
			});
		}

		orderSuccess(response) {
			frappe.call( "frappe.integrations.doctype.razorpay_settings.razorpay_settings.order_payment_success", {
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
				"theme": this.theme
			};
		}

		setupHandler() {
			this.options.handler = (response) => {
				if (response.error) {
					this.orderFail(response);
					this.onFail && this.onFail(response);
				}
				if (response.razorpay_payment_id) {
					this.orderSuccess(response);	
					this.onSuccess && this.onSuccess(response);
				}
			}
		}
	}
})