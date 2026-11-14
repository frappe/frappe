<!--
  One panel row on frappe-ui's `SidebarItem` and `SidebarSection`. The section the address is in
  opens itself and offers no control; a reader's toggle is remembered.
-->
<template>
	<!-- A heading with no destination: a section. Children mount only while it is open. -->
	<SidebarSection
		v-if="heading && !destination"
		:label="label"
		:collapsible="collapsible"
		:collapsed="!open"
		:data-key="item.key"
		@update:collapsed="toggle"
	>
		<template v-if="open">
			<SidebarRow
				v-for="child in node.children"
				:key="child.item.key"
				:node="child"
				:context="context"
				:current="current"
				:sections="sections"
				:sidebar="sidebar"
			/>
		</template>
	</SidebarSection>

	<template v-else>
		<!-- A destination in this prefix. `SidebarItem` puts attributes on its link,
		     so the hooks sit on a wrapper. -->
		<div
			v-if="destination && 'to' in destination"
			:data-key="item.key"
			:data-sidebar="destination.sidebar"
		>
			<SidebarItem :route="target" :label="label" :active="isCurrent">
				<template #prefix><Icon :name="iconOf(item)" /></template>
			</SidebarItem>
		</div>

		<!-- Outside this prefix: a full document load, so an `<a>`. -->
		<div v-else-if="destination && 'href' in destination" :data-key="item.key" :class="ROW">
			<a
				:href="destination.href"
				:class="ROW_TARGET"
				:target="destination.external ? '_blank' : undefined"
				:rel="destination.external ? 'noopener' : undefined"
			>
				<span class="grid shrink-0 place-items-center">
					<Icon :name="iconOf(item)" />
				</span>
				<span class="ml-2 min-w-0 flex-1 truncate text-sm">{{ label }}</span>
				<template v-if="destination.external">
					<span
						class="lucide-arrow-up-right mx-2 size-3 shrink-0 text-ink-gray-5"
						aria-hidden="true"
					/>
					<span class="sr-only">{{ __("Opens in a new tab") }}</span>
				</template>
			</a>
		</div>

		<!-- An action: it opens no place, so it is never current. Not drawn while its act is missing. -->
		<div v-else-if="actRendering && act.available.value" :data-key="item.key" :class="ROW">
			<button
				type="button"
				:class="ROW_TARGET"
				:aria-busy="act.spinning.value"
				@click="act.run"
			>
				<span class="grid shrink-0 place-items-center">
					<LoadingIndicator v-if="act.spinning.value" class="size-4" />
					<Icon v-else :name="iconOf(item)" />
				</span>
				<span class="ml-2 min-w-0 flex-1 truncate text-sm">{{ label }}</span>
			</button>
		</div>

		<!-- Rows fetched on demand; they land at this row's own level. -->
		<div v-else-if="expander" :data-key="item.key" :class="ROW">
			<button type="button" :class="ROW_TARGET" :aria-expanded="expanded" @click="expand">
				<span class="grid shrink-0 place-items-center">
					<Icon :name="iconOf(item)" />
				</span>
				<span class="ml-2 min-w-0 flex-1 truncate text-sm">{{ label }}</span>
			</button>
		</div>

		<!-- A heading with a destination: its children indent under it by hand. -->
		<div
			v-if="node.children.length && open"
			class="ml-3 flex flex-col gap-0.5 border-l border-outline-gray-2 pl-1"
		>
			<SidebarRow
				v-for="child in node.children"
				:key="child.item.key"
				:node="child"
				:context="context"
				:current="current"
				:sections="sections"
				:sidebar="sidebar"
			/>
		</div>

		<!-- Shaped like the child rows: `SidebarItem`'s height, padding and icon size. -->
		<div v-if="reading" data-expand-skeleton class="flex flex-col gap-0.5">
			<LoadingStatus />
			<div v-for="width in SKELETON_WIDTHS" :key="width" class="flex h-7 items-center pl-2">
				<Skeleton class="size-4 shrink-0 rounded-1" />
				<Skeleton :class="['ml-2 h-3 rounded-1', width]" />
			</div>
		</div>

		<SidebarRow
			v-for="child in expandedNodes"
			:key="child.item.key"
			:node="child"
			:context="context"
			:current="current"
			:sidebar="sidebar"
		/>
	</template>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { START_LOCATION } from "vue-router";
