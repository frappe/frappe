<template>
	<!-- Closes only through the builder, so a stray click can't drop unsaved steps. -->
	<Dialog v-model:open="open" size="6xl" bare :dismissible="false">
		<template #default>
			<div class="h-[calc(100vh_-_6rem)]">
				<AutomationBuilder
					v-if="open"
					:automation-name="automationName"
					:doctype="doctype"
					:parent-label="parentLabel"
					@update:dirty="$emit('update:dirty', $event)"
					@saved="$emit('saved', $event)"
					@close="close"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { Dialog } from "frappe-ui";
import AutomationBuilder from "./AutomationBuilder.vue";
import { translate as __ } from "../../utils/translate";

withDefaults(
	defineProps<{
		automationName?: string;
		doctype?: string;
		parentLabel?: string;
	}>(),
	{ automationName: "", doctype: "", parentLabel: () => __("Automations") }
);
const emit = defineEmits<{
	close: [];
	saved: [doc: Record<string, unknown>];
	"update:dirty": [dirty: boolean];
}>();
const open = defineModel<boolean>("open", { default: false });

function close() {
	open.value = false;
	emit("close");
}
</script>
