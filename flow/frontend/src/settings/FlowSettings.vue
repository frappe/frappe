<template>
	<SettingsDialog v-model:tab="page.state.settingsTab" :groups="groups">
		<template #general><GeneralPanel /></template>
		<template v-for="spec in docSpecs" #[spec.key]>
			<ModelsPanel v-if="spec.key === 'models'" :description="DESCRIPTIONS.models" />
			<DocPanel v-else :spec="spec" :description="DESCRIPTIONS[spec.key]" />
		</template>
		<template #knowledge><KnowledgePanel /></template>
	</SettingsDialog>
</template>

<script setup>
import { computed, inject, watch } from "vue";
import SettingsDialog from "@flow/ui-core/components/SettingsDialog.vue";
import { layout } from "@flow/ui-core/layout.js";

import DocPanel from "./DocPanel.vue";
import GeneralPanel from "./GeneralPanel.vue";
import KnowledgePanel from "./KnowledgePanel.vue";
import ModelsPanel from "./ModelsPanel.vue";
import { SPECS } from "./specs.js";

// Agents, skills and triggers have pages of their own, beside the chats.
const DESCRIPTIONS = {
	tools: "Actions agents can take.",
	models: "The models agents can use.",
	providers: "API keys for the model providers.",
	memories: "What agents have remembered.",
};
const ICONS = {
	general: "lucide-settings",
	tools: "lucide-wrench",
	models: "lucide-box",
	providers: "lucide-key",
	knowledge: "lucide-database",
	memories: "lucide-bookmark",
};

const page = inject("flowPage");
const flow = inject("flow");
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

// in the launcher's panel, the dialog fills the window while it's open (a phone's page fills the
// panel already); the panel goes back once the dialog's 150ms exit has played
let restore = null;
watch(
	() => flow.state.settingsOpen && !layout.phone,
	(open) => {
		if (window.top === window) return;
		clearTimeout(restore);
		const tell = () =>
			window.dispatchEvent(new CustomEvent("flow-settings", { detail: { open } }));
		if (open) tell();
		else restore = setTimeout(tell, 150);
	}
);
</script>
