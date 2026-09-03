<!--
	`<Island>` — an island inside a frappe-ui app.

		<Island
			name="insights.dashboard"
			:dashboard="dashboard"
			:context="{ user, locale, navigate }"
			v-model:title="title"
			v-model:actions="actions"
			@navigate="router.push($event)"
		/>

	The component is transparent: everything but `name` and `context` is the
	island's props object, passed to its component verbatim — data attributes and
	`on*` listeners alike, exactly as `h()` takes them. `class` and `style` stay
	here, on the host element.

	Desk's other host is `frappe.ui.mount_island`. Both wrap the same loop in
	`./host.js`; this component adds the Vue lifecycle and resolves a name over
	the API instead of out of `frappe.boot`.

	It imports nothing but vue — not frappe-ui — because an app can pin a
	frappe-ui older than this package's peer range and still host an island.
-->

<template>
	<!-- The island fills what it is given: `mountVueIsland` chains `height: 100%`
	     from here down, and the chain breaks at the first auto height. The static
	     style comes first, so a style the parent passes wins over it. -->
	<div ref="root" style="height: 100%" :class="attrs.class" :style="attrs.style"></div>
</template>

<script>
export default {
	// Everything the parent passes is the island's, not the host element's, so
	// nothing falls through by itself. `class` and `style` are bound above.
	inheritAttrs: false,
};
</script>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, useAttrs, watch } from "vue";

import { mountIsland } from "./host.js";

const props = defineProps({
	name: { type: String, required: true },
	/** The host context the island reads through `useDesk()`. All fields optional. */
	context: { type: Object, default: () => ({}) },
});

// `@error` is this component's own event. Vue keeps a declared emit out of
// `attrs`, so `onError` never reaches the island.
const emit = defineEmits(["error"]);

const attrs = useAttrs();
const root = ref(null);

// A token per load. An import can outlive the component, so only the newest load
// keeps its handle and anything later tears down what it mounted.
let token = null;
let handle = null;

/**
 * The island's props object: every attr but the two the host element keeps, and
 * but the states the island reports. `v-model:title` passes `title` down as well
 * as listening for it, and the island owns that value: sent back, it lands as a
 * stray attribute on the island's root and echoes every report through `update`.
 */
const islandProps = computed(() => {
	const reported = new Set(
		Object.keys(attrs)
			.filter((key) => key.startsWith("onUpdate:"))
			.map((key) => key.slice("onUpdate:".length))
	);
	return Object.fromEntries(
		Object.entries(attrs).filter(
			([key]) => key !== "class" && key !== "style" && !reported.has(key)
		)
	);
});

onMounted(load);
onBeforeUnmount(teardown);

watch(() => props.name, load);

// `useAttrs()` returns a proxy that refreshes on each render of the parent, so
// the object above is a new one every time whether or not anything changed.
// Compare per key, or every parent render would push a redundant update through
// the shadow boundary.
watch(islandProps, (next, previous) => {
	if (!sameProps(next, previous)) handle?.update(next);
});

async function load() {
	const mine = (token = {});

	try {
		const island = await mountIsland(props.name, root.value, {
			resolve: resolveAssets,
			desk: props.context,
			props: islandProps.value,
		});

		if (token !== mine) return island.unmount();
		handle = island;
	} catch (e) {
		if (token !== mine) return;
		handle = null;
		emit("error", e instanceof Error ? e : new Error(String(e)));
	}
}

function teardown() {
	token = {};
	handle?.unmount();
	handle = null;
}

function sameProps(a, b) {
	const keys = Object.keys(a);
	if (keys.length !== Object.keys(b).length) return false;
	return keys.every((key) => a[key] === b[key]);
}

/**
 * A plain fetch, not frappe-ui's resource layer, so this file keeps its only
 * import on vue.
 */
async function resolveAssets(name) {
	const url = `/api/method/frappe.utils.island.get_island_assets?name=${encodeURIComponent(
		name
	)}`;
	const response = await fetch(url, { credentials: "same-origin" });
	const body = await response.json().catch(() => ({}));
	if (!response.ok) {
		throw new Error(
			serverMessage(body) || `island: cannot resolve "${name}" (${response.status})`
		);
	}
	return body.message;
}

/**
 * The message `frappe.throw` sent. It rides `_server_messages`, a JSON list of
 * JSON strings, and not the response status.
 */
function serverMessage(body) {
	try {
		return JSON.parse(body._server_messages)
			.map((entry) => JSON.parse(entry).message)
			.filter(Boolean)
			.join(" ");
	} catch (e) {
		return body.exception || null;
	}
}
</script>
