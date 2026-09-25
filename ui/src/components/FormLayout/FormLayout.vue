<template>
	<div
		class="flex flex-col"
		:class="{ 'border border-outline-gray-1 border-outline-elevation-2 rounded-lg': hasTabs }"
	>
		<Tabs
			:model-value="activeIndex"
			@update:model-value="select"
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
import { computed, inject, provide, watch } from "vue";
import type { ComponentPublicInstance } from "vue";
import FormLayoutSection from "./FormLayoutSection.vue";
import { useFieldTypes } from "./useFieldTypes";
import { applyTabOverride, resolveLayout } from "./resolveLayout";
import { identifyTabs, tabStripLabel } from "./tabIdentity";
import { CommitKey, DocKey, HasTabsKey, ParentDocKey, ResolveFieldKey, UpdateKey } from "./types";
import { warnMissingCommit } from "./warnMissingCommit";
import type { FormLayoutProps } from "./types";

const props = defineProps<FormLayoutProps>();

// The document channel is `v-model:doc` alone: a consumer that wants "react to
// any change" uses `watch(doc, …)`, and per-field actions/side-effects are baked
// into the layout via `field.ui.on`. The strip has two channels of its own —
// `v-model:tab` below, and `update:activeTab` at the foot of this block.
const doc = defineModel<Record<string, any>>("doc", { required: true });

// The identity of the tab actually **shown**, announced whenever it changes and
// once on mount. `tab` above is the reader's *intent* and only the reader writes
// it; this is the resolution, which a `depends_on` moves without touching the
// intent — so a host that has to know where the reader ended up cannot get it
// from the model, and re-deriving it host-side would put one rule in two repos.
const emit = defineEmits<{ "update:activeTab": [identity: string] }>();

// The tab the reader last *chose*, by identity — an intent, not a position, and
// the only piece of strip state there is. It falls back to an internal ref, so a
// host that doesn't care (the dialogs, the stories) binds nothing; a host that
// wants the reader's place to outlive this component being rebuilt — as the
// Record page does on every save — holds the ref itself.
const desired = defineModel<string>("tab", { default: "" });

// Enclosing doc when this form is a child-row dialog, so `eval:parent.x` resolves
// against the parent. Absent at top level → `parent` falls back to `doc`.
const parentDoc = inject(ParentDocKey, null);

// Re-resolves conditional visibility/mandatory/read-only as the user edits.
const resolvedLayout = computed(() =>
	resolveLayout(props.layout, doc.value, parentDoc?.value ?? doc.value)
);

const visibleTabs = computed(() => {
	// Identity is resolved over the *whole* layout, before the override and before
	// the label fallback, all three deliberately. Resolving it over the visible
	// subset would make the positional fallback shift when a `depends_on`
	// neighbour hides — the very bug identity exists to kill — resolving it after
	// the fallback would collapse every unlabelled tab onto "details", and
	// resolving it after a relabel would move the address a script wrote.
	// The override lands after `resolveLayout` baked the `depends_on`, which is
	// what lets it lift one.
	const tabs = identifyTabs(resolvedLayout.value)
		.map((tab) => ({ ...tab, ...applyTabOverride(tab) }))
		.filter((tab) => !tab.hidden);
	const multipleTabs = tabs.length > 1;
	return tabs.map((tab) => ({
		...tab,
		label: tabStripLabel(tab.label, multipleTabs),
		sections: tab.sections.filter((section) => !section.hidden),
	}));
});

// Which tab is *shown* is derived, never stored: it is `desired` looked up in the
// tabs visible right now, falling back to the first. So a `depends_on` tab that
// disappears cannot strand the reader on a blank form — no clamp is needed —
// and one that comes back brings the reader with it, because a miss leaves
// `desired` alone. Nothing writes state in response to visibility changing.
const active = computed(
	() => visibleTabs.value.find((tab) => tab.identity === desired.value) ?? visibleTabs.value[0]
);

// Announced, never stored: the resolution leaves the component but does not come
// back, so `desired` stays the reader's alone and a tab that returns still brings
// them with it.
watch(
	() => active.value?.identity ?? "",
	(identity) => emit("update:activeTab", identity),
	{ immediate: true }
);

// frappe-ui's `Tabs` addresses its tabs by index. That index is a wire format
// living inside these two — it is never state, and because it is always derived
// from the list we just rendered, it can never point at a tab that isn't there.
const activeIndex = computed(() => Math.max(0, visibleTabs.value.indexOf(active.value)));

function select(index: string | number) {
	// An index naming no tab leaves the intent alone rather than blanking it:
	// `desired` is the reader's, and on the Record page it belongs to a host that
	// outlives this component. Writing `""` here would snap them to the first tab
	// and throw away the memory that makes a returning tab free.
	const chosen = visibleTabs.value[Number(index)];
	if (chosen) desired.value = chosen.identity;
}

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

// Asserted, not consumed: commits travel from each field straight to whoever
// owns them, on their own channel rather than through this component.
warnMissingCommit("FormLayout", inject(CommitKey, null));

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
