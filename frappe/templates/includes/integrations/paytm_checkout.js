function onScriptLoad() {
	console.log('inside on load')
	var config = {
		root: '',
		flow: 'DEFAULT',
		data: {
			orderId: '{{ order_id}}',
			token: '{{ token }}',
			tokenType: 'TXN_TOKEN',
			amount: '{{ amount }}'
		},
		handler: {
			notifyMerchant: function(eventName, data) {
				// notify about the state of the payment page ( invalid token , session expire , cancel transaction)
				console.log('notifyMerchant handler function called');
				console.log('eventName => ', eventName);
				console.log('data => ', data);
			},
			transactionStatus: function transactionStatus(paymentStatus) {
				// provide information to merchant about the payment status.
				console.log('transaction status handler function called');
				console.log('paymentStatus => ', paymentStatus);
			}
		}
	};

	$('.paytm-loading').addClass('hidden');
	if (window.Paytm && window.Paytm.CheckoutJS) {
		window.Paytm.CheckoutJS.onLoad(function excecuteAfterCompleteLoad() {
			// initialze configuration using init method
			window.Paytm.CheckoutJS.init(config)
				.then(function onSuccess() {
					// after successfully updating configuration, invoke Blink Checkout
					window.Paytm.CheckoutJS.invoke();
				})
				.catch(function onError(error) {
					console.log('inside the error window')
					console.log('error => ', error);
				});
		});
	}
}
