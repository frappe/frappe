// frappe.provide("frappe.integration_service")

// frappe.integration_service.razorpay = {
// 	load: function(frm) {
// 		new frappe.integration_service.Razorpay(frm)
// 	},
// 	scheduler_job_helper: function(){
// 		return  {
// 			"Every few minutes": "Check and capture new payments"
// 		}
// 	}
// }

// frappe.integration_service.Razorpay =  Class.extend({
// 	init:function(frm){
// 		this.frm = frm;
// 		this.frm.toggle_display("use_test_account", false);
// 		this.show_logs();
// 	},
// 	show_logs: function(){
// 		this.frm.add_custom_button(__("Show Log"), function(frm){
// 			frappe.route_options = {"integration_request_service": "Razorpay"};
// 			frappe.set_route("List", "Integration Request");
// 		});
// 	}
// })
// 

// function make_payment(order, ticket) {
// 		var options = {
// 			"key":  "rzp_test_lExD7NVL1JoKJJ", // Enter the Key ID generated from the Dashboard
// 			"amount": order.amount_due, // Amount is in currency subunits. Default currency is INR. Hence, 50000 refers to 50000 paise or INR 500.
// 			"currency": order.currency,
// 			"name": "IndiaOS",
// 			"description": "Conference Ticket",
// 			"image": "http://indiaos.in/assets/indiaos/img/icons/favicon.ico",
// 			"order_id": order.id,
// 			"prefill": {
// 				"name": ticket.full_name,
// 				"email": ticket.email,
// 				"contact": '7506056962'
// 			},
// 			"theme": {
// 				"color": "#F6E05E"
// 			}
// 		};

// 		options.handler = function (response){
// 			if (response.error) {
// 				openModal();
// 				fail('payment-failed');
// 			}

// 			if (response.razorpay_payment_id) {
// 				openModal();
// 				success();
				
// 			}
// 		}

// 		var razorpay = new Razorpay(options);
// 		razorpay.once('ready', function(response) {
//   			modalClose();
// 		})

//		razorpay.open();

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