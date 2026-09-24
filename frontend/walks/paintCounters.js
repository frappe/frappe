// The in-page counters for the return-visit walk: skeletons added, and field and row paints.

export const MARKERS = {
	skeleton: [
		".fui-skeleton",
		".animate-pulse",
		"[data-tile-skeleton]",
		"[data-record-header-skeleton]",
		"[data-record-body-skeleton]",
		"[data-record-tabs-skeleton]",
		"[data-feed-skeleton]",
		"[data-form-skeleton]",
		"[data-record-panel-skeleton]",
		"[data-panel-sections-skeleton]",
		"[data-quick-filter-skeleton]",
		"[data-list-header-skeleton]",
		"[data-expand-skeleton]",
		"[data-customize-skeleton]",
		'[role="status"]:has(.fui-skeleton)',
		'[data-slot="list-row"]:has(.fui-skeleton)',
	].join(", "),
	// Placeholder rows and header cells arrive as a set; the set is one skeleton.
	skeletonMember: '[data-list-header-skeleton], [data-slot="list-row"]',
	row: 'a[data-slot="list-row"][href]',
	field: "[data-record-body] [data-fieldname]",
	title: "[data-crumbs] button > span[title]",
};

// Runs in the page before any app code; serialized, so it may not close over anything.
export function installCounters(markers) {
	const painted = new WeakMap();
	const pending = new Set();
	const walk = {
		recordPath: "",
		reset(recordPath) {
			Object.assign(walk, { recordPath, skeletons: 0, fields: {}, rows: {} });
			walk.stepStart = walk.lastChange = performance.now();
		},
		read: () => ({
			skeletons: walk.skeletons,
			fields: walk.fields,
			rows: walk.rows,
			quietMs: performance.now() - walk.lastChange,
			changedAtMs: walk.lastChange - walk.stepStart,
		}),
	};
	walk.reset("");
	walk.stepStart = 0;
	window.__walk = walk;
	const paintable = [markers.row, markers.field, markers.title].join(", ");

	new MutationObserver(onMutations).observe(document, {
		childList: true,
		subtree: true,
		characterData: true,
		attributeFilter: ["class"],
		attributeOldValue: true,
	});
	hookValueSetters();

	function onMutations(records) {
		walk.lastChange = performance.now();
		const skeletons = new Set();
		for (const record of records) {
			if (record.type === "attributes") {
				if (turnedSkeleton(record)) skeletons.add(record.target);
				continue;
			}
			touch(record.target);
			for (const node of record.addedNodes)
				if (node.nodeType === 1) collectAdded(node, skeletons);
		}
		walk.skeletons += skeletons.size;
		flush();
	}

	function collectAdded(element, skeletons) {
		for (const skeleton of within(element, markers.skeleton)) {
			if (skeleton.parentElement?.closest(markers.skeleton)) continue;
			const member = skeleton.matches(markers.skeletonMember);
			skeletons.add(member ? skeleton.parentElement : skeleton);
		}
		for (const target of within(element, paintable)) pending.add(target);
	}

	function turnedSkeleton({ target, oldValue }) {
		const pulsing = target.classList.contains("animate-pulse");
		return (
			pulsing &&
			!oldValue?.includes("animate-pulse") &&
			!target.parentElement?.closest(markers.skeleton)
		);
	}

	function touch(node) {
		const element = node.nodeType === 1 ? node : node.parentElement;
		const target = element?.closest(paintable);
		if (target) pending.add(target);
	}

	function flush() {
		for (const element of pending) {
			const key = keyOf(element);
			const text = visibleText(element);
			if (!key || !element.isConnected || painted.get(element) === text) continue;
			painted.set(element, text);
			const [bucket, name] = key;
			walk[bucket][name] = (walk[bucket][name] ?? 0) + 1;
		}
		pending.clear();
	}

	function keyOf(element) {
		if (element.matches(markers.row))
			return ["rows", decodeURIComponent(element.getAttribute("href").split("/").pop())];
		if (element.matches(markers.field)) {
			const place = element.closest("[data-record-form]") ? "form" : "panel";
			return ["fields", `${place}.${element.dataset.fieldname}`];
		}
		return location.pathname === walk.recordPath ? ["fields", "title"] : null;
	}

	function visibleText(element) {
		const controls = [...element.querySelectorAll("input, textarea")];
		const values = controls.map((control) =>
			control.type === "checkbox" ? String(control.checked) : control.value
		);
		return [element.textContent.replace(/\s+/g, " ").trim(), ...values].join("|");
	}

	function within(element, selector) {
		return [
			...(element.matches(selector) ? [element] : []),
			...element.querySelectorAll(selector),
		];
	}

	// Vue writes an input's value as a property, which no MutationObserver sees.
	function hookValueSetters() {
		const hooks = [
			[HTMLInputElement.prototype, "value"],
			[HTMLInputElement.prototype, "checked"],
			[HTMLTextAreaElement.prototype, "value"],
		];
		for (const [prototype, property] of hooks) {
			const descriptor = Object.getOwnPropertyDescriptor(prototype, property);
			Object.defineProperty(prototype, property, {
				...descriptor,
				set(value) {
					descriptor.set.call(this, value);
					walk.lastChange = performance.now();
					touch(this);
					queueMicrotask(flush);
				},
			});
		}
	}
}
