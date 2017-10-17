frappe.ui.form.ControlMap = frappe.ui.form.ControlData.extend({
	loading: false,
	make_wrapper() {
		// Create the elements for barcode area
		this._super();

		let $input_wrapper = this.$wrapper.find('.control-input-wrapper');
		this.map_area = $(
				`<div class="map-wrapper border">
					<div id="map-control" style="min-height: 400px; z-index: 1"></div>
				</div>`
			);
		this.map_area.prependTo($input_wrapper);
		L.Icon.Default.imagePath = 'assets/frappe/images/leaflet';
		this.map = L.map('map-control').setView([19.0800, 72.8961], 13);

		L.tileLayer('http://{s}.tile.osm.org/{z}/{x}/{y}.png', {
			attribution: '&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors'
		}).addTo(this.map);

		this.$wrapper.find('.control-input').addClass("hidden");

		if (this.editableLayers === undefined){
			this.set_editable_layers();
		}
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
				featureGroup: this.editableLayers, //REQUIRED!!
				remove: true
			}
		};
		var drawControl = new L.Control.Draw(options);
		this.map.addControl(drawControl);
		// create control and add to map
		this.bind_draw_create();
		this.bind_draw_delete();
		this.bind_draw_edit();
		var lc = L.control.locate().addTo(this.map);

		// request location update and set location, sets current geolocation on load
		// lc.start();
	},

	bind_draw_create(){
		this.map.on('draw:created', (e) => {
			var type = e.layerType,
				layer = e.layer;
			if (type === 'marker') {
				layer.bindPopup('Marker');
			}
			this.editableLayers.addLayer(layer);
			this.set_value(JSON.stringify(this.editableLayers.toGeoJSON()));
		});
	},

	bind_draw_delete(){
		this.map.on('draw:deleted', (e) => {
			var type = e.layerType,
				layer = e.layer;
			this.editableLayers.removeLayer(layer);
			this.set_value(JSON.stringify(this.editableLayers.toGeoJSON()));
		});
	},

	bind_draw_edit(){
		this.map.on('draw:edited', (e) => {
			var type = e.layerType,
				layer = e.layer;
			this.editableLayers.removeLayer(layer);
			this.set_value(JSON.stringify(this.editableLayers.toGeoJSON()));
		});
	},

	format_for_input(value) {
		this.map.removeLayer(this.editableLayers);
		if(value){
			this.editableLayers = L.geoJson(JSON.parse(value)).addTo(this.map);
			this.map.addLayer(this.editableLayers);
		}
	},

	set_editable_layers(){
		this.editableLayers = new L.FeatureGroup();
	}
});
