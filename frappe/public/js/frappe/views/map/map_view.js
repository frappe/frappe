/**
 * nts.views.MapView
 */
nts.provide("nts.utils");
nts.provide("nts.views");

nts.views.MapView = class MapView extends nts.views.ListView {
	get view_name() {
		return "Map";
	}

	setup_defaults() {
		this.hide_sort_selector = true;
		super.setup_defaults();
		this.page_title = __("{0} Map", [this.page_title]);
	}

	setup_view() {
		this.map_id = nts.dom.get_unique_id();
		this.$result.html(`<div id="${this.map_id}" class="map-view-container"></div>`);

		L.Icon.Default.imagePath = nts.utils.map_defaults.image_path;
		this.map = L.map(this.map_id).setView(
			nts.utils.map_defaults.center,
			nts.utils.map_defaults.zoom
		);

		L.tileLayer(nts.utils.map_defaults.tiles, nts.utils.map_defaults.options).addTo(
			this.map
		);

		this.bind_leaflet_locate_control();
		L.control.scale().addTo(this.map);
	}

	render() {
		this.get_coords().then(() => {
			this.render_map_data();
		});
		this.$paging_area.find(".level-left").append("<div></div>");
	}

	render_map_data() {
		// Clear existing markers
		if (this.markerLayer) {
			this.map.removeLayer(this.markerLayer);
		}

		if (this.coords.features && this.coords.features.length) {
			this.markerLayer = L.featureGroup();

			this.coords.features.forEach((coords) => {
				const marker = L.geoJSON(coords).bindPopup(
					nts.utils.get_form_link(this.doctype, coords.properties.name, true)
				);
				this.markerLayer.addLayer(marker);
			});

			this.markerLayer.addTo(this.map);

			// Fit bounds to show all markers
			this.map.fitBounds(this.markerLayer.getBounds());
		}
	}

	get_coords() {
		let get_coords_method =
			(this.settings && this.settings.get_coords_method) || "nts.geo.utils.get_coords";

		if (
			cur_list.meta.fields.find(
				(i) => i.fieldname === "location" && i.fieldtype === "Geolocation"
			)
		) {
			this.type = "location_field";
		} else if (
			cur_list.meta.fields.find((i) => i.fieldname === "latitude") &&
			cur_list.meta.fields.find((i) => i.fieldname === "longitude")
		) {
			this.type = "coordinates";
		}
		return nts
			.call({
				method: get_coords_method,
				args: {
					doctype: this.doctype,
					filters: cur_list.filter_area.get(),
					type: this.type,
				},
			})
			.then((r) => {
				this.coords = r.message;
			});
	}

	bind_leaflet_locate_control() {
		// To request location update and set location, sets current geolocation on load
		this.locate_control = L.control.locate({ position: "topright" });
		this.locate_control.addTo(this.map);
	}
};
