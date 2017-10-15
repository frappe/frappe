frappe.ui.form.ControlMap = frappe.ui.form.ControlData.extend({
	make_wrapper() {
		// Create the elements for barcode area
		this._super();

		let $input_wrapper = this.$wrapper.find('.control-input-wrapper');
		this.map_area = $(`<div class="map-wrapper border">
								<div id="map-control" style="height: 180px; z-index: 1"></div>
							</div>`);
		frappe.require([
				"assets/frappe/js/lib/leaflet/leaflet.js",
				"assets/frappe/js/lib/leaflet/leaflet.css"
			], () => {
			this.map_area.prependTo($input_wrapper);

			var map = L.map('map-control').setView([19.0800, 72.8961], 13);

			L.tileLayer('http://{s}.tile.osm.org/{z}/{x}/{y}.png', {
				attribution: '&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors'
			}).addTo(map);

			var MyCustomMarker = L.Icon.extend({
				options: {
				shadowUrl: null,
				iconAnchor: new L.Point(12, 12),
				iconSize: new L.Point(24, 24),
				iconUrl: 'assets/frappe/images/leaflet/marker-icon.png'
				}
			});

			L.marker([19.0800, 72.8961], { icon: new MyCustomMarker() }).addTo(map)
				.bindPopup('Map Center')
				.openPopup();
			this.$wrapper.find('.control-input').hide();
		});
	}
});
