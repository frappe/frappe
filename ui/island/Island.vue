<!--
	`<Island>` — an island inside a frappe-ui app.

		<Island
			name="insights.dashboard"
			:props="{ dashboard: 'sales' }"
			:context="{ user, locale, navigate }"
			@navigate="router.push($event.route)"
		/>

	Desk's other host is `frappe.ui.mount_island`. Both wrap the same loop in
	`./host.js`; this component adds the Vue lifecycle and resolves a name over
	the API instead of out of `frappe.boot`.

	It imports nothing but vue — not frappe-ui — because an app can pin a
	frappe-ui older than this package's peer range and still host an island.
-->

<template>
	<!-- The island fills what it is given: `mountVueIsland` chains `height: 100%`
	     from here down, and the chain breaks at the first auto height. -->
	<div ref="root" v-bind="passthrough" style="height: 100%"></div>
</template>

<script>
export default {
	// The parent's listeners are the island's `on` callbacks, not DOM listeners
	// on the root element, so nothing falls through by itself.
	inheritAttrs: false,
};
</script>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, useAttrs, watch } from "vue";

import { mountIsland } from "./host.js";

const props = defineProps({
	name: { type: String, required: true },
	/** Props for the island's component. */
	props: { type: Object, default: () => ({}) },
	/** The host context the island reads through `useDesk()`. All fields optional. */
	context: { type: Object, default: () => ({}) },
});

// `@error` is this component's own event and never reaches the island.
const emit = defineEmits(["error"]);

const attrs = useAttrs();
const root = ref(null);

// A token per load. An import can outlive the component, so only the newest load
// keeps its handle and anything later tears down what it mounted.
let token = null;
let handle = null;

const passthrough = computed(() =>
	Object.fromEntries(Object.entries(attrs).filter(([key]) => !isListener(key)))
);

onMounted(load);
onBeforeUnmount(teardown);

watch(() => props.name, load);

// Deep, because the usual call site passes an object literal — a new identity on
// every render of the parent, which an identity watch cannot tell from a change.
// Island props are plain data, so the traversal is bounded.
watch(
	() => props.props,
	(next) => handle?.update(next),
	{ deep: true }
);

async function load() {
	const mine = (token = {});

	try {
		const island = await mountIsland(props.name, root.value, {
			resolve: resolveAssets,
			desk: props.context,
			props: props.props,
			on: listeners(),
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

/** `{ onNavigate: fn }` -> `{ navigate: fn }`, the shape the mount contract takes. */
function listeners() {
	return Object.fromEntries(
		Object.entries(attrs)
			.filter(([key, value]) => isListener(key) && typeof value === "function")
			.map(([key, value]) => [key.charAt(2).toLowerCase() + key.slice(3), value])
	);
}

function isListener(key) {
	return /^on[A-Z]/.test(key);
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
