<template>
	<div class="rounded-md border border-outline-gray-2 bg-surface-base">
		<div class="flex gap-3 border-b border-outline-gray-2 px-4 py-3">
			<Avatar size="md" label="Grace Hopper" />
			<div class="min-w-0">
				<div class="flex items-baseline gap-2">
					<span class="text-sm-medium text-ink-gray-8">Grace Hopper</span>
					<span class="text-p-sm text-ink-gray-4">10 minutes ago</span>
				</div>
				<p class="mt-0.5 text-p-base text-ink-gray-7">
					Thanks for the fix! Could you resend last month's usage report?
				</p>
			</div>
		</div>

		<div class="p-2">
			<EmailComposer ref="composerRef" v-model="body" v-model:to="to" @submit="onSend">
				<!-- #header replaces the built-in rows; recipients are host-seeded. -->
				<template #header>
					<div class="flex items-center gap-2 px-2.5 pb-1">
						<span class="text-p-sm text-ink-gray-5">Replying to</span>
						<span
							class="flex items-center gap-1.5 rounded-full border border-outline-gray-2 py-0.5 pl-1 pr-2 text-p-sm text-ink-gray-7"
						>
							<Avatar size="xs" label="Grace Hopper" />
							Grace Hopper
						</span>
					</div>
				</template>
			</EmailComposer>
		</div>
	</div>
	<p v-if="sent" class="mt-2 text-p-sm text-ink-gray-5">Reply sent to grace@example.com ✓</p>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { Avatar } from "frappe-ui";
import { EmailComposer } from "../index";
import type { Recipient } from "../types";

const body = ref("");
const to = ref<Recipient[]>([{ email: "grace@example.com", label: "Grace Hopper" }]);
const sent = ref(false);

const composerRef = ref<InstanceType<typeof EmailComposer> | null>(null);

function onSend() {
	sent.value = true;
	composerRef.value?.reset();
}
</script>
