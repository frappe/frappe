var url = window.location.href

context = decodeURIComponent(url)
function getJSON(url) {
	var hash;
	var myJson = {};
	var hashes = url.replace(/\+/g, ' ').slice(url.indexOf('?') + 1).split('&');
	for (var i = 0; i < hashes.length; i++) {
		hash = hashes[i].split('=');
		myJson[hash[0]] = hash[1]
	}
	return myJson;
}
data = getJSON(context)

$('#submit').on("click", function (e) {
	e.preventDefault();
	cardNumber = document.getElementById('cardholder-cardNumber').value;
	expirationDate = document.getElementById('cardholder-expirationDate').value;
	cardCode = document.getElementById('cardholder-cardCode').value;

	frappe.call({
		method: "frappe.integrations.doctype.authorizenet_settings.authorizenet_settings.charge_credit_card",
		freeze: true,
		args: {
			"cardNumber": cardNumber,
			"expirationDate": expirationDate,
			"cardCode": cardCode,
			"data": data
		},
		callback: function (r) {
			if (r.message === "Completed") {
				window.location.href = "/integrations/payment-success"
			}
			else {
				window.location.href = "/integrations/payment-failed"
			}
		}
	})
});