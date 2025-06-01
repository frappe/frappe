nts.listview_settings["Event"] = {
	add_fields: ["starts_on", "ends_on"],
	onload: function () {
		nts.route_options = {
			status: "Open",
		};
	},
};
