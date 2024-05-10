import { createApp } from "vue";
import BuildError from "./BuildError.vue";
import BuildSuccess from "./BuildSuccess.vue";

let $container = $("#build-events-overlay");
let success = null;
let error = null;

frappe.realtime.on("build_event", (data) => {
	if (data.success) {
		// remove executed cache for rebuilt files
		let changed_files = data.changed_files;
		if (Array.isArray(changed_files)) {
			for (let file of changed_files) {
				if (file.includes(".bundle.")) {
					let parts = file.split(".bundle.");
					if (parts.length === 2) {
						let filename = parts[0].split("/").slice(-1)[0];

						frappe.assets._executed = frappe.assets._executed.filter(
							(asset) => !asset.includes(`${filename}.bundle`)
						);
					}
				}
			}
		}
		// update assets json
		frappe.call("frappe.sessions.get_boot_assets_json").then((r) => {
			if (r.message) {
				frappe.boot.assets_json = r.message;

				if (frappe.hot_update) {
					frappe.hot_update.forEach((callback) => {
						callback();
					});
				}
			}
		});
		show_build_success(data);
	} else if (data.error) {
		show_build_error(data);
	}
});

function show_build_success(data) {
	if (error) {
		error.hide();
	}

	if (!success) {
		let target = $('<div class="build-success-container">').appendTo($container).get(0);
		success = createApp(BuildSuccess).mount(target);
	}
	success.show(data);
}

function show_build_error(data) {
	if (success) {
		success.hide();
	}
	if (!error) {
		let target = $('<div class="build-error-container">').appendTo($container).get(0);
		error = createApp(BuildError).mount(target);
	}
	error.show(data);
}
