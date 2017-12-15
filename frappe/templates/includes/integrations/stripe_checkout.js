$(document).ready(function(){
	(function(e){
		var handler = StripeCheckout.configure({
			key: "{{ publishable_key }}",
			token: function(token) {
				// You can access the token ID with `token.id`.
				// Get the token ID to your server-side code for use.
				stripe.make_payment_log(token, {{ frappe.form_dict|json }}, "{{ reference_doctype }}", "{{ reference_docname }}");
			}
		});
		
		handler.open({
			name: "{{payer_name}}",
			description: "{{description}}",
			amount: cint("{{ amount }}" * 100), // 2000 paise = INR 20
			email: "{{payer_email}}",
			currency: "{{currency}}"
		});
		
	})();
})

frappe.provide('stripe');

stripe.make_payment_log = function(token, data, doctype, docname){
	$('.stripe-loading').addClass('hidden');
	$('.stripe-confirming').removeClass('hidden');
	frappe.call({
		method:"frappe.templates.pages.integrations.stripe_checkout.make_payment",
		freeze:true,
		headers: {"X-Requested-With": "XMLHttpRequest"},
		args: {
			"stripe_token_id": token.id,
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
}
