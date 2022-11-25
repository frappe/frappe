/**
 * frappe.views.MapView
 */
frappe.provide('frappe.utils.utils');
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

	render() {
		this.get_coords()
			.then(() => {
				this.render_map_view();
			});
		this.$paging_area.find('.level-left').append('<div></div>');
	}

	render_map_view() {
		this.map_id = frappe.dom.get_unique_id();

		this.$result.html(`<div id="${this.map_id}" class="map-view-container"></div>`);

		L.Icon.Default.imagePath = '/assets/frappe/images/leaflet/';
		this.map = L.map(this.map_id).setView(frappe.utils.map_defaults.center,
			frappe.utils.map_defaults.zoom);

		L.tileLayer(frappe.utils.map_defaults.tiles,
			frappe.utils.map_defaults.options).addTo(this.map);

		L.control.scale().addTo(this.map);
		if (this.coords.features && this.coords.features.length) {
			//custom modification in code to bind other details for doctype task
			$.each(this.coords.features, function(i, cords_data) {
				if(cords_data.properties.name.startsWith("TASK-")){
					//Getting task data 
					frappe.call({
						method: 'foxerp_madinah.api.project.get_task_details',
						args: {
							"task_name": cords_data.properties.name
						},
						async: false,
						callback: function(task_data) {
							if(task_data.message.length>0){
								cords_data.properties.project =  task_data.message[0].project_name
								cords_data.properties.name =  task_data.message[0].subject
								cords_data.properties.task_phase =  task_data.message[0].task_phase
								//cords_data.properties.project = task_data.message[0].project
							}
						}
					});

				}else{
					cords_data.properties.project = ""
					cords_data.properties.task_phase = ""
				}
			})
			
			this.coords.features.forEach(
				coords => L.geoJSON(coords).bindPopup(coords.properties.name+"<br>"+coords.properties.project+"<br>"+coords.properties.task_phase).addTo(this.map)
			);
			// end here below commented code is orignal code.
			// this.coords.features.forEach(
			// 	coords => L.geoJSON(coords).bindPopup(coords.properties.name).addTo(this.map)
			// );
			let lastCoords = this.coords.features[0].geometry.coordinates.reverse();
			this.map.panTo(lastCoords, 8);
		}
	}

	get_coords() {
		let get_coords_method = this.settings && this.settings.get_coords_method || 'frappe.geo.utils.get_coords';

		if (cur_list.meta.fields.find(i => i.fieldname === 'location' && i.fieldtype === 'Geolocation')) {
			this.type = 'location_field';
		} else if  (cur_list.meta.fields.find(i => i.fieldname === "latitude") &&
			cur_list.meta.fields.find(i => i.fieldname === "longitude")) {
			this.type = 'coordinates';
		}
		return frappe.call({
			method: get_coords_method,
			args: {
				doctype: this.doctype,
				filters: cur_list.filter_area.get(),
				type: this.type
			}
		}).then(r => {
			this.coords = r.message;

		});
	}


	get required_libs() {
		return [
			"assets/frappe/js/lib/leaflet/leaflet.css",
			"assets/frappe/js/lib/leaflet/leaflet.js"
		];
	}


};
