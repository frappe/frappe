<template>
	<div class="flex flex-col items-center gap-3">
		<BrandMark :size="40" />
		<div class="text-4xl font-medium text-ink-gray-9">Finish setup to start</div>
		<div v-if="hasModels" class="max-w-sm text-sm text-ink-gray-6">
			Every model is set, but no agent is enabled.
		</div>
		<div v-if="canManage" class="mt-4 flex flex-wrap justify-center gap-2">
			<template v-if="!hasModels">
				<!-- a provider in place is a step done: ticked, and the model is next -->
				<Button
					v-if="hasProvider"
					icon-left="lucide-check"
					label="Provider added"
					@click="open('providers')"
				/>
				<Button
					v-else
					variant="solid"
					label="Add a provider"
					@click="create('providers')"
				/>
				<Button
					:variant="hasProvider ? 'solid' : 'outline'"
					label="Add a model"
					@click="create('models')"
				/>
			</template>
			<Button
				v-else
				variant="solid"
				label="Enable an agent"
				@click="router.push('/agents')"
			/>
		</div>
		<div v-else class="text-xs text-ink-gray-5">Ask an administrator to finish the setup.</div>
	</div>
</template>

<script setup>
import { computed, inject } from "vue";
import { useRouter } from "vue-router";
import { Button } from "frappe-ui";
import BrandMark from "@flow/ui-core/components/BrandMark.vue";

// The empty state until a model and an agent exist: what is missing, and who can add it.
const flow = inject("flow");
const page = inject("flowPage");
const router = useRouter();
const hasModels = computed(() => page.state.boot.models.length > 0);
const hasProvider = computed(() => Boolean(page.state.boot.has_provider));
const canManage = computed(() =>
	hasModels.value ? page.can("Flow Agent", "write") : page.can("Flow Model", "create")
);

function open(tab) {
	page.state.settingsTab = tab;
	flow.setSettingsOpen(true);
}

// an Add step opens settings on a blank record, not the list
function create(tab) {
	page.createRecord(tab);
	flow.setSettingsOpen(true);
}
</script>
