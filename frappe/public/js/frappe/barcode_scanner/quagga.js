import Quagga from 'quagga/dist/quagga';
frappe.provide('frappe.barcode');

Quagga.onProcessed(function(result) {
	let drawingCtx = Quagga.canvas.ctx.overlay,
		drawingCanvas = Quagga.canvas.dom.overlay;

	if (result) {
		if (result.boxes) {
			drawingCtx.clearRect(
				0,
				0,
				parseInt(drawingCanvas.getAttribute('width')),
				parseInt(drawingCanvas.getAttribute('height'))
			);
			result.boxes
				.filter(function(box) {
					return box !== result.box;
				})
				.forEach(function(box) {
					Quagga.ImageDebug.drawPath(box, { x: 0, y: 1 }, drawingCtx, {
						color: 'green',
						lineWidth: 2
					});
				});
		}

		if (result.box) {
			Quagga.ImageDebug.drawPath(result.box, { x: 0, y: 1 }, drawingCtx, {
				color: '#00F',
				lineWidth: 2
			});
		}

		if (result.codeResult && result.codeResult.code) {
			Quagga.ImageDebug.drawPath(result.line, { x: 'x', y: 'y' }, drawingCtx, {
				color: 'red',
				lineWidth: 3
			});
		}
	}
});

frappe.barcode.get_barcode = function() {
	return new Promise(resolve => {
		let d = new frappe.ui.Dialog({
			title: __('Scan Barcode'),
			fields: [
				{
					fieldtype: 'HTML',
					fieldname: 'scan_area'
				}
			],
			on_page_show() {
				let $scan_area = d.get_field('scan_area').$wrapper;
				$scan_area.addClass('barcode-scanner');

				Quagga.init(
					{
						inputStream: {
							name: 'Live',
							type: 'LiveStream',
							target: $scan_area.get(0)
						},
						decoder: {
							readers: ['code_128_reader']
						}
					},
					function(err) {
						if (err) {
							// eslint-disable-next-line
							console.log(err);
							return;
						}
						// eslint-disable-next-line
						console.log('Initialization finished. Ready to start');
						Quagga.start();
					}
				);

				Quagga.onDetected(function(result) {
					let code = result.codeResult.code;
					if (code) {
						Quagga.stop();
						d.hide();
						resolve(code);
					}
				});
			}
		});

		d.show();
	});
};
