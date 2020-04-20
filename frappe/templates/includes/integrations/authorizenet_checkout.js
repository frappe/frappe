$('#submit').on("click", function (e) {
	data = context.replace(/'/g, '"');
	e.preventDefault();
	cardNumber = document.getElementById('cardholder-cardNumber').value;
	expirationDate = document.getElementById('cardholder-expirationDate').value;
	cardCode = document.getElementById('cardholder-cardCode').value;

	frappe.call({
		method: "frappe.integrations.doctype.authorizenet_settings.authorizenet_settings.charge_credit_card",
		freeze: true,
		args: {
			"card_number": cardNumber,
			"expiration_date": expirationDate,
			"card_code": cardCode,
			"data": data
		},
		callback: function (r) {
			if (r.message.status === "Completed") {
				window.location.href = "/integrations/payment-success"
			}
			else {
				frappe.throw(__(`${r.message.description}`));
			}
		}
	})
});