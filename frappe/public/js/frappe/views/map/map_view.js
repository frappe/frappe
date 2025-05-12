/**
 * frappe.views.MapView
 */
frappe.provide("frappe.utils");
frappe.provide("frappe.views");

frappe.views.MapView = class MapView extends frappe.views.ListView {
	get view_name() {
		return "Map";
	}

	setup_defaults() {
		super.setup_defaults();
		this.page_title = __("{0} Map", [this.page_title]);
		this.setup_map_type();
	}

	setup_map_type() {
		if (
			this.meta.fields.find(
				(i) => i.fieldname === "location" && i.fieldtype === "Geolocation"
			)
		) {
			this.type = "location_field";
			this._add_field("location");
		} else if (
			this.meta.fields.find((i) => i.fieldname === "latitude") &&
			this.meta.fields.find((i) => i.fieldname === "longitude")
		) {
			this.type = "coordinates";
			this._add_field("latitude");
			this._add_field("longitude");
		}
	}

	setup_view() {
		this.map_id = frappe.dom.get_unique_id();
		this.$result.html(`<div id="${this.map_id}" class="map-view-container"></div>`);

		L.Icon.Default.imagePath = frappe.utils.map_defaults.image_path;
		this.map = L.map(this.map_id).setView(
			frappe.utils.map_defaults.center,
			frappe.utils.map_defaults.zoom
		);

		L.tileLayer(frappe.utils.map_defaults.tiles, frappe.utils.map_defaults.options).addTo(
			this.map
		);

		this.bind_leaflet_locate_control();
		L.control.scale().addTo(this.map);
	}

	render() {
		const coords = this.convert_to_geojson(this.data);
		this.render_map_data(coords);
		this.$paging_area.find(".level-left").append("<div></div>");
	}

	convert_to_geojson(data) {
		return this.type === "location_field"
			? this.get_location_data(data)
			: this.get_coordinates_data(data);
	}

	get_coordinates_data(data) {
		return data.map((row) => this.create_gps_marker(row)).filter(Boolean);
	}

	get_location_data(data) {
		return data.reduce((acc, row) => {
			const location = this.parse_location_field(row);
			if (location) {
				acc.push(...location);
			}
			return acc;
		}, []);
	}

	get_feature_properties(row) {
		return {
			name: row.name,
		};
	}

	parse_location_field(row) {
		const location = JSON.parse(row["location"]);
		if (!location) {
			return;
		}

		for (const feature of location["features"]) {
			feature["properties"] = {
				...(feature["properties"] || {}),
				...this.get_feature_properties(row),
			};
		}

		return location["features"];
	}

	create_gps_marker(row) {
		// Build marker based on latitude and longitude
		if (!row.latitude || !row.longitude) {
			return;
		}

		return {
			type: "Feature",
			properties: this.get_feature_properties(row),
			geometry: {
				type: "Point",
				coordinates: [parseFloat(row.longitude), parseFloat(row.latitude)], // geojson needs it reverse!
			},
		};
	}

	get_popup_content(feature) {
		return frappe.utils.get_form_link(this.doctype, feature.properties.name, true);
	}

	render_map_data(features) {
		// Clear existing markers
		if (this.markerLayer) {
			this.map.removeLayer(this.markerLayer);
		}

		if (features && features.length) {
			this.markerLayer = L.featureGroup();

			features.forEach((feature) => {
				const marker = L.geoJSON(feature).bindPopup(this.get_popup_content(feature));
				this.markerLayer.addLayer(marker);
			});

			this.markerLayer.addTo(this.map);

			// Fit bounds to show all markers
			this.map.fitBounds(this.markerLayer.getBounds());
		}
	}

	bind_leaflet_locate_control() {
		// To request location update and set location, sets current geolocation on load
		this.locate_control = L.control.locate({ position: "topright" });
		this.locate_control.addTo(this.map);
	}
};
