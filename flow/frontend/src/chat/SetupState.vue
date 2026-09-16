<template>
	<div class="flex flex-col items-center gap-3">
		<BrandMark :size="40" />
		<div class="text-4xl font-medium text-ink-gray-9">Finish setup to start</div>
		<div v-if="hasModels" class="max-w-sm text-sm text-ink-gray-6">
			Every model is set, but no agent is enabled.
		</div>
		<div v-if="canManage" class="mt-4 flex flex-wrap justify-center gap-2">
			<Button
				v-if="!hasModels"
				variant="solid"
				label="Add a provider"
				@click="open('providers')"
			/>
			<Button
				v-if="!hasModels"
				variant="outline"
				label="Add a model"
				@click="open('models')"
			/>
			<Button v-else variant="solid" label="Enable an agent" @click="open('agents')" />
		</div>
		<div v-else class="text-xs text-ink-gray-5">Ask an administrator to finish the setup.</div>
	</div>
</template>

<script setup>
import { computed, inject } from "vue";
import { Button } from "frappe-ui";
import BrandMark from "@flow/ui-core/components/BrandMark.vue";

// The empty state until a model and an agent exist: what is missing, and who can add it.
const flow = inject("flow");
const page = inject("flowPage");
const hasModels = computed(() => page.state.boot.models.length > 0);
const canManage = computed(() =>
	hasModels.value ? page.can("Flow Agent", "write") : page.can("Flow Model", "create")
);

function open(tab) {
	page.state.settingsTab = tab;
	flow.setSettingsOpen(true);
}
</script>
