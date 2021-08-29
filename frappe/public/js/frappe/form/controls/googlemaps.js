frappe.provide('frappe.utils.utils');
let marker;
let i;
let z;
let default_icon_url = "https://iconsplace.com/wp-content/uploads/_icons/ff0000/256/png/radio-tower-icon-14-256.png";
let markers = []

frappe.ui.form.ControlGooglemaps = frappe.ui.form.ControlData.extend({
	horizontal: false,

	format_for_input(value) {
		this.get_google_icons()
            .then(() => {
                this.render_map(value)
            });
	},

	render_map(value) {
		//set bounds variable for fitbBounds function (set map center with multiple markers)
		var bounds = new google.maps.LatLngBounds();
		let markers = []

		// run if form has value (markers, circles, etc);
		if (value) {
			this.objValue;
			this.objValue = JSON.parse(value);

			// set default icon
			var default_icon = {
				url: default_icon_url,
				scaledSize: new google.maps.Size(20, 20)
			};

			// list of markers
			var points = this.objValue.features.filter(function(ele) {
				return ele.properties.point_type === "marker";
			});

			// list of circles
			var circle = this.objValue.features.filter(function(ele) {
				return ele.properties.point_type === "circle";
			});

			if (points.length > 0) {

				//create dafult map
				let map = new google.maps.Map(document.getElementById("map"), {
					zoom: 8,
					mapTypeId: "terrain",
					center: {lat: -6.321916245621676, lng:106.67620042320505}

				});

				// map.setOptions({
				// 	maxZoom: 10
				// });

				for (i = 0; i < points.length; i++) {
					for (z = 0; z < this.icons.length; z++) {
						// set icons get from json or default icon url if icon in json
						if (points[i].properties.icon === this.icons[z].name1) {
							this.icon_url = this.icons[z].icon_image;
						} else {
							this.icon_url = default_icon_url;
						}
					}
					
					// set icon for gmaps
					const icon = {
						url: this.icon_url,
						scaledSize: new google.maps.Size(15, 15)
					};
					
					// draw markers on gmaps
					var marker = new google.maps.Marker({
						position: new google.maps.LatLng(points[i].geometry.coordinates[1], points[i].geometry.coordinates[0]),
						map: map,
						icon: icon
					});

					markers.push(marker);

					var infowindow = new google.maps.InfoWindow();
					var markerLabel = points[i].properties.name;
					google.maps.event.addListener(marker,'click', (function(marker,markerLabel,infowindow){ 
						return function() {
							infowindow.setContent(markerLabel);
							infowindow.open(map,marker);
						};
					})(marker,markerLabel,infowindow)); 
					bounds.extend(marker.position);
					// map.setCenter(this.markersCenter.lng, this.markersCenter.lat); // set map center to marker position
					
					// map.fitBounds(bounds);
				}

				// google.maps.event.addListener(marker, 'dblclick', function(event){
				// 	map = marker.getMap();    
				// 	map.setCenter(overlay.getPosition()); // set map center to marker position
				// 	smoothZoom(map, 12, map.getZoom()); // call smoothZoom, parameters map, final zoomLevel, and starting zoom level
				// });
				// this.fitToMarkers(map, markers);
				// map.fitBounds(bounds);
				// map.panTo(bounds);

				if (circle.length > 0) {
					for (i = 0; i < circle.length; i++) {  
						const cityCircle = new google.maps.Circle({
							fillColor: "rgb(51, 136, 255)",
							fillOpacity: 0.2,
							strokeWeight: 1,
							strokeColor: "rgb(51, 136, 255)",
							clickable: false,
							editable: true,
							zIndex: 1,
							map,
							center: {lng: circle[i].geometry.coordinates[0], lat: circle[i].geometry.coordinates[1]},
							radius: circle[i].properties.radius
						});
					}
				}

				this.getMarkersCenter(markers);
				map.setCenter(new google.maps.LatLng(
					this.markersCenter.lat,
					this.markersCenter.lng
				));

				if (this.markersZoom > 18) {
					this.markersZoom = 18;
				}

				console.log(this.markersZoom);

				this.smoothZoom(map, this.markersZoom, map.getZoom()); // call smoothZoom, parameters map, final zoomLevel, and starting zoom level


				const drawingManager = new google.maps.drawing.DrawingManager({
					drawingMode: google.maps.drawing.OverlayType.MARKER,
					drawingControl: true,
					drawingControlOptions: {
					  position: google.maps.ControlPosition.TOP_CENTER,
					  drawingModes: [
						google.maps.drawing.OverlayType.MARKER,
						google.maps.drawing.OverlayType.CIRCLE,
						// google.maps.drawing.OverlayType.POLYGON,
						// google.maps.drawing.OverlayType.POLYLINE,
						// google.maps.drawing.OverlayType.RECTANGLE,
					  ],
					},
					markerOptions: {
					  icon: default_icon,
					},
					circleOptions: {
						fillColor: "rgb(51, 136, 255)",
						fillOpacity: 0.2,
						strokeWeight: 1,
						strokeColor: "rgb(51, 136, 255)",
						clickable: false,
						editable: true,
						zIndex: 1,
					  },
				});
				drawingManager.setMap(map);

				this.customControlDiv = document.createElement('div');
				this.customControl = this.custom_control(this.customControlDiv, map);

				this.customControlDiv.index = 1;
				map.controls[google.maps.ControlPosition.TOP_CENTER].push(this.customControlDiv);


				google.maps.event.addListener(drawingManager, 'overlaycomplete', function(event) {
					if (event.type == 'circle') {

						let newDataCircle = 
						{
							"type": "Feature",
							"properties": {
							  "point_type": "circle",
							  "radius": event.overlay.getRadius()
							},
							"geometry": {
							  "type": "Point",
							  "coordinates": [
								event.overlay.getCenter().lng(),
								event.overlay.getCenter().lat()
							  ]
							}
						}


						self.objValue.features.push(newDataCircle);
						self.set_value(JSON.stringify(self.objValue));
					} else if (event.type == 'marker') {

						let newDataMarker = 
						{
							"type": "Feature",
							"properties": {
								"point_type": "marker"
							},
							"geometry": {
								"type": "Point",
								"coordinates": [
								event.overlay.getPosition().lng(),
								event.overlay.getPosition().lat()]
							}
						}
						self.objValue.features.push(newDataMarker);
						self.set_value(JSON.stringify(self.objValue));
					}
				});
			}
		} else if (value===undefined || value === "") {
			const icon = {
				url: "https://iconsplace.com/wp-content/uploads/_icons/ff0000/256/png/radio-tower-icon-14-256.png",
				scaledSize: new google.maps.Size(20, 20)
			};

			let map = new google.maps.Map(document.getElementById("map"), {
				zoom: 13,
				center: { lat: -6.304551452226169, lng: 106.68479307871746 },
				mapTypeId: "terrain",
			});

			// map.setOptions({
			// 	minZoom: 0
			// });

			const drawingManager = new google.maps.drawing.DrawingManager({
				drawingMode: google.maps.drawing.OverlayType.MARKER,
				drawingControl: true,
				drawingControlOptions: {
				  position: google.maps.ControlPosition.TOP_CENTER,
				  drawingModes: [
					google.maps.drawing.OverlayType.MARKER,
					google.maps.drawing.OverlayType.CIRCLE,
					// google.maps.drawing.OverlayType.POLYGON,
					// google.maps.drawing.OverlayType.POLYLINE,
					// google.maps.drawing.OverlayType.RECTANGLE,
				  ],
				},
				markerOptions: {
				  icon: icon,
				},
				circleOptions: {
					fillColor: "rgb(51, 136, 255)",
					fillOpacity: 0.2,
					strokeWeight: 1,
					strokeColor: "rgb(51, 136, 255)",
					clickable: false,
					editable: true,
					zIndex: 1,
				  },
			});

			drawingManager.setMap(map);
			this.customControlDiv = document.createElement('div');
			this.customControl = this.custom_control(this.customControlDiv, map);

			this.customControlDiv.index = 1;
			map.controls[google.maps.ControlPosition.TOP_CENTER].push(this.customControlDiv);


			// this.clear_gmap_button();

			google.maps.event.addListener(drawingManager, 'overlaycomplete', function(event) {
				if (event.type == 'circle') {

					var data_layers =
						{
							"type": "FeatureCollection",
							"features": [
								{
									"type": "Feature",
									"properties": {
									  "point_type": "circle",
									  "radius": event.overlay.getRadius()
									},
									"geometry": {
									  "type": "Point",
									  "coordinates": [
										event.overlay.getCenter().lng(),
										event.overlay.getCenter().lat()
									  ]
									}
								}
							]
						}
					self.set_value(JSON.stringify(data_layers));
				} else if (event.type == 'marker') {

					var data_layers =
						{
							"type": "FeatureCollection",
							"features": [
								{
									"type": "Feature",
									"properties": {
										"point_type": "marker"
									},
									"geometry": {
										"type": "Point",
										"coordinates": [
										event.overlay.getPosition().lng(),
										event.overlay.getPosition().lat()]
									}
								}
							]
						}	
					self.set_value(JSON.stringify(data_layers));
				}
			});
		}
	},

	getZoomLevel(lngMin,lngMax) {
		var GLOBE_WIDTH = 256; // a constant in Google's map projection
		var angle = lngMax - lngMin;
		if (angle < 0) {
			angle += 360;
		}
		this.markersZoom = Math.round(Math.log(256 * 360 / angle / GLOBE_WIDTH) / Math.LN2);
	},

	getMarkersCenter(markers) {
		let latMin;
		let latMax;
		let lngMin;
		let lngMax;

		for (var index in markers) {
			if (index == 0) {
				latMin = markers[index].getPosition().lat();
				latMax = markers[index].getPosition().lat();
				lngMin = markers[index].getPosition().lng();
				lngMax = markers[index].getPosition().lng();
			} else {
				if (latMin > markers[index].getPosition().lat()) {
					latMin = markers[index].getPosition().lat();
				} else if (latMax < markers[index].getPosition().lat()) {
					latMax = markers[index].getPosition().lat();
				}
				
				if (lngMin > markers[index].getPosition().lng()) {
					lngMin = markers[index].getPosition().lng();
				} else if (lngMax < markers[index].getPosition().lng()) {
					lngMax = markers[index].getPosition().lng();
				}
			}
		}
		this.markersCenter = {lat: ((latMax + latMin) / 2.0), lng:  ((lngMax + lngMin) / 2.0)}
		this.getZoomLevel(lngMin,lngMax)
	},



	// fitToMarkers(map, markers) {
	// 	var bounds = new google.maps.LatLngBounds();
	
	// 	// Create bounds from markers
	// 	for( var index in markers ) {
	// 		var latlng = markers[index].getPosition();
	// 		bounds.extend(latlng);
	// 	}
	
	// 	// Don't zoom in too far on only one marker
	// 	if (bounds.getNorthEast().equals(bounds.getSouthWest())) {
	// 	   var extendPoint1 = new google.maps.LatLng(bounds.getNorthEast().lat() + 0.01, bounds.getNorthEast().lng() + 0.01);
	// 	   var extendPoint2 = new google.maps.LatLng(bounds.getNorthEast().lat() - 0.01, bounds.getNorthEast().lng() - 0.01);
	// 	   bounds.extend(extendPoint1);
	// 	   bounds.extend(extendPoint2);
	// 	}
	
	// 	map.fitBounds(bounds);
	
	// 	// Adjusting zoom here doesn't work :/
	
	// },

	smoothZoom (map, max, cnt) {
		let self = this;
		if (cnt >= max) {
			return;
		}
		else {
			z = google.maps.event.addListener(map, 'zoom_changed', function(event){
				google.maps.event.removeListener(z);
				self.smoothZoom(map, max, cnt + 1);
			});
			setTimeout(function(){map.setZoom(cnt)}, 80); // 80ms is what I found to work well on my system -- it might not work well on all systems
		}
	},

	get_google_icons() {
        return frappe.call({
            method: 'frappe.geo.utils.get_google_icons',
            args: {
                doctype: "Digital Asset",
                filters: 'googlemaps',
                type: 'googlemaps_icons'
            }
        }).then(r => {
            this.icons = r.message;
        });
    },

	custom_control(controlDiv, map) {

		// Set CSS for the control border
		var controlUI = document.createElement('div');
		controlUI.style.backgroundColor = '#fff';
		controlUI.style.borderStyle = 'solid';
		controlUI.style.borderWidth = '1px';
		controlUI.style.borderColor = '#ccc';
		controlUI.style.marginTop = '4px';
		controlUI.style.marginLeft = '-6px';
		controlUI.style.cursor = 'pointer';
		controlUI.style.textAlign = 'center';
		controlUI.title = 'Click to clear map drawer';
		controlDiv.appendChild(controlUI);

		// Set CSS for the control interior
		var controlText = document.createElement('div');
		controlText.style.fontFamily = 'Arial,sans-serif';
		controlText.style.fontSize = '9px';
		controlText.style.paddingLeft = '4px';
		controlText.style.paddingRight = '4px';
		controlText.style.paddingTop = '7px';
		controlText.style.paddingBottom = '7px';
		controlText.innerHTML = '<img src="https://cdn3.iconfinder.com/data/icons/linecons-free-vector-icons-pack/32/trash-512.png" width="14">';
		controlUI.appendChild(controlText);

		// Setup the click event listeners
		google.maps.event.addDomListener(controlUI, 'click', function () {
			var data_layers = undefined;
			self.set_value(data_layers);
		});
	},

    make_wrapper() {
		// Create the elements for map area
		this._super();
		self = this;

		let $input_wrapper = this.$wrapper.find('.control-input-wrapper');
		this.map_id = 'map';

		this.map_area = $(
			`<div class="map-wrapper border">
				<div id="` + this.map_id + `" style="min-height: 400px; z-index: 1; max-width:100%"></div>
			</div>`
		);

		this.map_area.prependTo($input_wrapper);
		this.$wrapper.find('.control-input').addClass("hidden");

		const icon = {
			url: "https://iconsplace.com/wp-content/uploads/_icons/ff0000/256/png/radio-tower-icon-14-256.png",
			scaledSize: new google.maps.Size(15, 15)
		};
	}
}); 