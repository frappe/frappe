export function setup_skip_links() {
	// https://axesslab.com/skip-links
	for (const skipLink of document.querySelectorAll("[data-frappe-skip-link]")) {
		const skipTo = skipLink.getAttribute("data-frappe-skip-link");
		if (!skipTo) {
			skipLink.remove();
		}
		if (!document.querySelector(skipTo)) {
			skipLink.remove();
		}
		if (!skipLink.hasAttribute("role")) {
			skipLink.setAttribute("role", "link");
		}
		if (!skipLink.hasAttribute("tabindex")) {
			skipLink.setAttribute("tabindex", "0");
		}
		if (!skipLink.hasAttribute("href")) {
			skipLink.setAttribute("href", "#");
		}
		skipLink.addEventListener("click", (event) => {
			event.preventDefault();
			const skipElement = document.querySelector(skipTo);
			if (!skipElement) {
				return; // Target element has been removed
			}
			skipElement.setAttribute("tabindex", -1);
			skipElement.focus();
			skipElement.addEventListener(
				"blur",
				() => {
					skipElement.removeAttribute("tabindex");
				},
				{ once: true }
			);
		});
	}
}
