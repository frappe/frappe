<template>
	<div class="rounded-md border border-outline-gray-2 bg-surface-base p-2">
		<EmailComposer
			ref="composerRef"
			v-model="body"
			v-model:to="to"
			:upload-function="mockUpload"
			placeholder="Insert a canned reply…"
			@submit="onSend"
		>
			<!-- #actions adds host utilities beside the built-in attach button,
			     inserting through the exposed editor. -->
			<template #actions>
				<Tooltip text="Canned replies">
					<Dropdown :options="cannedReplyOptions">
						<Button
							variant="ghost"
							size="sm"
							:icon="LucideZap"
							aria-label="Canned replies"
						/>
					</Dropdown>
				</Tooltip>
			</template>
		</EmailComposer>
	</div>
	<p v-if="sent" class="mt-2 text-p-sm text-ink-gray-5">Sent ✓</p>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { Button, Dropdown, Tooltip } from "frappe-ui";
import LucideZap from "~icons/lucide/zap";
import { EmailComposer } from "../index";
import type { Recipient, UploadFunction } from "../types";

const body = ref("");
const to = ref<Recipient[]>([{ email: "grace@example.com", label: "Grace Hopper" }]);
const sent = ref(false);

const composerRef = ref<InstanceType<typeof EmailComposer> | null>(null);

const cannedReplies = [
	{ label: "Greeting", body: "<p>Hi Grace, thanks for reaching out!</p>" },
	{ label: "Fix shipped", body: "<p>The fix is live. Please refresh and try again.</p>" },
	{ label: "Sign-off", body: "<p>Best regards,<br>Sydney</p>" },
];
const cannedReplyOptions = cannedReplies.map((reply) => ({
	label: reply.label,
	onClick: () => composerRef.value?.editor?.commands.insertContent(reply.body),
}));

const mockUpload: UploadFunction = async (file) => ({
	name: `mock-${Date.now()}`,
	file_name: file.name,
	file_url: URL.createObjectURL(file),
	file_size: file.size,
	file_type: file.type,
});

function onSend() {
	sent.value = true;
	composerRef.value?.reset();
}
</script>
