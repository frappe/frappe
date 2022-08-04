frappe.provide("frappe.ui");

frappe.ui.ThemeSwitcher = class ThemeSwitcher {
	constructor() {
		this.setup_dialog();
		this.refresh();
	}

	setup_dialog() {
		this.dialog = new frappe.ui.Dialog({
			title: __("Switch Theme"),
		});
		this.body = $(`<div class="theme-grid"></div>`).appendTo(this.dialog.$body);
		this.bind_events();
	}

	bind_events() {
		this.dialog.$wrapper.on("keydown", (e) => {
			if (!this.themes) return;

			const key = frappe.ui.keys.get_key(e);
			let increment_by;

			if (key === "right") {
				increment_by = 1;
			} else if (key === "left") {
				increment_by = -1;
			} else if (e.keyCode === 13) {
				// keycode 13 is for 'enter'
				this.hide();
			} else {
				return;
			}

			const current_index = this.themes.findIndex((theme) => {
				return theme.name === this.current_theme;
			});

			const new_theme = this.themes[current_index + increment_by];
			if (!new_theme) return;

			new_theme.$html.click();
			return false;
		});
	}

	refresh() {
		this.current_theme = document.documentElement.getAttribute("data-theme-mode") || "light";
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
					info: __("Light Theme"),
				},
				{
					name: "dark",
					label: __("Timeless Night"),
					info: __("Dark Theme"),
				},
				{
					name: "automatic",
					label: __("Automatic"),
					info: __("Uses system's theme to switch between light and dark mode"),
				},
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
		const is_auto_theme = theme.name === "automatic";
		const preview = $(`<div class="${this.current_theme == theme.name ? "selected" : ""}">
			<div data-theme=${is_auto_theme ? "light" : theme.name}
				data-is-auto-theme="${is_auto_theme}" title="${theme.info}">
				<div class="background">
					<div>
						<div class="preview-check" data-theme=${is_auto_theme ? "dark" : theme.name}>
							${frappe.utils.icon("tick", "xs")}
						</div>
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

		preview.on("click", () => {
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
		document.documentElement.setAttribute("data-theme-mode", this.current_theme);
		frappe.show_alert(__("Theme Changed"), 3);

		frappe.xcall("frappe.core.doctype.user.user.switch_theme", {
			theme: toTitle(theme),
		});
	}

	show() {
		this.dialog.show();
	}

	hide() {
		this.dialog.hide();
	}
};

frappe.ui.add_system_theme_switch_listener = () => {
	frappe.ui.dark_theme_media_query.addEventListener("change", () => {
		frappe.ui.set_theme();
	});
};

frappe.ui.dark_theme_media_query = window.matchMedia("(prefers-color-scheme: dark)");

frappe.ui.set_theme = (theme) => {
	const root = document.documentElement;
	let theme_mode = root.getAttribute("data-theme-mode");
	if (!theme) {
		if (theme_mode === "automatic") {
			theme = frappe.ui.dark_theme_media_query.matches ? "dark" : "light";
		}
	}
	root.setAttribute("data-theme", theme || theme_mode);
};
