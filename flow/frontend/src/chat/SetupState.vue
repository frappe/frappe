<template>
	<div class="flex flex-col items-center gap-3">
		<BrandMark line :size="32" class="min-h-0 shrink max-md:!h-7 max-md:!w-7" />
		<div class="text-4xl font-medium text-ink-gray-9">Finish setup to start</div>
		<div v-if="hasModels" class="max-w-sm text-base text-ink-gray-6">
			Every model is set, but no agent is enabled.
		</div>
		<div v-if="canManage" class="mt-3 flex flex-col gap-2.5">
			<template v-if="!hasModels">
				<!-- each step numbered in a ring; a provider in place is a step done, its ring ticked -->
				<Button v-if="hasProvider" variant="outline" class="[justify-content:flex-start]" label="Provider added" @click="open('providers')">
					<template #prefix>
						<span :class="ring"><span class="lucide-check size-3" aria-hidden="true" /></span>
					</template>
				</Button>
				<Button v-else variant="outline" class="[justify-content:flex-start]" label="Add a provider" @click="create('providers')">
					<template #prefix><span :class="ring">1</span></template>
				</Button>
				<Button variant="outline" class="[justify-content:flex-start]" label="Add a model" @click="create('models')">
					<template #prefix><span :class="ring">2</span></template>
				</Button>
			</template>
			<Button
				v-else
				variant="solid"
				label="Enable an agent"
				@click="router.push('/agents')"
			/>
		</div>
		<div v-else class="text-sm text-ink-gray-5">Ask an administrator to finish the setup.</div>
	</div>
</template>

<script setup>
import { computed, inject } from "vue";
import { useRouter } from "vue-router";
import { Button } from "frappe-ui";
import BrandMark from "@flow/ui-core/components/BrandMark.vue";

import { inPanel } from "../panel.js";

// The empty state until a model and an agent exist: what is missing, and who can add it.
const flow = inject("flow");
const page = inject("flowPage");
const router = useRouter();
const hasModels = computed(() => page.state.boot.models.length > 0);
const hasProvider = computed(() => Boolean(page.state.boot.provider));
const ring =
	"grid size-4.5 flex-none place-items-center rounded-full border border-outline-gray-3 text-2xs text-ink-gray-7";
const canManage = computed(() =>
	hasModels.value ? page.can("Flow Agent", "write") : page.can("Flow Model", "create")
);

// the done step opens the providers; the launcher's panel opens its provider's form instead
function open(tab) {
	if (inPanel) return router.push(`/providers/${page.state.boot.provider}`);
	page.state.settingsTab = tab;
	flow.setSettingsOpen(true);
}

// an Add step opens settings on a blank record, not the list; the launcher's panel opens the
// record's form in the chat's place, as an agent's, rather than settings over the whole window
function create(tab) {
	if (inPanel) return router.push(`/${tab}/new`);
	page.createRecord(tab);
	flow.setSettingsOpen(true);
}
</script>
