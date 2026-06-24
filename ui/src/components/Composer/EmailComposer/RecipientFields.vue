<template>
	<!-- Subject and To are shown when enabled by props; Cc/Bcc are revealed by
		 the header toggles. The To row rides along so the sender can see and edit
		 who the reply goes to. -->
	<div>
		<Row v-if="showSubject || subject" label="Subject">
			<input
				v-model="subject"
				type="text"
				class="flex-1 border-0 bg-transparent p-0 text-base text-ink-gray-8 placeholder-ink-gray-4 focus:ring-0"
				placeholder="Subject"
			/>
		</Row>

		<Row label="To">
			<RecipientSelect v-model="model.to" class="flex-1" placeholder="To" />
		</Row>

		<Row v-if="showCc || model.cc.length" label="CC">
			<RecipientSelect v-model="model.cc" class="flex-1" placeholder="CC" />
		</Row>

		<Row v-if="showBcc || model.bcc.length" label="BCC">
			<RecipientSelect v-model="model.bcc" class="flex-1" placeholder="BCC" />
		</Row>
	</div>
</template>

<script setup lang="ts">
import RecipientSelect from "./RecipientSelect.vue";
import Row from "./RecipientRow.vue";
import type { Recipients } from "../types";

defineProps<{ showSubject?: boolean; showCc?: boolean; showBcc?: boolean }>();
const model = defineModel<Recipients>({ required: true });
const subject = defineModel<string>("subject", { default: "" });
</script>
