<template>
	<SettingsDialog v-model:tab="page.state.settingsTab" :groups="groups">
		<template #general><GeneralPanel /></template>
		<template v-for="spec in docSpecs" #[spec.key]>
			<DocPanel :spec="spec" :description="DESCRIPTIONS[spec.key]" />
		</template>
		<template #knowledge><KnowledgePanel /></template>
	</SettingsDialog>
</template>

<script setup>
import { computed, inject } from "vue";
import SettingsDialog from "@flow/ui-core/components/SettingsDialog.vue";

import DocPanel from "./DocPanel.vue";
import GeneralPanel from "./GeneralPanel.vue";
import KnowledgePanel from "./KnowledgePanel.vue";
import { SPECS } from "./specs.js";

// Agents, skills and triggers have pages of their own, beside the chats.
const DESCRIPTIONS = {
	tools: "Actions agents can take.",
	models: "The models agents can use.",
	providers: "API keys for the model providers.",
	memories: "What agents have remembered.",
};
const ICONS = {
	general: "settings",
	tools: "tool",
	models: "box",
	providers: "key",
	knowledge: "database",
	memories: "bookmark",
};

const page = inject("flowPage");
const docKeys = ["tools", "models", "providers", "memories"];
const docSpecs = computed(() =>
	docKeys.map((key) => SPECS[key]).filter((spec) => page.can(spec.doctype, "read"))
);

// the dialog's tabs, grouped; a tab is offered only when the user may read its doctype
const groups = computed(() => {
	const tab = (id, label) => ({ id, label, icon: ICONS[id] });
	const allowed = new Set(docSpecs.value.map((spec) => spec.key));
	const docTab = (key) => (allowed.has(key) ? tab(key, SPECS[key].label) : null);
	return [
		{ label: "Chat", tabs: [tab("general", "General")] },
		{
			label: "Agents",
			tabs: [
				docTab("tools"),
				page.can("Flow Knowledge Base", "read") ? tab("knowledge", "Knowledge") : null,
				docTab("memories"),
			],
		},
		{ label: "Models", tabs: ["models", "providers"].map(docTab) },
	]
		.map((group) => ({ ...group, tabs: group.tabs.filter(Boolean) }))
		.filter((group) => group.tabs.length);
});
</script>
