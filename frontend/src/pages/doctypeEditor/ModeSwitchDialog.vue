<!-- The Design | Customize switch's question when edits are pending; it closes with its answer. -->
<template>
	<div class="flex flex-col gap-5" data-mode-switch-dialog>
		<p class="text-p-base text-ink-gray-7">{{ message }}</p>
		<div class="flex justify-end gap-2">
			<Button :label="__('Cancel')" @click="close(null)" />
			<Button :label="__('Discard')" @click="close('discard')" />
			<Button variant="solid" :label="__('Save first')" @click="close('save')" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { __ } from "@/i18n";
import type { ModeSwitchAnswer } from "./modeSwitch";

defineProps<{ message: string; close: (answer: ModeSwitchAnswer) => void }>();
</script>
