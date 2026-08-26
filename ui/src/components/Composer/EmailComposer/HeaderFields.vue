<template>
	<div class="px-2.5">
		<Row v-if="showFrom" label="From" :items-center="true">
			<!-- -ml-1 offsets the ghost trigger's px-2 so its text sits 12px from the label. -->
			<Select v-model="from" :options="senderOptions" variant="ghost" class="-ml-1" />
		</Row>

		<Row v-if="showSubject" label="Subject" :items-center="true">
			<input
				v-model="subject"
				type="text"
				class="flex-1 border-0 bg-transparent p-0 text-base text-ink-gray-8 focus:ring-0"
			/>
		</Row>

		<Row v-if="showTo" label="To">
			<RecipientSelect v-model="to" class="flex-1" :search="search" />
			<div v-if="showCc || showBcc" class="flex shrink-0 items-center gap-1">
				<Button
					v-if="showCc"
					variant="ghost"
					label="CC"
					:class="openCc ? '!bg-surface-gray-4' : '!text-ink-gray-5'"
					size="xs"
					@click="toggleCc"
				/>
				<Button
					v-if="showBcc"
					variant="ghost"
					label="BCC"
					:class="openBcc ? '!bg-surface-gray-4' : '!text-ink-gray-5'"
					size="xs"
					@click="toggleBcc"
				/>
			</div>
		</Row>

		<Row v-if="showCc && openCc" label="CC">
			<RecipientSelect v-model="cc" class="flex-1" :search="search" />
		</Row>
		<Row v-if="showBcc && openBcc" label="BCC">
			<RecipientSelect v-model="bcc" class="flex-1" :search="search" />
		</Row>
		<div class="border-b bg-surface-gray-1 mt-2"></div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Button, Select } from "frappe-ui";
import RecipientSelect from "./RecipientSelect.vue";
import Row from "./HeaderRow.vue";
import type { Recipient, RecipientSearch } from "../types";

// Private to EmailComposer, which always passes every flag; required props
// keep the defaults in one place (EmailComposerProps).
const props = withDefaults(
	defineProps<{
		showTo: boolean;
		showCc: boolean;
		showBcc: boolean;
		showFrom: boolean;
		showSubject: boolean;
		senders?: Recipient[];
		search?: RecipientSearch;
	}>(),
	{ senders: () => [] }
);

const to = defineModel<Recipient[]>("to", { default: () => [] });
const cc = defineModel<Recipient[]>("cc", { default: () => [] });
const bcc = defineModel<Recipient[]>("bcc", { default: () => [] });
const subject = defineModel<string>("subject", { default: "" });
const from = defineModel<string>("from", { default: "" });

const senderOptions = computed(() =>
	props.senders.map((sender) => ({
		label: sender.label || sender.email,
		value: sender.email,
	}))
);

// Default to the first sender so the From row never sits unselected.
watch(
	[() => props.showFrom, () => props.senders],
	([show, senders]) => {
		if (show && !from.value && senders.length) from.value = senders[0].email;
	},
	{ immediate: true }
);

const openCc = ref(false);
const openBcc = ref(false);

// Prefilled recipients auto-open their row.
watch(
	() => cc.value.length,
	(count) => {
		if (count) openCc.value = true;
	},
	{ immediate: true }
);
watch(
	() => bcc.value.length,
	(count) => {
		if (count) openBcc.value = true;
	},
	{ immediate: true }
);

// Closing a row drops its recipients so none are sent invisibly.
function toggleCc() {
	openCc.value = !openCc.value;
	if (!openCc.value) cc.value = [];
}
function toggleBcc() {
	openBcc.value = !openBcc.value;
	if (!openBcc.value) bcc.value = [];
}
</script>
