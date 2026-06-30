<template>
	<!-- Subject and To are shown when enabled by `fields`; Cc/Bcc are revealed by
		 the toggles on the To row (or whenever they already carry recipients). -->
	<div class="px-2.5">
		<Row
			v-if="showSubject || subject"
			label="Subject"
			label-class="w-[52px]"
			:items-center="true"
		>
			<input
				v-model="subject"
				type="text"
				class="flex-1 border-0 bg-transparent p-0 text-base text-ink-gray-8 focus:ring-0"
			/>
		</Row>

		<Row label="To">
			<RecipientSelect v-model="model.to" class="flex-1" :search="search" />
			<div v-if="canCc || canBcc" class="flex shrink-0 items-center gap-1">
				<Button
					v-if="canCc"
					variant="ghost"
					label="CC"
					:class="showCc ? '!bg-surface-gray-4' : '!text-ink-gray-5'"
					@click="showCc = !showCc"
				/>
				<Button
					v-if="canBcc"
					variant="ghost"
					label="BCC"
					:class="showBcc ? '!bg-surface-gray-4' : '!text-ink-gray-5'"
					@click="showBcc = !showBcc"
				/>
			</div>
		</Row>

		<Row v-if="showCc || model.cc.length" label="CC">
			<RecipientSelect v-model="model.cc" class="flex-1" :search="search" />
		</Row>

		<Row v-if="showBcc || model.bcc.length" label="BCC">
			<RecipientSelect v-model="model.bcc" class="flex-1" :search="search" />
		</Row>
		<div class="border-b bg-surface-gray-1 mt-1"></div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Button } from "frappe-ui";
import RecipientSelect from "./RecipientSelect.vue";
import Row from "./RecipientRow.vue";
import type { Field, Recipients, RecipientSearch } from "../types";

const props = withDefaults(
	defineProps<{
		/** Rows offered beyond the always-present "To". */
		fields?: Field[];
		search?: RecipientSearch;
	}>(),
	{ fields: () => ["cc", "bcc"] }
);

const model = defineModel<Recipients>({ required: true });
const subject = defineModel<string>("subject", { default: "" });

// Which optional rows this composer offers.
const showSubject = computed(() => props.fields.includes("subject"));
const canCc = computed(() => props.fields.includes("cc"));
const canBcc = computed(() => props.fields.includes("bcc"));

// Toggle state for the Cc/Bcc rows (display-only; rows also show when prefilled).
const showCc = ref(false);
const showBcc = ref(false);
</script>
