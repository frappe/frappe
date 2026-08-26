<template>
	<div class="rounded-md border border-outline-gray-2 bg-surface-base p-2">
		<EmailComposer
			ref="composerRef"
			v-model="body"
			v-model:to="to"
			:extensions="[insertDate]"
			:upload-function="mockUpload"
			placeholder="Try ⌘⇧E for today's date, or insert a template…"
			@submit="onSend"
		>
			<!-- #actions adds host utilities beside the built-in attach button. -->
			<template #actions>
				<Dropdown :options="templateOptions">
					<Button variant="ghost" size="sm" label="Templates" />
				</Dropdown>
			</template>
		</EmailComposer>
	</div>
	<p v-if="sent" class="mt-2 text-p-sm text-ink-gray-5">Sent ✓</p>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { Extension } from "@tiptap/core";
import { Button, Dropdown } from "frappe-ui";
import { EmailComposer } from "../index";
import type { Recipient, UploadFunction } from "../types";

const body = ref("");
const to = ref<Recipient[]>([{ email: "grace@example.com", label: "Grace Hopper" }]);
const sent = ref(false);

// A host tiptap extension, appended after the built-in RichTextKit.
const insertDate = Extension.create({
	name: "insertDate",
	addKeyboardShortcuts() {
		return {
			"Mod-Shift-e": ({ editor }) =>
				editor.commands.insertContent(new Date().toLocaleDateString()),
		};
	},
});

const templates = [
	{ label: "Greeting", body: "<p>Hi Grace, thanks for reaching out!</p>" },
	{ label: "Fix shipped", body: "<p>The fix is live — please refresh and try again.</p>" },
	{ label: "Sign-off", body: "<p>Best regards,<br>Sydney</p>" },
];
const composerRef = ref<InstanceType<typeof EmailComposer> | null>(null);
const templateOptions = templates.map((template) => ({
	label: template.label,
	onClick: () => composerRef.value?.editor?.commands.insertContent(template.body),
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
