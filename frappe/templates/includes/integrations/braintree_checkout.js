$(document).ready(function() {

	var button = document.querySelector('#submit-button');
	var form = document.querySelector('#payment-form');
	var data = {{ frappe.form_dict | json }};
	var doctype = "{{ reference_doctype }}"
	var docname = "{{ reference_docname }}"

	braintree.dropin.create({
		authorization: "{{ client_token }}",
		container: '#bt-dropin',
		paypal: {
			flow: 'vault'
		}
	}, function(createErr, instance) {
		form.addEventListener('submit', function(event) {
			event.preventDefault();
			instance.requestPaymentMethod(function(err, payload) {
				if (err) {
					console.log('Error', err);
					return;
				}
				frappe.call({
					method: "frappe.templates.pages.integrations.braintree_checkout.make_payment",
					freeze: true,
					headers: {
						"X-Requested-With": "XMLHttpRequest"
					},
					args: {
						"payload_nonce": payload.nonce,
						"data": JSON.stringify(data),
						"reference_doctype": doctype,
						"reference_docname": docname
					},
					callback: function(r) {
						if (r.message && r.message.status == "Completed") {
							window.location.href = r.message.redirect_to
						} else if (r.message && r.message.status == "Error") {
							window.location.href = r.message.redirect_to
						}
					}
				})
			});
		});

		instance.on('paymentMethodRequestable', function (event) {
			button.removeAttribute('disabled');
		});

		instance.on('noPaymentMethodRequestable', function () {
			button.setAttribute('disabled', true);
		});
	});

})
