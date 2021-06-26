import BuildError from "./BuildError.vue";
import BuildSuccess from "./BuildSuccess.vue";

let $container = $("#build-events-overlay");
let success = null;
let error = null;

frappe.realtime.on("build_event", data => {
	if (data.success) {
		show_build_success(data);
	} else if (data.error) {
		show_build_error(data);
	}
});

function show_build_success() {
	if (error) {
		error.hide();
	}
	if (!success) {
		let target = $('<div class="build-success-container">')
			.appendTo($container)
			.get(0);
		let vm = new Vue({
			el: target,
			render: h => h(BuildSuccess)
		});
		success = vm.$children[0];
	}
	success.show();
}

function show_build_error(data) {
	if (success) {
		success.hide();
	}
	if (!error) {
		let target = $('<div class="build-error-container">')
			.appendTo($container)
			.get(0);
		let vm = new Vue({
			el: target,
			render: h => h(BuildError)
		});
		error = vm.$children[0];
	}
	error.show(data);
}
