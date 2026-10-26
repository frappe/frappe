// Desk's indicator colors, as the themes frappe-ui's Badge has.
const THEMES = {
	grey: "gray",
	gray: "gray",
	darkgrey: "gray",
	green: "green",
	red: "red",
	orange: "amber",
	yellow: "amber",
	pink: "violet",
	purple: "violet",
	blue: "blue",
	lightblue: "blue",
	cyan: "blue",
};

export function badge_theme(color) {
	return THEMES[(color || "").toLowerCase()] || "gray";
}
