frappe.provide('frappe.utils.utils');
frappe.provide("frappe.views");

let default_icon = "https://iconsplace.com/wp-content/uploads/_icons/ff0000/256/png/radio-tower-icon-14-256.png";

frappe.views.GooglemapsView = class GooglemapsView extends frappe.views.ListView {
    get view_name() {
        return 'Googlemaps';
    }

    setup_defaults() {
        super.setup_defaults();
        this.page_title = __('{0} Googlemaps', [this.page_title]);
    }

    setup_view() {
    }

    on_filter_change() {
        this.get_google_coords();
    }

    render() {
        this.get_google_coords()
            .then(() => {
                this.get_google_icons()
                .then(() => {
                    this.render_map_view();
                });
            });
        this.$paging_area.find('.level-left').append('<div></div>');
    }

    render_map_view() {
        self = this;
		this.map_id = 'map';
        this.$result.html(`<div id="${this.map_id}" class="map-view-container"></div>`);

        this.map = new google.maps.Map(document.getElementById("map"), {
            center: {lat:0.21901832756664624, lng:119.1115301972551},
            mapTypeId: "terrain",
            zoom: 5,
        });

        let i;
        let z;
        let y;

        if (this.coords && this.coords.length > 0) {
            for (i = 0; i < this.coords.length; i++) {
                if (this.coords[i].google_maps_location !== null) {
                    this.name = this.coords[i].name;

                    this.coorData = JSON.parse(this.coords[i].google_maps_location);
                    this.markers = this.coorData.features;

                    for (z = 0; z < this.markers.length; z++) {

                        if (this.markers[z].properties.point_type === 'marker'){
                            for (y = 0; y < this.icons.length; y++) {
                                if (this.icons[y].name1 === this.markers[z].properties.icon) {
                                    this.icon_url = this.icons[y].icon_image;
                                } else {
                                    this.icon_url = default_icon;
                                }
                            }
                            const icon = {
                                url: this.icon_url,
                                scaledSize: new google.maps.Size(15, 15)
                            };

                            this.marker = new google.maps.Marker({
                                position: new google.maps.LatLng(this.markers[z].geometry.coordinates[1], this.markers[z].geometry.coordinates[0]),
                                map: this.map,
                                icon: icon,
                            });


                            var infowindow = new google.maps.InfoWindow();
                            var markerLabel = this.markers[z].properties.name;
                            var markerPoint = this.marker;
                            google.maps.event.addListener(this.marker,'click', (function(markerPoint,markerLabel,infowindow){ 
                                return function() {
                                   infowindow.setContent(markerLabel);
                                   infowindow.open(map,markerPoint);
                                };
                            })(markerPoint,markerLabel,infowindow)); 
                        }   
                    }
                } 
            }
        }
    }

    get_google_coords() {
        let get_google_coords_method = this.settings && this.settings.get_google_coords_method || 'frappe.geo.utils.get_google_coords';

        if (cur_list.meta.fields.find(i => i.fieldtype === 'Googlemaps')) {
            this.type = 'googlemaps_coordinates';
        }


        return frappe.call({
            method: get_google_coords_method,
            args: {
                doctype: this.doctype,
                filters: cur_list.filter_area.get(),
                type: this.type
            }
        }).then(r => {
            this.coords = r.message;

        });
    }

    get_google_icons() {
        let get_google_icons_method = this.settings && this.settings.get_google_icons_method || 'frappe.geo.utils.get_google_icons';

        if (cur_list.meta.fields.find(i => i.fieldtype === 'Googlemaps')) {
            this.type = 'googlemaps_icons';
        }

        return frappe.call({
            method: get_google_icons_method,
            args: {
                doctype: "Digital Asset",
                filters: 'googlemaps',
                type: this.type
            }
        }).then(r => {
            this.icons = r.message;

        });
    }
};