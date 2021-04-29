frappe.provide('frappe.barcode');

frappe.barcode.scan_barcode = function() {
	return new Promise((resolve, reject) => {
		if (
			window.cordova &&
			window.cordova.plugins &&
			window.cordova.plugins.barcodeScanner
		) {
			window.cordova.plugins.barcodeScanner.scan(result => {
				if (!result.cancelled) {
					resolve(result.text);
				}
			}, reject);
		} else {
			frappe.require('barcode_scanner.bundle.js', () => {
				frappe.barcode.get_barcode().then(barcode => {
					resolve(barcode);
				});
			});
		}
	});
};
