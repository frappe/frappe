const DEFAULT_SETTINGS = {
	toolbar: true,
	navigation: true,
	zoom: true,
	search: true,
};

const buildViewerHash = (settings = {}) => {
	const merged = { ...DEFAULT_SETTINGS, ...settings };
	const params = [];

	if (merged.toolbar === false) params.push("toolbar=0");
	if (merged.navpanes === false) params.push("navpanes=0");
	if (merged.scrollbar === false) params.push("scrollbar=0");

	if (typeof merged.page === "number") params.push(`page=${Math.max(1, merged.page)}`);

	if (merged.zoom) {
		if (typeof merged.zoom === "string" || typeof merged.zoom === "number") {
			params.push(`zoom=${merged.zoom}`);
		} else {
			params.push("zoom=page-width");
		}
	}

	return params.length ? `#${params.join("&")}` : "";
};

const createIframe = (src, settings) => {
	const iframe = document.createElement("iframe");
	iframe.className = "embedpdf-iframe";
	iframe.style.width = "100%";
	iframe.style.height = "100%";
	iframe.style.border = "none";
	iframe.setAttribute("allowfullscreen", "true");
	iframe.src = `${src}${buildViewerHash(settings)}`;
	return iframe;
};

const EmbedPDF = {
	init({ target, src, settings } = {}) {
		if (!target) {
			throw new Error("EmbedPDF: target element is required");
		}

		if (!src) {
			throw new Error("EmbedPDF: src is required");
		}

		const container = typeof target === "string" ? document.querySelector(target) : target;

		if (!container) {
			throw new Error("EmbedPDF: unable to resolve target element");
		}

		while (container.firstChild) {
			container.removeChild(container.firstChild);
		}

		const iframe = createIframe(src, settings);
		container.appendChild(iframe);

		return {
			iframe,
			target: container,
			updateSource(newSrc, newSettings) {
				if (!newSrc) return;
				const hash = buildViewerHash(newSettings ?? settings);
				iframe.src = `${newSrc}${hash}`;
			},
			destroy() {
				if (iframe.parentNode === container) {
					container.removeChild(iframe);
				}
			},
		};
	},
};

export default EmbedPDF;
