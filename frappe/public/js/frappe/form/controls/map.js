frappe.ui.form.ControlMap = frappe.ui.form.ControlData.extend({
	loading: false,
	saving: false,
	make_wrapper() {
		// Create the elements for barcode area
		this._super();

		let $input_wrapper = this.$wrapper.find('.control-input-wrapper');
		this.map_area = $(
			`<div class="map-wrapper border">
				<div id="` + this.df.fieldname + `" style="min-height: 400px; z-index: 1"></div>
			</div>`
		);
		this.map_area.prependTo($input_wrapper);
		this.$wrapper.find('.control-input').addClass("hidden");
		this.bind_leaflet();
	},

	bind_leaflet(){
		L.Icon.Default.imagePath = '/assets/frappe/images/leaflet/';
		this.map = L.map(this.df.fieldname).setView([19.0800, 72.8961], 13);

		L.tileLayer('http://{s}.tile.osm.org/{z}/{x}/{y}.png', {
			attribution: '&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors'
		}).addTo(this.map);

		this.editableLayers = new L.FeatureGroup();

		var options = {
			position: 'topleft',
			draw: {
				polyline: {
					shapeOptions: {
						color: '#7573fc',
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
						color: '#7573fc'
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

		// create control and add to map
		var drawControl = new L.Control.Draw(options);
		this.map.addControl(drawControl);

		// Manually set location on click of locate button
		L.control.locate().addTo(this.map);
		// To request location update and set location, sets current geolocation on load
		// var lc = L.control.locate().addTo(this.map);
		// lc.start();

		this.map.on('draw:created', (e) => {
			var type = e.layerType,
				layer = e.layer;
			if (type === 'marker') {
				layer.bindPopup('Marker');
			}
			this.editableLayers = new L.FeatureGroup();
			this.editableLayers.addLayer(layer);
			this.set_value(JSON.stringify(this.editableLayers.toGeoJSON()));
		});

		this.map.on('draw:deleted', (e) => {
			var type = e.layerType,
				layer = e.layer;
			this.editableLayers.removeLayer(layer);
			this.set_value(JSON.stringify(this.editableLayers.toGeoJSON()));
		});

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
			this.add_non_group_layers(L.geoJson(JSON.parse(value)), this.editableLayers);
			this.map.addLayer(this.editableLayers);
		}
	},

	add_non_group_layers(source_layer, target_group) {
		if (source_layer instanceof L.LayerGroup) {
			source_layer.eachLayer((layer)=>{
				this.add_non_group_layers(layer, target_group);
			});
		} else {
			target_group.addLayer(source_layer);
		}
	}
});
