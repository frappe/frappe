frappe.provide("frappe.utils");

frappe.ui.form.ControlGeolocation = class ControlGeolocation extends frappe.ui.form.ControlData {
	static horizontal = false;

	async make() {
		super.make();
		$(this.input_area).addClass("hidden");
	}

	set_disp_area(value) {
		// Create the elements for map area
		if (!this.disp_area) {
			return;
		}
		if (!this.map_id) {
			this.map_id = frappe.dom.get_unique_id();
			this.map_area = $(
				`<div class="map-wrapper border">
					<div id="${this.map_id}" style="min-height: 400px; z-index: 1; max-width:100%"></div>
				</div>`
			);

			$(this.disp_area).html(this.map_area);
		}

		// show again on idempotent invocations
		$(this.disp_area).removeClass("like-disabled-input");
		$(this.disp_area).css("display", "block");

		if (this.frm) {
			this.make_map();
			if (value) {
				this.bind_leaflet_data(value);
			}
		} else {
			$(document).on("frappe.ui.Dialog:shown", () => {
				this.make_map();
				if (value) {
					this.bind_leaflet_data(value);
				}
			});
		}
	}

	make_map(value) {
		if (!this.map) {
			this.customize_draw_controls();
			this.bind_leaflet_map();
		}
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
			if (!this.bound_event_listeners) {
				this.bind_leaflet_event_listeners();
			}
			if (!this.locate_control) {
				this.bind_leaflet_locate_control();
			}
		}
	}

	bind_leaflet_data(value) {
		/* render raw value from db into map */
		this.clear_editable_layers();

		const data_layers = new L.FeatureGroup().addLayer(
			L.geoJson(JSON.parse(value), {
				pointToLayer: this.point_to_layer,
				style: this.set_style,
				onEachFeature: this.on_each_feature,
			})
		);
		this.add_non_group_layers(data_layers, this.editableLayers);
		this.editableLayers.addTo(this.map);
		this.fit_and_recenter_map();
	}

	/**
	 * Defines custom rules for how geoJSON data is rendered on the map.
	 *
	 * Can be inherited in custom map controllers.
	 *
	 * @param {Object} geoJsonPoint - The geoJSON object to be rendered on the map.
	 * @param {Object} latlng - The latitude and longitude where the geoJSON data should be rendered on the map.
	 * @returns {Object} - Returns the Leaflet layer object to be rendered on the map.
	 */
	point_to_layer(geoJsonPoint, latlng) {
		// Custom rules for how geojson data is rendered on the map
		if (geoJsonPoint.properties.point_type == "circle") {
			return L.circle(latlng, { radius: geoJsonPoint.properties.radius });
		} else if (geoJsonPoint.properties.point_type == "circlemarker") {
			return L.circleMarker(latlng, { radius: geoJsonPoint.properties.radius });
		} else {
			return L.marker(latlng);
		}
	}

	/**
	 * Defines custom styles for how geoJSON Line and LineString data is rendered on the map.
	 *
	 * Can be inherited in custom map controllers.
	 *
	 * @param {Object} geoJsonFeature - The geoJSON object to be rendered on the map.
	 * @returns {Object} - Returns the style object for the geoJSON object.
	 */
	set_style(geoJsonFeature) {
		return {};
	}

	/**
	 * Is called after each feature is rendered and styles, can be used to attache popups, tooltips and other events
	 *
	 * Can be inherited in custom map controllers.
	 *
	 * @param {Object} feature - The leaflet object representing a geojson feature.
	 * @param {Object} layer - The leaflet layer object.
	 */
	on_each_feature(feature, layer) {}

	customize_draw_controls() {
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

		L.Icon.Default.imagePath = frappe.utils.map_defaults.image_path;
	}

	bind_leaflet_map() {
		this.map = L.map(this.map_id);
		this.map.setView(frappe.utils.map_defaults.center, frappe.utils.map_defaults.zoom);

		L.tileLayer(frappe.utils.map_defaults.tiles, frappe.utils.map_defaults.options).addTo(
			this.map
		);

		this.editableLayers = new L.FeatureGroup();
	}

	bind_leaflet_locate_control() {
		// To request location update and set location, sets current geolocation on load
		this.locate_control = L.control.locate({ position: "topright" });
		this.locate_control.addTo(this.map);
	}

	bind_leaflet_draw_control() {
		if (!this.draw_control) {
			this.draw_control = this.get_leaflet_controls();
		}
		if (this.disp_status == "Write") {
			this.draw_control.addTo(this.map);
		} else {
			this.draw_control.remove();
		}
	}

	get_leaflet_controls() {
		return new L.Control.Draw({
			position: "topleft",
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
				remove: true,
			},
		});
	}

	bind_leaflet_event_listeners() {
		this.bound_event_listeners = true;
		this.map.on("draw:created", (e) => {
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
