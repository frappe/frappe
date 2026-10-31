<template>
	<form class="flex flex-col gap-2 px-3.5 py-2.5" @submit.prevent="save">
		<p v-if="reason" class="text-sm text-ink-gray-7">{{ reason }}</p>
		<FormControl
			v-model="value"
			type="password"
			autocomplete="new-password"
			placeholder="Enter it here, not in the chat"
		/>
		<ErrorMessage v-if="error" :message="error" />
		<p v-else class="text-xs text-ink-gray-5">
			Saved straight into the field. The assistant and this chat never see it.
		</p>
		<div class="flex items-center justify-end gap-2">
			<button type="button" class="flow-btn-secondary" :disabled="busy" @click="deny">Deny</button>
			<button
				type="submit"
				class="flow-btn-primary"
				:class="value && !busy ? '' : 'pointer-events-none opacity-50'"
			>
				Save
			</button>
		</div>
	</form>
</template>

<script setup>
import { computed, inject, ref } from "vue";
import { ErrorMessage, FormControl } from "frappe-ui";

// A request_secret card: the value is saved by the site, then the card is approved without it
const props = defineProps({
	arguments: { type: Object, default: () => ({}) },
	call: { type: Object, required: true },
});
const flow = inject("flow");
const reason = computed(() => props.arguments.reason);
const value = ref("");
const busy = ref(false);
const error = ref("");

async function save() {
	if (!value.value || busy.value) return;
	busy.value = true;
	error.value = "";
	const sid = flow.state.sessionId;
	try {
		await flow.client.saveSecret(sid, props.call.id, value.value);
		value.value = "";
		// the user switched chats while it saved: its card waits in its own chat
		if (flow.state.sessionId === sid) await flow.answerApproval(props.call.id, "Approve");
	} catch (e) {
		error.value = e?.message || "Couldn't save it. Please try again.";
	} finally {
		busy.value = false;
	}
}

function deny() {
	value.value = "";
	flow.answerApproval(props.call.id, "Deny");
}
</script>
