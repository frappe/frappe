frappe.provide('frappe.ui');

frappe.ui.ThemeSwitcher = class ThemeSwitcher {
	constructor() {
		this.setup_dialog();
		this.refresh();
	}

	setup_dialog() {
		this.dialog = new frappe.ui.Dialog({
			title: __("Switch Theme")
		});
		this.body = $(`<div class="theme-grid"></div>`).appendTo(this.dialog.$body);
	}

	refresh() {
		this.current_theme = document.documentElement.getAttribute("data-theme") || "light";
		this.fetch_themes().then(() => {
			this.render();
		});
	}

	fetch_themes() {
		return new Promise((resolve) => {
			this.themes = [
				{
					name: "light",
					label: __("Frappe Light"),
				},
				{
					name: "dark",
					label: __("Timeless Night"),
				}
			];

			resolve(this.themes);
		});
	}

	render() {
		this.themes.forEach((theme) => {
			let html = this.get_preview_html(theme);
			html.appendTo(this.body);
			theme.$html = html;
		});
	}

	get_preview_html(theme) {
		const preview = $(`<div class="${this.current_theme == theme.name ? "selected" : "" }">
			<div data-theme=${theme.name}>
				<div class="background">
					<div>
						<div class="preview-check">${frappe.utils.icon('tick', 'xs')}</div>
					</div>
					<div class="navbar"></div>
					<div class="p-2">
						<div class="toolbar">
							<span class="text"></span>
							<span class="primary"></span>
						</div>
						<div class="foreground"></div>
						<div class="foreground"></div>
					</div>
				</div>
			</div>
			<div class="mt-3 text-center">
				<h5 class="theme-title">${theme.label}</h5>
			</div>
		</div>`);

		preview.on('click', () => {
			if (this.current_theme === theme.name) return;

			this.themes.forEach((th) => {
				th.$html.removeClass("selected");
			});

			preview.addClass("selected");
			this.toggle_theme(theme.name);
		});

		return preview;
	}

	toggle_theme(theme) {
		this.current_theme = theme.toLowerCase();
		document.documentElement.setAttribute("data-theme", this.current_theme);
		frappe.show_alert("Theme Changed", 3);

		frappe.xcall("frappe.core.doctype.user.user.switch_theme", {
			theme: toTitle(theme)
		});
	}
	show() {
		this.dialog.show();
	}

	hide() {
		this.dialog.hide();
	}
};
