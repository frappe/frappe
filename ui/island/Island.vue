<!--
	`<Island>`: the Vue host, an island inside a frappe-ui app.

		<Island
			name="insights.dashboard"
			:dashboard="dashboard"
			:context="{ user, locale, navigate }"
			@title="title = $event"
			@actions="actions = $event"
			@navigate="router.push($event)"
		/>

	The component is transparent. Everything but `name` and `context` is the
	island's props object, passed to its component verbatim. `class` and `style`
	stay here, on the host element.

	The desk loader, `frappe.ui.mount_island`, is the other host. Both wrap the
	host loop in `./host.js`. This component adds the Vue lifecycle, and it
	resolves a name over the API instead of from `frappe.boot`.

	It imports nothing but Vue, and not frappe-ui, because an app can pin a
	frappe-ui older than this package's peer range and still host an island.
-->

<template>
	<!-- The island fills what it is given. `mountVueIsland` chains `height: 100%`
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
	/** The host context the island reads through `useHost()`. All fields optional. */
	context: { type: Object, default: () => ({}) },
});

// `@error` is this component's own event. Vue keeps a declared emit out of
// `attrs`, so `onError` never reaches the island.
const emit = defineEmits(["error"]);

const attrs = useAttrs();
const root = ref(null);

let handle = null;

/**
 * The island's props object, which is every attribute but the two the host
 * element keeps. An island reports through plain events, so a host binds a
 * listener and passes no value down. Nothing has to be filtered out here.
 */
const islandProps = computed(() =>
	Object.fromEntries(Object.entries(attrs).filter(([key]) => key !== "class" && key !== "style"))
);

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

function load() {
	// The handle is the component's from here on, loaded or not. `update`
	// reaches a pending mount, and `unmount` cancels it.
	handle?.unmount();
	handle = mountIsland(props.name, root.value, {
		resolve: resolveAssets,
		host: props.context,
		props: islandProps.value,
	});

	// A load this component moved on from reports nothing. The loop resolves a
	// cancelled load instead of failing it.
	handle.ready.catch((e) => emit("error", e instanceof Error ? e : new Error(String(e))));
}

function teardown() {
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
 * The message `frappe.throw` sent. It is in `_server_messages`, a JSON list of
 * JSON strings, and not in the response status.
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
