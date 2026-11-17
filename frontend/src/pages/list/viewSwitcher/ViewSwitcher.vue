<!-- The list's last crumb: the open view and a chevron, opening the views and acts. It draws its own "/". -->
<template>
	<!-- `-ml-0.5` takes back 2px of the header gap, so this "/" matches the others. -->
	<span class="-ml-0.5 mr-0.5 shrink-0 text-base text-ink-gray-4" aria-hidden="true">/</span>
	<Dropdown :options="options" side="bottom" align="start">
		<!-- The button is the trigger itself, so the menu anchors to it. -->
		<button
			type="button"
			class="group flex min-w-0 max-w-64 shrink items-center gap-1 rounded-4 px-0.5 py-1 text-lg-medium leading-tighter text-ink-gray-9 focus-visible:focus-ring"
			data-view
			data-view-switcher
			@click="views || reload()"
		>
			<span class="min-w-0 truncate" :title="host.view().label">{{
				host.view().label
			}}</span>
			<span
				class="lucide-chevron-down size-4 shrink-0 text-ink-gray-5 group-hover:text-ink-gray-8"
				aria-hidden="true"
			/>
		</button>
		<!-- frappe-ui's gray-4 group labels fall below 4.5:1. -->
		<template #group-label="{ group }">
			<span class="text-ink-gray-6">{{ group.group }}</span>
		</template>
	</Dropdown>
	<!-- The key remounts it per request: a confirmed dialog closes itself but stays mounted. -->
	<ViewDialogs
		v-if="asking"
		:key="asked"
		:request="asking"
		:run="host.call"
		@close="asking = null"
	/>
</template>

<script setup lang="ts">
import { Dropdown } from "frappe-ui";
import { computed, defineAsyncComponent, ref } from "vue";
import { useListedViews } from "@/list/listedViews";
import type { SwitcherHost } from "./switcherHost";
import { viewMenu, type ViewRequest } from "./viewMenu";

const ViewDialogs = defineAsyncComponent(() => import("./ViewDialogs.vue"));

// The header passes its `page`; the switcher reads its host instead.
defineOptions({ inheritAttrs: false });

const props = defineProps<{ host: SwitcherHost }>();

const { views, reload } = useListedViews(props.host.doctype, props.host.app);
const asking = ref<ViewRequest | null>(null);
const asked = ref(0);

const options = computed(() =>
	viewMenu({
		views: views.value,
		current: props.host.view().key,
		plainModified: props.host.view().plainModified,
		unbuilt: props.host.unbuilt,
		types: props.host.types,
		admin: props.host.admin,
		drawn: props.host.drawn,
		run: props.host.run,
		ask: (request) => {
			asked.value++;
			asking.value = request;
		},
	})
);
</script>
