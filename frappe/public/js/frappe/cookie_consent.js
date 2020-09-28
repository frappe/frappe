frappe.provide('frappe.cookie');

frappe.cookie.cookie_consent = function() {
	// var style = getComputedStyle(document.body);
	window.cookieconsent.initialise({
		// palette: {
		// 	popup: {
		// 		background: style.getPropertyValue('--light'),
		// 		text: style.getPropertyValue('--dark'),
		// 	},
		// 	button: {
		// 		background: style.getPropertyValue('--primary'),
		// 		text: style.getPropertyValue('--white'),
		// 	},
		// 	highlight: {
		// 		background: style.getPropertyValue('--success'),
		// 		text: style.getPropertyValue('--white'),
		// 	}
		// },
		theme: "classic",
		position: 'bottom-left', // bottom-right, top, bottom (default)
		// static: true,
		type: 'opt-in', // categories, info, opt-in, opt-out
		layout: 'basic-header',
		content: {
			header: __('This website uses cookies'),
			message: __('We use cookies to ensure you get the best experience on our website.'),
			dismiss: __('Got it!'),
			allow: __('Allow cookies'),
			deny: __('Decline'),
			link: __('Learn more'),
			href: 'https://www.cookiesandyou.com',
			close: '&#x274c',
			target: '_blank',
			policy: __('Cookie Policy')
		},
		// overrideHTML: `<div>Custom HTML</div>`, // overrides everything
		// onInitialise: function (status) {
		// 	var type = this.options.type;
		// 	var didConsent = this.hasConsented();
		// 	if (type == 'opt-in' && didConsent) {
		// 		// enable cookies
		// 	}
		// 	if (type == 'opt-out' && !didConsent) {
		// 		// disable cookies
		// 	}
		// },
		// onStatusChange: function(status, chosenBefore) {
		// 	var type = this.options.type;
		// 	var didConsent = this.hasConsented();
		// 	if (type == 'opt-in' && didConsent) {
		// 		// enable cookies
		// 	}
		// 	if (type == 'opt-out' && !didConsent) {
		// 		// disable cookies
		// 	}
		// },
		// onRevokeChoice: function() {
		// 	var type = this.options.type;
		// 	if (type == 'opt-in') {
		// 		// disable cookies
		// 	}
		// 	if (type == 'opt-out') {
		// 		// enable cookies
		// 	}
		// }
	});
};
