<template>
	<div
		class="flex flex-col"
		:class="{ 'border border-outline-gray-1 border-outline-elevation-2 rounded-lg': hasTabs }"
	>
		<Tabs
			v-model="tabIndex"
			as="div"
			:tabs="visibleTabs"
			:class="[
				!hasTabs ? `[&_[role='tablist']]:hidden` : '',
				`[&_[role='tablist']::-webkit-scrollbar]:h-0 [&_[role='tab']]:shrink-0 [&_[role='tabpanel']]:overflow-visible !overflow-visible`,
			]"
		>
			<template #tab-panel="{ tab }">
				<div :ref="untabPanel" class="sections" :class="{ 'my-4 sm:my-5': hasTabs }">
					<template
						v-for="(section, index) in tab.sections"
						:key="section.name ?? index"
					>
						<FormLayoutSection :section="section" />
					</template>
				</div>
			</template>
		</Tabs>
	</div>
</template>

<script setup lang="ts">
import { Tabs } from "frappe-ui";
import { computed, inject, provide, ref, watch } from "vue";
import type { ComponentPublicInstance } from "vue";
import FormLayoutSection from "./FormLayoutSection.vue";
import { useFieldTypes } from "./useFieldTypes";
import { resolveLayout } from "./resolveLayout";
import { DocKey, HasTabsKey, ParentDocKey, ResolveFieldKey, UpdateKey } from "./types";
import type { FormLayoutSchema } from "./types";

const props = defineProps<{ layout: FormLayoutSchema }>();

// `FormLayout` is render-only and emits nothing: its sole outward channel is
// `v-model:doc`. A consumer that wants "react to any change" uses `watch(doc, …)`;
// per-field actions/side-effects are baked into the layout via `field.ui.on`.
const doc = defineModel<Record<string, any>>("doc", { required: true });

const tabIndex = ref(0);

// Enclosing doc when this form is a child-row dialog, so `eval:parent.x` resolves
// against the parent. Absent at top level → `parent` falls back to `doc`.
const parentDoc = inject(ParentDocKey, null);

// Re-resolves conditional visibility/mandatory/read-only as the user edits.
const resolvedLayout = computed(() =>
	resolveLayout(props.layout, doc.value, parentDoc?.value ?? doc.value)
);

const visibleTabs = computed(() => {
	const tabs = resolvedLayout.value.filter((tab) => !tab.hidden);
	// With multiple tabs the strip is always shown, so an unlabelled tab would
	// render a blank button — fall back to "Details" so every tab reads clearly.
	const multipleTabs = tabs.length > 1;
	return tabs.map((tab) => ({
		...tab,
		label: tab.label || (multipleTabs ? "Details" : ""),
		sections: tab.sections.filter((section) => !section.hidden),
	}));
});

// A `depends_on` tab can disappear while the user is on it, leaving `tabIndex`
// pointing past the end so `Tabs` renders nothing (blank form). Clamp it back
// into range when the visible set shrinks.
watch(visibleTabs, (tabs) => {
	if (tabIndex.value >= tabs.length) tabIndex.value = Math.max(0, tabs.length - 1);
});

const hasTabs = computed(
	() =>
		visibleTabs.value.length > 1 ||
		(visibleTabs.value.length === 1 && Boolean(visibleTabs.value[0].label))
);

// reka-ui hard-codes `tabindex="0"` on the tabpanel, making the whole panel a tab
// stop before any field. Drop it to `-1` so Tab flows straight to the first field.
function untabPanel(el: Element | ComponentPublicInstance | null) {
	(el as Element | null)?.closest('[role="tabpanel"]')?.setAttribute("tabindex", "-1");
}

// Live sync on every keystroke/selection.
function update(fieldname: string, value: any) {
	doc.value[fieldname] = value;
}

const { resolve } = useFieldTypes();

provide(DocKey, doc);
provide(UpdateKey, update);
provide(ResolveFieldKey, resolve);
provide(HasTabsKey, hasTabs);
</script>

<style scoped>
/* Hide sections that render no fields. */
.section:not(:has(.field)) {
	display: none;
}

/* The first section with fields sits flush under the tab strip. */
.section:has(.field):nth-child(1 of .section:has(.field)) {
	border-top: none;
	margin-top: 0;
	padding-top: 0;
}
</style>
