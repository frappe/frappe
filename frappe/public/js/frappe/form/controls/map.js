frappe.ui.form.ControlMap = frappe.ui.form.ControlData.extend({
	make_wrapper() {
		// Create the elements for barcode area
		this._super();

		let $input_wrapper = this.$wrapper.find('.control-input-wrapper');
		this.map_area = $(
			`<div class="map-wrapper border">
				<div id="map-control" style="min-height: 400px; z-index: 1"></div>
			</div>`
		);
		frappe.require([
				"assets/frappe/js/lib/leaflet/leaflet.css",
				"assets/frappe/js/lib/leaflet/leaflet.js",
				"assets/frappe/js/lib/leaflet/leaflet.draw.css",
				"assets/frappe/js/lib/leaflet/leaflet.draw.js",
		], () => {
			L.Icon.Default.imagePath = 'assets/frappe/images/leaflet';
			this.map_area.prependTo($input_wrapper);
			map = L.map('map-control').setView([19.0800, 72.8961], 13);

			L.tileLayer('http://{s}.tile.osm.org/{z}/{x}/{y}.png', {
				attribution: '&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors'
			}).addTo(map);

			var editableLayers = new L.FeatureGroup();

			if((this.value != undefined) || (this.value != null)){
				editableLayers = L.geoJson(JSON.parse(this.value)).addTo(map);
			}

			map.addLayer(editableLayers);
			var options = {
				position: 'topleft',
				draw: {
					polyline: {
						shapeOptions: {
							color: '#f357a1',
							weight: 10
						}
					},
					polygon: {
						allowIntersection: false, // Restricts shapes to simple polygons
						drawError: {
							color: '#e1e100', // Color the shape will turn when intersects
							message: '<strong>Oh snap!<strong> you can\'t draw that!' // Message that will show when intersect
						},
						shapeOptions: {
							color: '#f357a1'
						}
					},
					circle: true,
					rectangle: {
						shapeOptions: {
							clickable: false
						}
					}
				},
				edit: {
					featureGroup: editableLayers, //REQUIRED!!
					remove: true
				}
			};
			var drawControl = new L.Control.Draw(options);
			map.addControl(drawControl);

			map.on('draw:created', (e) => {
				var type = e.layerType,
				layer = e.layer;
				if (type === 'marker') {
					layer.bindPopup('A popup!');
				}
				editableLayers.addLayer(layer);
				this.set_value(JSON.stringify(editableLayers.toGeoJSON()));
			});

			map.on('draw:deleted', (e) => {
				var type = e.layerType,
				layer = e.layer;
				editableLayers.removeLayer(layer);
				this.set_value(JSON.stringify(editableLayers.toGeoJSON()));
			});

			map.on('draw:edited', (e) => {
				var type = e.layerType,
				layer = e.layer;
				editableLayers.removeLayer(layer);
				this.set_value(JSON.stringify(editableLayers.toGeoJSON()));
			});
			this.$wrapper.find('.control-input').hide();
		});
	}
});
