import JsBarcode from "jsbarcode";

function get_options(value, df_options = null) {
	let options = {};
	options.fontSize = "16";
	options.width = "3";
	options.height = "50";
	if (df_options) {
		Object.assign(options, JSON.parse(df_options));
		if (options.format && options.format === "EAN") {
			options.format = value.length == 8 ? "EAN8" : "EAN13";
		}
	}
	return options;
}

window.render_barcode = (el) => {
	const value = el.dataset.barcodeValue;
	try {
		JsBarcode(el, value, get_options(value, el.dataset.options));
		el.setAttribute("width", "100%");
	} catch (e) {
		console.log(e);
	}
};
