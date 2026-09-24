// The in-page counters for the return-visit walk: skeletons added, and field and row paints.

export const MARKERS = {
	skeletons: [
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
	],
	// Placeholder rows and header cells arrive as a set; the set is one skeleton.
	skeletonMember: '[data-list-header-skeleton], [data-slot="list-row"]',
	row: 'a[data-slot="list-row"][href]',
	field: "[data-record-body] [data-fieldname]",
	title: "[data-crumbs] button > span[title]",
};

// Runs in the page before any app code; serialized, so it may not close over anything.
export function installCounters(markers) {
	const skeletonSelector = markers.skeletons.join(", ");
	const paintable = [markers.row, markers.field, markers.title].join(", ");
	const painted = new WeakMap();
	const pending = new Set();
	let countedSkeletons = new WeakSet();
	let frame = 0;
	const walk = createWalk();
	window.__walk = walk;

	new MutationObserver(onMutations).observe(document, {
		childList: true,
		subtree: true,
		characterData: true,
		attributeFilter: ["class"],
		attributeOldValue: true,
	});
	hookValueSetters();

	function createWalk() {
		const state = {
			reset(recordPath) {
				flush();
				countedSkeletons = new WeakSet();
				Object.assign(state, {
					recordPath,
					skeletons: 0,
					skeletonMarkers: {},
					fields: {},
					rows: {},
				});
				state.stepStart = state.lastChange = performance.now();
			},
			quietMs: () => performance.now() - state.lastChange,
			read: () => readStep(state),
		};
		state.reset("");
		state.stepStart = 0;
		return state;
	}

	function readStep(state) {
		flush();
		return {
			skeletons: state.skeletons,
			skeletonMarkers: state.skeletonMarkers,
			fields: state.fields,
			rows: state.rows,
			quietMs: state.quietMs(),
			changedAtMs: state.lastChange - state.stepStart,
		};
	}

	function onMutations(records) {
		walk.lastChange = performance.now();
		for (const record of records) {
			if (record.type === "attributes") {
				if (turnedSkeleton(record)) countSkeleton(record.target, record.target);
				continue;
			}
			touch(record.target);
			for (const node of record.addedNodes) if (node.nodeType === 1) collectAdded(node);
		}
		scheduleFlush();
	}

	function turnedSkeleton({ target, oldValue }) {
		const pulsing = target.classList.contains("animate-pulse");
		return (
			pulsing &&
			!oldValue?.includes("animate-pulse") &&
			!target.parentElement?.closest(skeletonSelector)
		);
	}

	function countSkeleton(root, matched) {
		if (countedSkeletons.has(root)) return;
		countedSkeletons.add(root);
		const marker = markers.skeletons.find((selector) => matched.matches(selector));
		walk.skeletons += 1;
		walk.skeletonMarkers[marker] = (walk.skeletonMarkers[marker] ?? 0) + 1;
	}

	function touch(node) {
		const element = node.nodeType === 1 ? node : node.parentElement;
		const target = element?.closest(paintable);
		if (target) pending.add(target);
	}

	function collectAdded(element) {
		for (const skeleton of within(element, skeletonSelector)) {
			if (skeleton.parentElement?.closest(skeletonSelector)) continue;
			const member = skeleton.matches(markers.skeletonMember);
			countSkeleton((member && skeleton.parentElement) || skeleton, skeleton);
		}
		for (const target of within(element, paintable)) pending.add(target);
	}

	function within(element, selector) {
		return [
			...(element.matches(selector) ? [element] : []),
			...element.querySelectorAll(selector),
		];
	}

	// A paint is what a frame draws, so an element filled in the frame it was added paints once.
	function scheduleFlush() {
		if (!frame) frame = requestAnimationFrame(flush);
	}

	function flush() {
		cancelAnimationFrame(frame);
		frame = 0;
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
		const controls = [...element.querySelectorAll("input, textarea, select")];
		const values = controls.map((control) =>
			control.type === "checkbox" ? String(control.checked) : control.value
		);
		return [element.textContent.replace(/\s+/g, " ").trim(), ...values].join("|");
	}

	// Vue writes a control's value as a property, which no MutationObserver sees.
	function hookValueSetters() {
		const hooks = [
			[HTMLInputElement.prototype, "value"],
			[HTMLInputElement.prototype, "checked"],
			[HTMLTextAreaElement.prototype, "value"],
			[HTMLSelectElement.prototype, "value"],
		];
		for (const [prototype, property] of hooks) {
			const descriptor = Object.getOwnPropertyDescriptor(prototype, property);
			Object.defineProperty(prototype, property, {
				...descriptor,
				set(value) {
					descriptor.set.call(this, value);
					walk.lastChange = performance.now();
					touch(this);
					scheduleFlush();
				},
			});
		}
	}
}
