/**
 * frappe.views.MapView
 */
frappe.provide("frappe.views");

frappe.views.MapView = class MapView extends frappe.views.ListView {
	get view_name() {
		return 'Map';
	}

	setup_defaults() {
		super.setup_defaults();
		this.page_title = __('{0} Map', [this.page_title]);
	}

	setup_view() {
	}

	on_filter_change() {
		this.get_coords();
	}

	prepare_data(data) {
		super.prepare_data(data);
		this.items = this.data.map(d => {
			return d;
		});
	}

	render() {
		this.get_coords()
			.then(() => {
				this.render_map_view();
			});
		this.$paging_area.find('.level-left').append('<div></div>');
	}

	render_map_view() {
		this.map_id = frappe.dom.get_unique_id();

		this.$result.html(`
			<div id="` + this.map_id + `" class="map-view-container"  style="width: 100%;height: calc(100vh - 284px); z-index: 0;">
				
			</div>
		`);


		this.map = L.map(this.map_id).setView([12.3112899, -85.7384542], 8); //coords of India if markers does not exists

		L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
			attribution: '&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors',
			maxZoom: 18
		}).addTo(this.map);

		L.control.scale().addTo(this.map);

		let lastCoords = [];
		for (const [key, value] of Object.entries(this.coords_map)) {
			new L.marker([value[0], value[1]])
				.bindPopup(key)
				.addTo(this.map);
			lastCoords = [value[0], value[1]];
		}
		this.map.panTo(lastCoords, 8);


	}

	get_coords() {
		let get_coords_method;
		if (JSON.stringify(frappe.listview_settings) === '{}') {
			get_coords_method = 'frappe.geo.utils.get_coords';
		} else {
			get_coords_method = frappe.listview_settings[this.doctype].get_coords_method;
		}
		console.log(cur_list.filter_area);
		return frappe.call({
			method: get_coords_method,
			args: {
				doctype: this.doctype,
				filters: cur_list.filter_area.get()
			}
		}).then(r => {
			this.coords_map = Object.assign(r.message);

		});
	}


	get required_libs() {
		return [
			"assets/frappe/js/lib/leaflet/leaflet.css",
			"assets/frappe/js/lib/leaflet/leaflet.js"
		];
	}


};
