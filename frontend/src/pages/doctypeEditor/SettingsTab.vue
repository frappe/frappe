<!-- The Settings tab: the DocType's sections in a 200px list on the left, the open one alone on the
     right. A row Mod+J finds opens its section, scrolls into view and flashes once. -->
<template>
	<div class="mx-auto flex w-full max-w-[1048px] gap-10 px-10 pb-24 pt-8" data-editor-settings>
		<nav
			class="sticky top-8 flex w-[200px] shrink-0 flex-col gap-0.5 self-start"
			:aria-label="__('Settings sections')"
		>
			<ItemListRow
				v-for="one in sections"
				:key="one.key"
				as="button"
				type="button"
				class="text-left"
				:selected="one.key === current?.key"
				:data-section-link="one.key"
				@click="place = { section: one.key, found: null }"
			>
				<template #prefix
					><span
						class="size-4"
						:class="[
							one.icon,
							one.key === 'danger' ? 'text-ink-red-4' : 'text-ink-gray-5',
						]"
						aria-hidden="true"
				/></template>
				<span
					class="block truncate"
					:class="one.key === 'danger' ? 'text-ink-red-7' : 'text-ink-gray-8'"
					>{{ __(one.label) }}</span
				>
			</ItemListRow>
		</nav>
		<div v-if="current" ref="pane" class="min-w-0 max-w-[728px] flex-1">
			<h2 class="mb-1 flex h-7 items-center text-lg font-semibold text-ink-gray-9">
				{{ __(current.label) }}
			</h2>
			<SettingsSection :key="current.key" :section="current.key" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, nextTick, provide, ref, watch } from "vue";
import type { RouteLocationRaw } from "vue-router";
import { ItemListRow } from "frappe-ui";
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import SettingsSection from "./SettingsSection.vue";
import { settingSections, type DangerScope } from "./settingsRows";
import { SettingsView, SettingsViewKey, type SettingsPlace } from "./settingsView";

const props = defineProps<{
	canvas: DesignCanvas;
	customize: RouteLocationRaw | null;
	danger: DangerScope | null;
}>();
const place = defineModel<SettingsPlace>("place", { required: true });

const view = new SettingsView(
	() => props.canvas,
	place,
	() => props.customize,
	() => props.danger
);
provide(SettingsViewKey, view);

const sections = computed(() => settingSections(view.settings, view.danger()));
// A section the DocType no longer has (a new one turned into a child table) falls back to the first.
const current = computed(
	() => sections.value.find((one) => one.key === place.value.section) ?? sections.value[0]
);

const pane = ref<HTMLElement | null>(null);
watch(
	() => place.value.found,
	async (found) => {
		if (!found) return;
		await nextTick();
		const row = pane.value?.querySelector<HTMLElement>(
			`[data-setting="${CSS.escape(found.key)}"]`
		);
		row?.scrollIntoView({ block: "center", behavior: "smooth" });
		flash(row);
	},
	{ immediate: true }
);

function flash(element: HTMLElement | null | undefined) {
	element
		?.querySelector(":scope > [data-flash]")
		?.animate(
			[
				{ opacity: 0 },
				{ opacity: 1, offset: 0.1 },
				{ opacity: 1, offset: 0.6 },
				{ opacity: 0 },
			],
			{ duration: 2000, easing: "ease-out" }
		);
}
</script>
