<!-- In a dialog that is a person's confirm: lists it as a `confirm` or `danger`, which no agent answers
     and a run waits on, and says so when an agent's call opened it. -->
<template>
	<p v-if="asked" class="text-p-sm text-ink-gray-6" data-agent-asked>{{ asked }}</p>
</template>

<script setup lang="ts">
import { inject } from "vue";
import { agentAsk } from "@/acts/dispatcher";
import { ListedDialogKey, type ReadableDialog } from "@/shell/dialogs/readableDialogs";

const props = defineProps<{ kind: "confirm" | "danger"; message: string; buttons: string[] }>();
const asked = agentAsk.note();
const listed = inject<ReadableDialog | null>(ListedDialogKey, null);
// `kind` last: the list reacts to it at once, so `message` and `buttons` must be in by then.
if (listed)
	Object.assign(listed, { message: props.message, buttons: props.buttons, kind: props.kind });
</script>
