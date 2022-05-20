frappe.provide('frappe.utils.utils');
let marker;
let i;
let z;
let default_icon_url = "https://iconsplace.com/wp-content/uploads/_icons/ff0000/256/png/radio-tower-icon-14-256.png";
let markers = []

frappe.ui.form.ControlGooglemaps = frappe.ui.form.ControlData.extend({
	horizontal: false,

	format_for_input(value, docstatus = 0) {
		this.get_google_icons()
			.then(() => {
				this.render_map(value, docstatus)
			});
	},

	render_map(value, docstatus = 0) {
		self = this


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
				scaledSize: new google.maps.Size(30, 30)
			};

			// list of markers
			var points = this.objValue.features.filter(function (ele) {
				return ele.properties.point_type === "marker";
			});


			// list of circles
			var circle = this.objValue.features.filter(function (ele) {
				return ele.properties.point_type === "circle";
			});

			if (points.length > 0) {




				//create dafult map
				let map = new google.maps.Map(document.getElementById(this.map_id), {
					zoom: 8,
					mapTypeId: "terrain",
					center: { lat: -6.321916245621676, lng: 106.67620042320505 }
				});

				let searchInput = document.createElement("input");
				searchInput.id = "pac-input"
				searchInput.type = "text";
				searchInput.placeholder = "Search"
				searchInput.className = "controls"; // set the CSS class

				document.body.appendChild(searchInput); // put it into the DOM


				let input = document.getElementById("pac-input");
				let searchBox = new google.maps.places.SearchBox(input);

				const locationButton = document.createElement("button");

				locationButton.innerHTML = "<img src='https://img.icons8.com/color/30/000000/place-marker--v1.png'/>";

				locationButton.classList.add("custom-map-control-button");

				map.controls[google.maps.ControlPosition.TOP_LEFT].push(locationButton);

				locationButton.addEventListener("click", () => {

					// Try HTML5 geolocation.
					if (navigator.geolocation) {
						navigator.geolocation.getCurrentPosition(
							(position) => {
								const pos = {
									lat: position.coords.latitude,
									lng: position.coords.longitude,
								};

								new google.maps.Marker({
									map,
									animation: google.maps.Animation.DROP,
									position: pos,
								})
								// infowindow.setPosition(pos);
								// infowindow.setContent("Location found.");
								// infowindow.open(this.map);
								map.setCenter(pos);
								map.setZoom(16)
							},
							() => {
								handleLocationError(true, infowindow, this.map.getCenter());
							}
						);
					} else {
						// Browser doesn't support Geolocation
						handleLocationError(false, infowindow, this.map.getCenter());
					}
				});



				map.controls[google.maps.ControlPosition.TOP_CENTER].push(input);

				map.addListener("bounds_changed", () => {
					searchBox.setBounds(map.getBounds());
				});

				searchBox.addListener("places_changed", () => {
					const places = searchBox.getPlaces();

					if (places.length == 0) {
						return;
					}

					// Clear out the old markers.
					markers.forEach((marker) => {
						marker.setMap(null);
					});
					markers = [];

					// For each place, get the icon, name and location.
					const bounds = new google.maps.LatLngBounds();

					places.forEach((place) => {
						if (!place.geometry || !place.geometry.location) {
							console.log("Returned place contains no geometry");
							return;
						}

						const icon = {
							url: place.icon,
							size: new google.maps.Size(71, 71),
							origin: new google.maps.Point(0, 0),
							anchor: new google.maps.Point(17, 34),
							scaledSize: new google.maps.Size(25, 25),
						};



						// Create a marker for each place.
						markers.push(
							new google.maps.Marker({
								map,
								icon,
								title: place.name,
								position: place.geometry.location,
							})
						);
						if (place.geometry.viewport) {
							// Only geocodes have viewport.
							bounds.union(place.geometry.viewport);
						} else {
							bounds.extend(place.geometry.location);
						}
					});
					map.fitBounds(bounds);
				});


				for (i = 0; i < points.length; i++) {
					this.icon_url = default_icon_url;
					for (z = 0; z < this.icons.length; z++) {
						if (points[i].properties.icon === this.icons[z].name1) {
							this.icon_url = this.icons[z].icon_image;
							break;
						}
					}

					// set icon for gmaps
					const icon = {
						url: this.icon_url,
						scaledSize: new google.maps.Size(30, 30)
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
					google.maps.event.addListener(marker, 'click', (function (marker, markerLabel, infowindow) {
						return function () {
							infowindow.setContent(markerLabel);
							infowindow.open(map, marker);
						};
					})(marker, markerLabel, infowindow));
					bounds.extend(marker.position);
				}

				if (circle.length > 0) {
					for (i = 0; i < circle.length; i++) {
						const cityCircle = new google.maps.Circle({
							fillColor: "rgb(51, 136, 255)",
							fillOpacity: 0.2,
							strokeWeight: 1,
							strokeColor: "rgb(51, 136, 255)",
							clickable: false,
							zIndex: 1,
							map,
							center: { lng: circle[i].geometry.coordinates[0], lat: circle[i].geometry.coordinates[1] },
							radius: circle[i].properties.radius
						});
					}
				}

				this.getMarkersCenter(markers);
				map.setCenter(new google.maps.LatLng(
					this.markersCenter.lat,
					this.markersCenter.lng
				));

				if (this.markersZoom > 15) {
					this.markersZoom = 15;
				}
				map.setZoom(this.markersZoom + 1);

				// this.smoothZoom(map, this.markersZoom, map.getZoom()); // call smoothZoom, parameters map, final zoomLevel, and starting zoom level

				if (docstatus === 1) {
					this.drawingManager = new google.maps.drawing.DrawingManager({
						// drawingMode: google.maps.drawing.OverlayType.MARKER,
						drawingControl: false,
						drawingControlOptions: {
							position: google.maps.ControlPosition.TOP_CENTER,
							drawingModes: [
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
							zIndex: 1,
						},
					});
				} else {
					this.drawingManager = new google.maps.drawing.DrawingManager({
						// drawingMode: google.maps.drawing.OverlayType.MARKER,
						drawingControl: false,
						drawingControlOptions: {
							position: google.maps.ControlPosition.TOP_CENTER,
							drawingModes: [
								// google.maps.drawing.OverlayType.MARKER,
								// google.maps.drawing.OverlayType.CIRCLE,
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
							zIndex: 1,
						},
					});
				}
				this.drawingManager.setMap(map);

				google.maps.event.addListener(this.drawingManager, 'overlaycomplete', function (event) {
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
		} else if (value === undefined || value === "") {
			const icon = {
				url: "https://iconsplace.com/wp-content/uploads/_icons/ff0000/256/png/radio-tower-icon-14-256.png",
				scaledSize: new google.maps.Size(30, 30)
			};

			let map = new google.maps.Map(document.getElementById(this.map_id), {
				zoom: 13,
				center: { lat: -6.304551452226169, lng: 106.68479307871746 },
				mapTypeId: "terrain",
			});

			let searchInput = document.createElement("input");
			searchInput.id = "pac-input"
			searchInput.type = "text";
			searchInput.placeholder = "Search"
			searchInput.className = "controls"; // set the CSS class

			document.body.appendChild(searchInput); // put it into the DOM


			let input = document.getElementById("pac-input");
			let searchBox = new google.maps.places.SearchBox(input);

			const locationButton = document.createElement("button");

			locationButton.innerHTML = "<img src='https://img.icons8.com/color/30/000000/place-marker--v1.png'/>";

			locationButton.classList.add("custom-map-control-button");

			map.controls[google.maps.ControlPosition.TOP_LEFT].push(locationButton);

			locationButton.addEventListener("click", () => {

				// Try HTML5 geolocation.
				if (navigator.geolocation) {
					navigator.geolocation.getCurrentPosition(
						(position) => {
							const pos = {
								lat: position.coords.latitude,
								lng: position.coords.longitude,
							};

							new google.maps.Marker({
								map,
								animation: google.maps.Animation.DROP,
								position: pos,
							})
							// infowindow.setPosition(pos);
							// infowindow.setContent("Location found.");
							// infowindow.open(this.map);
							map.setCenter(pos);
							map.setZoom(16)
						},
						() => {
							handleLocationError(true, infowindow, this.map.getCenter());
						}
					);
				} else {
					// Browser doesn't support Geolocation
					handleLocationError(false, infowindow, this.map.getCenter());
				}
			});



			map.controls[google.maps.ControlPosition.TOP_CENTER].push(input);

			map.addListener("bounds_changed", () => {
				searchBox.setBounds(map.getBounds());
			});

			searchBox.addListener("places_changed", () => {
				const places = searchBox.getPlaces();

				if (places.length == 0) {
					return;
				}

				// Clear out the old markers.
				markers.forEach((marker) => {
					marker.setMap(null);
				});
				markers = [];

				// For each place, get the icon, name and location.
				const bounds = new google.maps.LatLngBounds();

				places.forEach((place) => {
					if (!place.geometry || !place.geometry.location) {
						console.log("Returned place contains no geometry");
						return;
					}

					const icon = {
						url: place.icon,
						size: new google.maps.Size(71, 71),
						origin: new google.maps.Point(0, 0),
						anchor: new google.maps.Point(17, 34),
						scaledSize: new google.maps.Size(25, 25),
					};



					// Create a marker for each place.
					markers.push(
						new google.maps.Marker({
							map,
							icon,
							title: place.name,
							position: place.geometry.location,
						})
					);
					if (place.geometry.viewport) {
						// Only geocodes have viewport.
						bounds.union(place.geometry.viewport);
					} else {
						bounds.extend(place.geometry.location);
					}
				});
				map.fitBounds(bounds);
			});

			if (docstatus === 1) {
				this.drawingManager = new google.maps.drawing.DrawingManager({
					// drawingMode: google.maps.drawing.OverlayType.MARKER,
					drawingControl: false,
					drawingControlOptions: {
						position: google.maps.ControlPosition.TOP_CENTER,
						drawingModes: [
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
						zIndex: 1,
					},
				});
			} else {
				this.drawingManager = new google.maps.drawing.DrawingManager({
					// drawingMode: google.maps.drawing.OverlayType.MARKER,
					drawingControl: false,
					drawingControlOptions: {
						position: google.maps.ControlPosition.TOP_CENTER,
						drawingModes: [
							// google.maps.drawing.OverlayType.MARKER,
							// google.maps.drawing.OverlayType.CIRCLE
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
						zIndex: 1,
					},
				});
			}
			this.drawingManager.setMap(map);

			google.maps.event.addListener(this.drawingManager, 'overlaycomplete', function (event) {
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

	getZoomLevel(lngMin, lngMax) {
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
		this.markersCenter = { lat: ((latMax + latMin) / 2.0), lng: ((lngMax + lngMin) / 2.0) }
		this.getZoomLevel(lngMin, lngMax)
	},

	// smoothZoom (map, max, cnt) {
	// 	let self = this;
	// 	if (cnt >= max) {
	// 		return;
	// 	}
	// 	else {
	// 		z = google.maps.event.addListener(map, 'zoom_changed', function(event){
	// 			google.maps.event.removeListener(z);
	// 			self.smoothZoom(map, max, cnt + 1);
	// 		});
	// 		setTimeout(function(){map.setZoom(cnt)}, 80);
	// 	}
	// },

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

	make_wrapper() {
		// Create the elements for map area
		this._super();
		self = this;
		// this.$result.html(`<input id="pac-input" class="controls" type="text" placeholder="Search" /><div id="${this.map_id}" class="map-view-container"></div>`);


		let $input_wrapper = this.$wrapper.find('.control-input-wrapper');

		this.map_id = frappe.dom.get_unique_id();;

		this.map_area = $(
			`<div class="map-wrapper border">
				<div id="` + this.map_id + `" style="min-height: 400px; z-index: 1; max-width:100%"></div>
			</div>`
		);

		this.map_area.prependTo($input_wrapper);
		this.$wrapper.find('.control-input').addClass("hidden");



		const icon = {
			url: "https://iconsplace.com/wp-content/uploads/_icons/ff0000/256/png/radio-tower-icon-14-256.png",
			scaledSize: new google.maps.Size(30, 30)
		};

		if (this.frm.doc.docstatus === 1) {
			this.format_for_input(this.frm.doc.google_maps_location, this.frm.doc.docstatus)
			this.$wrapper.find(".like-disabled-input").addClass("hidden");
		}
	}
}); 