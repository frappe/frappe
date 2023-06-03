frappe.provide("frappe.utils.utils");

frappe.ui.form.ControlGeolocation = class ControlGeolocation extends frappe.ui.form.ControlData {
	static horizontal = false;

	async make() {
		super.make();
		$(this.input_area).addClass("hidden");
	}

	set_disp_area(value) {
		// Create the elements for map area
<<<<<<< HEAD
<<<<<<< HEAD
		super.make_wrapper();

		let $input_wrapper = this.$wrapper.find(".control-input-wrapper");
=======
		if (!this.disp_area) return;
		
>>>>>>> 5171d6edc9 (feat: read-only geolocation (GDE-86))
=======
		if (!this.disp_area) {
			return;
		}

>>>>>>> d6edc1530e (refactor: const instead of var, indentation)
		this.map_id = frappe.dom.get_unique_id();
		this.map_area = $(
			`<div class="map-wrapper border">
				<div id="${this.map_id}" style="min-height: 400px; z-index: 1; max-width:100%"></div>
			</div>`
		);
<<<<<<< HEAD
		this.map_area.prependTo($input_wrapper);
		this.$wrapper.find(".control-input").addClass("hidden");
=======

		$(this.disp_area).html(this.map_area);
		$(this.disp_area).removeClass("like-disabled-input");
		$(this.disp_area).css("display", "block");
>>>>>>> 5171d6edc9 (feat: read-only geolocation (GDE-86))

		if (this.frm) {
			this.make_map(value);
		} else {
<<<<<<< HEAD
			$(document).on("frappe.ui.Dialog:shown", () => {
				this.make_map();
=======
			$(document).on('frappe.ui.Dialog:shown', () => {
				this.make_map(value);
>>>>>>> 5171d6edc9 (feat: read-only geolocation (GDE-86))
			});
		}
	}

	make_map(value) {
		this.bind_leaflet_map();
<<<<<<< HEAD
		this.bind_leaflet_draw_control();
		this.bind_leaflet_event_listeners();
		this.bind_leaflet_locate_control();
<<<<<<< HEAD
		this.bind_leaflet_refresh_button();
		this.map.setView(frappe.utils.map_defaults.center, frappe.utils.map_defaults.zoom);
=======
		this.bind_leaflet_data(value);
>>>>>>> 5171d6edc9 (feat: read-only geolocation (GDE-86))
=======
		if (this.disabled) {
			this.map.dragging.disable();
			this.map.touchZoom.disable();
			this.map.doubleClickZoom.disable();
			this.map.scrollWheelZoom.disable();
			this.map.boxZoom.disable();
			this.map.keyboard.disable();
			this.map.zoomControl.remove();
		} else {
			this.bind_leaflet_draw_control();
			this.bind_leaflet_event_listeners();
			this.bind_leaflet_locate_control();
			this.bind_leaflet_data(value);
		}
>>>>>>> d6edc1530e (refactor: const instead of var, indentation)
	}

	bind_leaflet_data(value) {
		/* render raw value from db into map */
		if (!this.map || !value) {
			return;
		}
		this.clear_editable_layers();
<<<<<<< HEAD
		if (value) {
			var data_layers = new L.FeatureGroup().addLayer(
				L.geoJson(JSON.parse(value), {
					pointToLayer: function (geoJsonPoint, latlng) {
						if (geoJsonPoint.properties.point_type == "circle") {
							return L.circle(latlng, { radius: geoJsonPoint.properties.radius });
						} else if (geoJsonPoint.properties.point_type == "circlemarker") {
							return L.circleMarker(latlng, {
								radius: geoJsonPoint.properties.radius,
							});
						} else {
							return L.marker(latlng);
						}
					},
				})
			);
			this.add_non_group_layers(data_layers, this.editableLayers);
			try {
				this.map.fitBounds(this.editableLayers.getBounds(), {
					padding: [50, 50],
				});
			} catch (err) {
				// suppress error if layer has a point.
			}
			this.editableLayers.addTo(this.map);
		} else {
			this.map.setView(frappe.utils.map_defaults.center, frappe.utils.map_defaults.zoom);
=======

		const data_layers = new L.FeatureGroup().addLayer(
			L.geoJson(JSON.parse(value), {
				pointToLayer: function (geoJsonPoint, latlng) {
					if (geoJsonPoint.properties.point_type == "circle") {
						return L.circle(latlng, { radius: geoJsonPoint.properties.radius });
					} else if (geoJsonPoint.properties.point_type == "circlemarker") {
						return L.circleMarker(latlng, { radius: geoJsonPoint.properties.radius });
					} else {
						return L.marker(latlng);
					}
				},
			})
		);
		this.add_non_group_layers(data_layers, this.editableLayers);
<<<<<<< HEAD
		try {
			this.map.fitBounds(this.editableLayers.getBounds(), {
				padding: [50, 50],
			});
<<<<<<< HEAD
>>>>>>> 5171d6edc9 (feat: read-only geolocation (GDE-86))
		}
		catch(err) {
=======
		} catch (err) {
>>>>>>> d6edc1530e (refactor: const instead of var, indentation)
			// suppress error if layer has a point.
		}
=======
>>>>>>> 79aaf072bd (fix: fit and recenter map when section is expanded)
		this.editableLayers.addTo(this.map);
		this.fit_and_recenter_map();
	}

	bind_leaflet_map() {
		const circleToGeoJSON = L.Circle.prototype.toGeoJSON;
		L.Circle.include({
			toGeoJSON: function () {
				const feature = circleToGeoJSON.call(this);
				feature.properties = {
					point_type: "circle",
					radius: this.getRadius(),
				};
				return feature;
			},
		});

		L.CircleMarker.include({
			toGeoJSON: function () {
				const feature = circleToGeoJSON.call(this);
				feature.properties = {
					point_type: "circlemarker",
					radius: this.getRadius(),
				};
				return feature;
			},
		});

		L.Icon.Default.imagePath = "/assets/frappe/images/leaflet/";
		this.map = L.map(this.map_id);
		this.map.setView(frappe.utils.map_defaults.center, frappe.utils.map_defaults.zoom);

<<<<<<< HEAD
		L.tileLayer(frappe.utils.map_defaults.tiles, frappe.utils.map_defaults.options).addTo(
			this.map
		);
<<<<<<< HEAD
=======
		L.tileLayer(frappe.utils.map_defaults.tiles,
			frappe.utils.map_defaults.options).addTo(this.map);

		this.editableLayers = new L.FeatureGroup();
>>>>>>> 5171d6edc9 (feat: read-only geolocation (GDE-86))
=======

		this.editableLayers = new L.FeatureGroup();
>>>>>>> d6edc1530e (refactor: const instead of var, indentation)
	}

	bind_leaflet_locate_control() {
		// To request location update and set location, sets current geolocation on load
		this.locate_control = L.control.locate({ position: "topright" });
		this.locate_control.addTo(this.map);
	}

	bind_leaflet_draw_control() {
		if (
			!frappe.perm.has_perm(this.doctype, this.df.permlevel, "write", this.doc) ||
			this.df.read_only
		) {
			return;
		}

<<<<<<< HEAD
		var options = {
			position: "topleft",
=======
		this.map.addControl(this.get_leaflet_controls());
	}

	get_leaflet_controls() {
		return new L.Control.Draw({
			position: 'topleft',
>>>>>>> 5171d6edc9 (feat: read-only geolocation (GDE-86))
			draw: {
				polyline: {
					shapeOptions: {
						color: frappe.ui.color.get("blue"),
						weight: 10,
					},
				},
				polygon: {
					allowIntersection: false, // Restricts shapes to simple polygons
					drawError: {
						color: frappe.ui.color.get("orange"), // Color the shape will turn when intersects
						message: "<strong>Oh snap!<strong> you can't draw that!", // Message that will show when intersect
					},
					shapeOptions: {
						color: frappe.ui.color.get("blue"),
					},
				},
				circle: true,
				rectangle: {
					shapeOptions: {
						clickable: false,
					},
				},
			},
			edit: {
				featureGroup: this.editableLayers, //REQUIRED!!
<<<<<<< HEAD
<<<<<<< HEAD
				remove: true,
			},
		};

		// create control and add to map
		this.drawControl = new L.Control.Draw(options);
		this.map.addControl(this.drawControl);

		this.map.on("draw:created", (e) => {
=======
				remove: true
			}
=======
				remove: true,
			},
>>>>>>> d6edc1530e (refactor: const instead of var, indentation)
		});
	}

	bind_leaflet_event_listeners() {
<<<<<<< HEAD
		this.map.on('draw:created', (e) => {
>>>>>>> 5171d6edc9 (feat: read-only geolocation (GDE-86))
=======
		this.map.on("draw:created", (e) => {
>>>>>>> d6edc1530e (refactor: const instead of var, indentation)
			var type = e.layerType,
				layer = e.layer;
			if (type === "marker") {
				layer.bindPopup("Marker");
			}
			this.editableLayers.addLayer(layer);
			this.set_value(JSON.stringify(this.editableLayers.toGeoJSON()));
		});

		this.map.on("draw:deleted draw:edited", (e) => {
			const { layer } = e;
			this.editableLayers.removeLayer(layer);
			this.set_value(JSON.stringify(this.editableLayers.toGeoJSON()));
		});
	}

<<<<<<< HEAD
	bind_leaflet_refresh_button() {
		L.easyButton({
			id: "refresh-map-" + this.df.fieldname,
			position: "topright",
			type: "replace",
			leafletClasses: true,
			states: [
				{
					stateName: "refresh-map",
					onClick: function (button, map) {
						map._onResize();
					},
					title: "Refresh map",
					icon: "fa fa-refresh",
				},
			],
		}).addTo(this.map);
	}

=======
>>>>>>> 5171d6edc9 (feat: read-only geolocation (GDE-86))
	add_non_group_layers(source_layer, target_group) {
		// https://gis.stackexchange.com/a/203773
		// Would benefit from https://github.com/Leaflet/Leaflet/issues/4461
		if (source_layer instanceof L.LayerGroup) {
			source_layer.eachLayer((layer) => {
				this.add_non_group_layers(layer, target_group);
			});
		} else {
			target_group.addLayer(source_layer);
		}
	}

	clear_editable_layers() {
		this.editableLayers.eachLayer((l) => {
			this.editableLayers.removeLayer(l);
		});
	}

	fit_and_recenter_map() {
		// Spread map across the wrapper, recenter and zoom w.r.t bounds
		try {
			this.map.invalidateSize();
			this.map.fitBounds(this.editableLayers.getBounds(), {
				padding: [50, 50],
			});
		} catch (err) {
			// suppress error if layer has a point.
		}
	}

	on_section_collapse(hide) {
		!hide && this.fit_and_recenter_map();
	}
};
