frappe.provide('frappe.utils.utils');
frappe.provide("frappe.views");

let default_icon_url = "https://iconsplace.com/wp-content/uploads/_icons/ff0000/256/png/radio-tower-icon-14-256.png";

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
        this.$result.html(`<input id="pac-input" class="controls" type="text" placeholder="Search" /><div id="${this.map_id}" class="map-view-container"></div>`);

        this.map = new google.maps.Map(document.getElementById("map"), {
            center: { lat: 0.21901832756664624, lng: 119.1115301972551 },
            mapTypeId: "terrain",
            zoom: 5,
        });

        this.input = document.getElementById("pac-input");
        this.searchBox = new google.maps.places.SearchBox(this.input);

        const locationButton = document.createElement("button");

        locationButton.innerHTML = "<img src='https://img.icons8.com/color/30/000000/place-marker--v1.png'/>";

        locationButton.classList.add("custom-map-control-button");

        this.map.controls[google.maps.ControlPosition.TOP_LEFT].push(locationButton);


        locationButton.addEventListener("click", () => {
            let map = this.map
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
                        this.map.setCenter(pos);
                        this.map.setZoom(16)
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



        this.map.controls[google.maps.ControlPosition.TOP_CENTER].push(this.input);

        this.map.addListener("bounds_changed", () => {
            this.searchBox.setBounds(this.map.getBounds());
        });

        let markers = []

        this.searchBox.addListener("places_changed", () => {
            const places = this.searchBox.getPlaces();

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

                let map = this.map

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
            this.map.fitBounds(bounds);
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

                        if (this.markers[z].properties.point_type === 'marker') {
                            this.icon_url = default_icon_url;
                            for (y = 0; y < this.icons.length; y++) {
                                if (this.icons[y].name1 === this.markers[z].properties.icon) {
                                    this.icon_url = this.icons[y].icon_image;
                                }
                            }
                            const icon = {
                                url: this.icon_url,
                                scaledSize: new google.maps.Size(30, 30)
                            };

                            this.marker = new google.maps.Marker({
                                position: new google.maps.LatLng(this.markers[z].geometry.coordinates[1], this.markers[z].geometry.coordinates[0]),
                                map: this.map,
                                icon: icon,
                            });


                            var infowindow = new google.maps.InfoWindow();

                            var markerLabel = this.markers[z].properties.name

                            var markerPoint = this.marker;
                            let map = this.map

                            google.maps.event.addListener(this.marker, 'click', (function (markerPoint, markerLabel, infowindow) {
                                return function () {
                                    this.map.panTo(this.getPosition())
                                    this.map.setZoom(16)
                                    setTimeout(() => {
                                        infowindow.setContent(markerLabel);
                                        infowindow.open(map, markerPoint);
                                    }, 500)
                                };
                            })(markerPoint, markerLabel, infowindow));

                            google.maps.event.addListener(this.marker, 'mouseover', (function (markerPoint, markerLabel, infowindow) {
                                return function () {
                                    infowindow.setContent(markerLabel);
                                    infowindow.open(map, markerPoint);
                                };
                            })(markerPoint, markerLabel, infowindow));

                            google.maps.event.addListener(this.marker, 'mouseout', (function (markerPoint, markerLabel, infowindow) {
                                return function () {
                                    infowindow.close();
                                };
                            })(markerPoint, markerLabel, infowindow));
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

    handleLocationError(browserHasGeolocation, infowindow, pos) {
        infowindow.setPosition(pos);
        infowindow.setContent(
            browserHasGeolocation
                ? "Error: The Geolocation service failed."
                : "Error: Your browser doesn't support geolocation."
        );
        infowindow.open(map);
    }
};