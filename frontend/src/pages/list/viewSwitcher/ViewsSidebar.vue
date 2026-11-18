<!-- The DocType sidebar's body: the doctype's views by group, each opening its view, with the row's acts under ⋯. -->
<template>
	<nav v-if="groups" class="flex flex-col gap-0.5" :aria-label="title" data-views-sidebar>
		<template v-for="group in groups" :key="group.label">
			<p
				v-if="group.layer !== null && group.views.length"
				class="flex h-6 items-end pb-0.5 pl-2 text-xs text-ink-gray-6"
			>
				{{ group.label }}
			</p>
			<div v-for="view in group.views" :key="view.key" :data-key="view.key">
				<SidebarItem
					:label="view.label"
					:title="view.label"
					:route="addressOf(view.key)"
					class="data-[state=inactive]:has-[[data-view-menu][data-state=open]]:bg-surface-gray-2"
					:active="view.key === open"
					@click="visit($event, view.key)"
				>
					<template #prefix><Icon :name="iconOf(view.type)" /></template>
					<template #suffix>
						<ViewRowLane
							:modified="isViewModified(doctype, view.key)"
							:is-default="view.default"
							:label="view.label"
							:options="actsOf(view)"
						/>
					</template>
				</SidebarItem>
			</div>
			<div v-for="type in group.soon" :key="type.name" :data-key="type.name.toLowerCase()">
				<SidebarItem
					:route="addressOf(type.name.toLowerCase())"
					:aria-label="__('{0}, soon', [type.label])"
					:active="type.name.toLowerCase() === open"
				>
					<template #prefix><Icon :name="type.icon || 'list'" /></template>
					<span class="truncate text-sm leading-tighter">{{ type.label }}</span>
					<!-- The row's hover fill is the badge's own gray: it takes the next one up there. -->
					<Badge
						class="ml-2 group-hover/sidebar-item:bg-surface-gray-3"
						:label="__('Soon')"
						theme="gray"
						size="sm"
					/>
					<template #suffix><span class="mr-0.5 w-7 shrink-0" /></template>
				</SidebarItem>
			</div>
		</template>
	</nav>
	<!-- The key remounts it per request: a confirmed dialog closes itself but stays mounted. -->
	<ViewDialogs v-if="asking" :key="asked" :request="asking" :run="call" @close="asking = null" />
</template>

<script setup lang="ts">
import { Badge, SidebarItem } from "frappe-ui";
import { computed, defineAsyncComponent, inject, onBeforeUnmount, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { acts } from "@/acts/dispatcher";
import type { Boot } from "@/boot";
import Icon from "@/icons/Icon.vue";
import { useListedViews, type ListedView } from "@/list/listedViews";
import { isViewModified } from "@/list/modifiedView";
import { openViewKey, viewsSidebarDrawn } from "@/navigation/viewsSidebar";
import { routeFor } from "@/router/routeFor";
import { skipDefaultOnce } from "@/router/skipDefault";
import ViewRowLane from "./ViewRowLane.vue";
import { actGroups, viewLayers, type ViewMenuHost, type ViewRequest } from "./viewMenu";
import { isSiteAdmin } from "./viewRules";

const ViewDialogs = defineAsyncComponent(() => import("./ViewDialogs.vue"));

const props = defineProps<{
	doctype: string;
	title?: string;
}>();

const boot = inject<Boot>("boot")!;
const route = useRoute();
const { views } = useListedViews(props.doctype, boot.app);
const asking = ref<ViewRequest | null>(null);
const asked = ref(0);

const types = boot.view_types ?? [];
const groups = computed(
	() => views.value && viewLayers(views.value, boot.unbuilt_view_types ?? [])
);
const open = computed(() => openViewKey(route));

// The crumb drops its list of views only once this body has rows to show instead.
watch(groups, (now) => (viewsSidebarDrawn.value = now ? props.doctype : null), {
	immediate: true,
});
onBeforeUnmount(() => {
	if (viewsSidebarDrawn.value === props.doctype) viewsSidebarDrawn.value = null;
});

// The same acts as the crumb's menu, run on the list page the sidebar sits beside.
const host: Omit<ViewMenuHost, "views" | "current"> = {
	unbuilt: [],
	types,
	admin: isSiteAdmin(boot.session.roles ?? []),
	plainModified: false,
	drawn: (name) => !!acts.find(`list.${name}`),
	run: (name, value) => void acts.perform(`list.${name}`, value),
	ask: (request) => {
		asked.value++;
		asking.value = request;
	},
};

const call = (name: string, value?: unknown) => acts.run(`list.${name}`, value);

function actsOf(view: ListedView) {
	return actGroups({ ...host, views: views.value, current: open.value ?? "" }, view);
}

function iconOf(type: string) {
	return types.find((one) => one.name === type)?.icon || "list";
}

// The plain List is `/<doctype>`, which meets the default; picking it skips the default once.
function addressOf(key: string) {
	return key === "list" ? routeFor(props.doctype) : routeFor(props.doctype, null, { view: key });
}

// A modified click opens a new tab and leaves this one, so it must not arm the skip.
function visit(event: MouseEvent | undefined, key: string) {
	const modified =
		event && (event.metaKey || event.ctrlKey || event.shiftKey || event.button > 0);
	if (key === "list" && !modified) skipDefaultOnce(props.doctype);
}
</script>
