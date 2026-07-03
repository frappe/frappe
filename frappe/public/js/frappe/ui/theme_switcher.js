frappe.provide("frappe.ui");

frappe.ui.ThemeSwitcher = class ThemeSwitcher {
	constructor() {
		this.setup_dialog();
		this.refresh();
	}

	setup_dialog() {
		this.dialog = new frappe.ui.Dialog({
			title: __("Switch Theme"),
			size: "large",
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
					name: "automatic",
					label: __("Automatic"),
					info: __("Uses system's theme to switch between light and dark mode"),
				},
				{
					name: "light",
					label: __("Light"),
					info: __("Light Theme"),
				},
				{
					name: "dark",
					label: __("Dark"),
					info: __("Dark Theme"),
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
		const selected = this.current_theme === theme.name;
		const is_auto = theme.name === "automatic";

		const field = `<div class="theme-preview-field">
			<div class="theme-preview-label"></div>
			<div class="theme-preview-input"></div>
		</div>`;

		const window_html = (t) => `<div class="theme-preview-container" data-theme="${t}">
			<div class="theme-preview-frame">
				<div class="theme-preview-titlebar">
					<span class="theme-preview-dot theme-preview-dot--red"></span>
					<span class="theme-preview-dot theme-preview-dot--yellow"></span>
					<span class="theme-preview-dot theme-preview-dot--green"></span>
				</div>
				<div class="theme-preview-content">
					<div class="theme-preview-sidebar"></div>
					<div class="theme-preview-main">
						<div class="theme-preview-header">
							<div class="theme-preview-header-title"></div>
							<div class="theme-preview-header-action"></div>
						</div>
						<div class="theme-preview-body">
							${field}${field}${field}${field}
						</div>
					</div>
				</div>
			</div>
		</div>`;

		const preview = is_auto
			? `<div class="theme-card-preview">
				${window_html("light")}
				${window_html("dark")}
			</div>`
			: `<div class="theme-card-preview">${window_html(theme.name)}</div>`;

		const $card = $(`
			<div class="theme-card-wrapper${selected ? " selected" : ""}">
				<button type="button" class="theme-card" title="${theme.info}">
					${preview}
					<div class="theme-card-footer">
						<span class="theme-card-label">${theme.label}</span>
						<span class="theme-card-radio"></span>
					</div>
				</button>
			</div>
		`);

		$card.on("click", () => {
			if (this.current_theme === theme.name) return;
			this.themes.forEach((th) => th.$html.removeClass("selected"));
			$card.addClass("selected");
			this.toggle_theme(theme.name);
		});

		return $card;
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

frappe.ui.get_current_theme = () => {
	return document.documentElement.getAttribute("data-theme");
};
