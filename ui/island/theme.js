// The host page's live theme, shared by every island on it.
//
// Desk flips `data-theme` on <html> mid-session, from the theme switcher or from
// the OS preference under "automatic". One observer serves all islands, because
// each island is a separate Vue app and the attribute is one DOM node.

const listeners = new Set();
let observer = null;

export function currentTheme() {
	return document.documentElement.getAttribute("data-theme") || "light";
}

/** Runs `callback(theme)` on every host theme change. Returns an unsubscribe. */
export function onThemeChange(callback) {
	listeners.add(callback);

	if (!observer) {
		observer = new MutationObserver(() => {
			const theme = currentTheme();
			listeners.forEach((listener) => listener(theme));
		});
		observer.observe(document.documentElement, {
			attributes: true,
			attributeFilter: ["data-theme"],
		});
	}

	return () => {
		listeners.delete(callback);
		if (!listeners.size && observer) {
			observer.disconnect();
			observer = null;
		}
	};
}