import { LoadingIndicator, SidebarItem, SidebarSection, Skeleton } from "frappe-ui";
import { useActRow } from "./actRow";
import { buildTree, containsKey, type ItemNode } from "@/navigation/tree";
import type { SectionMemory } from "@/navigation/sectionMemory";
import { iconOf, labelOf, renderingOf } from "@/navigation/registry";
import Icon from "@/icons/Icon.vue";
import LoadingStatus from "./LoadingStatus.vue";
import type { ItemContext } from "@/navigation/types";

// `SidebarItem`'s own classes, for the two rows drawn by hand. Neither is ever current.
const ROW = "flex h-7 items-center rounded-4 text-ink-gray-6 transition hover:bg-surface-gray-2";
const ROW_TARGET =
	"flex h-full min-w-0 flex-1 items-center rounded-4 pl-2 text-left focus-visible:ring-0 focus-visible:focus-ring";
const SKELETON_WIDTHS = ["w-1/2", "w-2/3", "w-2/5"];

// `current` is passed down: one row wins across the rail and the open panel together.
const props = defineProps<{
	node: ItemNode;
	context: ItemContext;
	current?: string;
	sections?: SectionMemory;
	/** The sidebar these rows are drawn in, named in each link so a destination in several sidebars stays in this one. */
	sidebar?: string;
}>();

const item = computed(() => props.node.item);
const isCurrent = computed(() => !!props.current && props.current === item.value.key);
const rendering = computed(() => renderingOf(item.value, props.context));
const label = computed(() => labelOf(item.value, props.context));

const destination = computed(() => {
	const value = rendering.value;
	return value && ("to" in value || "href" in value) ? value : null;
});
const actRendering = computed(() => {
	const value = rendering.value;
	return value && "act" in value ? value : null;
});
// Where a click goes: the destination, with this sidebar named when it names none of its own.
const target = computed(() => {
	const value = destination.value;
	if (!value || !("to" in value)) return undefined;
	if (!props.sidebar || value.sidebar) return value.to;

	const { path, query, hash } = props.context.router.resolve(value.to, START_LOCATION);
	return { path, query: { ...query, sidebar: props.sidebar }, hash };
});
const act = useActRow(() => actRendering.value ?? { act: "" });
const expander = computed(() => {
	const value = rendering.value;
	return value && "expand" in value ? value : null;
});
// Children with no destination read as a heading whether or not the renderer said `group`.
const heading = computed(
	() => (rendering.value && "group" in rendering.value) || props.node.children.length > 0
);

// `keep_closed` starts a section closed; `collapsible` lets a reader close it. Neither is "open".
const shippedOpen = computed(() => !item.value.keep_closed);

// The one section the address is standing in opens itself, transiently and writing nothing.
const holdsCurrent = computed(() => !!props.current && containsKey(props.node, props.current));

// No control while the address is inside: the section may not shut over the row you are on.
const collapsible = computed(() => !!item.value.collapsible && !holdsCurrent.value);

/** Where this section rests when the address is not inside it. */
function settled(): boolean {
	return props.sections?.recall(item.value.key) ?? shippedOpen.value;
}

const open = ref(holdsCurrent.value || settled());

// Re-derived, not assigned: a save can bring the same key back with a different `keep_closed`.
watch([() => item.value.keep_closed, holdsCurrent], () => {
	open.value = holdsCurrent.value || settled();
});

/** A click on the heading, the one thing here that writes. */
function toggle() {
	open.value = !open.value;
	props.sections?.remember(item.value.key, open.value);
}

const expanded = ref(false);
const reading = ref(false);
const expandedNodes = ref<ItemNode[]>([]);

// A new context is a new list, so an expansion measured against the old one collapses;
// `generation` keeps a fetch left in flight from putting rows back.
let generation = 0;

watch(
	() => props.context,
	() => {
		generation += 1;
		expanded.value = false;
		reading.value = false;
		expandedNodes.value = [];
	}
);

async function expand() {
	if (!expander.value || expanded.value) return;

	// Set before the await, so a second click cannot fire a second request.
	expanded.value = true;
	reading.value = true;
	const mine = generation;

	try {
		const nodes = buildTree(await expander.value.expand());
		if (mine === generation) expandedNodes.value = nodes;
	} catch (error) {
		// Back to unexpanded, so it can be tried again.
		if (mine === generation) expanded.value = false;
		console.error(`[frappe] could not expand navigation item '${item.value.key}'`, error);
	} finally {
		if (mine === generation) reading.value = false;
	}
}
</script>
