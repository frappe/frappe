// The phone tab bar (frappe/ui/mobile_nav.js) lives in mobile_nav.bundle.js. Only this
// loader is in desk.bundle.js.
$(document).on("startup", () => {
	// Nothing is loaded on a wider screen. Same breakpoint as mobile_nav.scss; a window
	// narrowed later loads the bar then. mobile_nav.bundle.js builds it as it runs.
	// load_asset, not frappe.require, which would freeze the screen while it loads.
	const phone = window.matchMedia("(max-width: 767.98px)");
	const load = () => {
		if (!phone.matches) return;
		phone.removeEventListener("change", load);
		for (const asset of [
			"mobile_nav.bundle.js",
			"bottom_sheet.bundle.js",
			"bottom_sheet.bundle.css",
		]) {
			const path = frappe.assets.bundled_asset(asset);
			frappe.assets.load_asset(path, path);
		}
	};
	phone.addEventListener("change", load);
	load();
});
