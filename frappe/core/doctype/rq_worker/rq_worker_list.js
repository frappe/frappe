frappe.listview_settings["RQ Worker"] = {
	refresh(listview) {
		listview.$no_result.html(`
			<div class="no-result text-muted flex justify-center align-center">
			${__("No RQ Workers connected. Try restarting the bench.")}
			</div>
		`);
	},
};
