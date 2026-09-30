// The in-page probe for the view-restore walk: each scroller's offset on every frame the record
// shows, and the record's view (offsets, form tab, section states) when read.

export const VIEW = {
	scrollers: {
		details: ['[data-record-tab="details"] [data-slot="scroll-area-viewport"]'],
		// The second selector finds the scroller on a build without the `data-body-scroll` mark.
		panel: [
			'[data-body-column="panel"] > [data-body-scroll]',
			'[data-body-column="panel"] > div',
		],
	},
	content: "[data-record-form] [data-fieldname]",
	form: "[data-record-form]",
	tab: '[role="tab"][aria-selected="true"]',
	section: ".section",
	header: ".section-header",
	sectionContent: ".form-section-content",
};

// Runs in the page before any app code; serialized, so it may not close over anything.
export function installViewProbe(view) {
	const frames = [];
	let recordPath = "";
	let lastChange = performance.now();
	let last = "";
	window.__view = {
		reset(path) {
			recordPath = path;
			frames.length = 0;
			lastChange = performance.now();
		},
		frames: () => frames,
		quietMs: () => performance.now() - lastChange,
		read: () => ({ ...offsets(), tab: tabLabel(), sections: sections() }),
		scroller: (name) => scroller(name).element,
	};
	new MutationObserver(() => (lastChange = performance.now())).observe(document, {
		childList: true,
		subtree: true,
		characterData: true,
		attributeFilter: ["class", "data-state"],
	});
	if (document.readyState === "loading") addEventListener("DOMContentLoaded", startFrames);
	else startFrames();

	// A resize observer runs after every rAF callback and layout, so it reads what the frame paints.
	function startFrames() {
		const probe = document.createElement("div");
		probe.style.cssText =
			"position:fixed;left:-9px;top:0;height:1px;width:1px;visibility:hidden";
		document.body.append(probe);
		new ResizeObserver(sample).observe(probe);
		const tick = () => {
			probe.style.width = probe.style.width === "1px" ? "2px" : "1px";
			requestAnimationFrame(tick);
		};
		requestAnimationFrame(tick);
	}

	function sample() {
		if (location.pathname !== recordPath || !shown(document.querySelector(view.content)))
			return;
		const frame = offsets();
		const key = JSON.stringify(frame);
		if (key !== last) lastChange = performance.now();
		last = key;
		frames.push(frame);
	}

	function offsets() {
		const read = (name) => {
			const { element } = scroller(name);
			return shown(element) ? element.scrollTop : null;
		};
		return {
			details: read("details"),
			panel: read("panel"),
			panelMarked: scroller("panel").marked,
		};
	}

	function scroller(name) {
		const [marked, ...fallbacks] = view.scrollers[name];
		const element = document.querySelector(marked);
		if (element) return { element, marked: true };
		const fallback = fallbacks
			.map((selector) => document.querySelector(selector))
			.find(Boolean);
		return { element: fallback ?? null, marked: false };
	}

	function tabLabel() {
		const form = document.querySelector(view.form);
		return form?.querySelector(view.tab)?.textContent.trim() ?? null;
	}

	function sections() {
		const form = document.querySelector(view.form);
		return [...(form?.querySelectorAll(view.section) ?? [])].filter(shown).map((section) => ({
			label: section.querySelector(view.header)?.textContent.trim() ?? "",
			state: section.querySelector(view.sectionContent)?.dataset.state ?? null,
		}));
	}

	function shown(element) {
		return Boolean(element?.getClientRects().length);
	}
}
