frappe.listview_settings["Server Script"] = {
	onload: function (listview) {
		add_github_star_cta(listview);
	},
};

function add_github_star_cta(listview) {
	try {
		const key = "show_github_star_banner";
		if (localStorage.getItem(key) == "false") {
			return;
		}

		if (listview.github_star_banner) {
			listview.github_star_banner.remove();
		}

		const message = "Loving Frappe Framework?";
		const link = "https://github.com/frappe/frappe";
		const cta = "Star us on GitHub";

		listview.github_star_banner = $(`
				<div style="position: relative;">
					<div class="pr-3">
						${message} <br><a href="${link}" target="_blank" style="color: var(--primary-color)">${cta} &rarr; </a>
					</div>
					<div style="position: absolute; top: -1px; right: -4px; cursor: pointer;" title="Dismiss"
						onclick="localStorage.setItem('${key}', 'false') || this.parentElement.remove()">
						<svg class="icon  icon-sm" style="">
							<use class="" href="#icon-close"></use>
						</svg>
					</div>
				</div>
			`).appendTo(listview.page.sidebar);
	} catch (error) {
		console.error(error);
	}
}
