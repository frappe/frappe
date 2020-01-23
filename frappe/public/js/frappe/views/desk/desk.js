export default class Desk {
	constructor({ wrapper }) {
		this.wrapper = wrapper;
		this.make();
	}

	make() {
		this.make_container();
		this.show_loading_state();
		this.fetch_desktop_settings().then(() => {
			this.make_sidebar();
			this.make_body();
			this.setup_events;
			this.hide_loading_state();
		});
	}

	make_container() {
		this.container = $(`<div class="desk-container row">
			<div class="desk-sidebar" style="height: 90vh;">
				<div class="skeleton skeleton-full"></div>
			</div>
			<div class="desk-body" style="height: 90vh;">
				<div class="skeleton skeleton-3"></div>
				<div class="skeleton skeleton-30"></div>
				<div class="skeleton skeleton-10"></div>
				<div class="skeleton skeleton-full"></div>
			</div>
			</div>`);

		this.container.appendTo(this.wrapper);
		this.sidebar = this.container.find('.desk-sidebar')
		this.body = this.container.find('.desk-body')
	}

	show_loading_state() {
	}

	hide_loading_state() {
		this.container.find('.skeleton').hide();
	}

	fetch_desktop_settings() {
		return frappe
			.call("frappe.desk.desktop.get_base_configuration_for_desk")
			.then(response => {
				if (response.message) {
					console.log(response);
					this.data = response.message;
				} else {
					frappe.throw({
						title: "Couldn't Load Desk",
						message:
							"Something went wrong while loading Desk. <b>Please relaod the page</b>. If the problem persists, contact the Administrator",
						indicator: "red",
						primary_action: {
							label: "Reload",
							action: () => location.reload()
						}
					});
				}
			});
	}

	make_sidebar() {}

	make_body() {}

	setup_events() {}
}