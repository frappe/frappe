$(document).ready(function(){
	var button = document.querySelector('#submit-button');
	var form = document.querySelector('#payment-form');

	braintree.dropin.create({
    authorization: 'sandbox_7dsn3svb_pfsbz9xn3pzywcdf',
    container: '#bt-dropin',
    paypal: {
      flow: 'vault'
    }
  }, function (createErr, instance) {
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      instance.requestPaymentMethod(function (err, payload) {
        if (err) {
          console.log('Error', err);
          return;
        }
        // Add the nonce to the form and submit
        document.querySelector('#nonce').value = payload.nonce;
				frappe.call({
					method:"frappe.templates.pages.integrations.braintree_checkout.make_payment",
					freeze:true,
					headers: {"X-Requested-With": "XMLHttpRequest"},
					args: {
						"braintree_token_id": token.id,
						"data": JSON.stringify(data),
						"reference_doctype": doctype,
						"reference_docname": docname
					},
					callback: function(r){
						if (r.message && r.message.status == 200) {
							window.location.href = r.message.redirect_to
						}
						else if (r.message && ([401,400,500].indexOf(r.message.status) > -1)) {
							window.location.href = r.message.redirect_to
						}
					}
				})
      });
    });
  });

})
