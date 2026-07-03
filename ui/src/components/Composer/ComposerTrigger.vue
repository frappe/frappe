<template>
	<!-- The collapsed bar that opens the window. Default content is the signed-in
		 user's avatar (from `frappe.boot`) plus the active channel's draft preview.
		 Hosts without a populated `frappe.boot` (e.g. a standalone SPA) can override
		 the slot with their own avatar; it's scoped with `preview` so the draft-text
		 behavior isn't lost. -->
	<button
		v-show="!composer.open.value"
		type="button"
		class="ec-trigger flex w-full cursor-pointer items-center gap-3 rounded-lg border border-outline-gray-2 bg-surface-white px-4 py-2 text-left shadow-sm hover:border-outline-gray-3 hover:bg-surface-gray-1"
		@click="onClick"
	>
		<slot :preview="preview">
			<Avatar
				:image="currentUser.image || ''"
				:label="currentUser.fullname || ''"
				size="sm"
				class="shrink-0"
			/>
			<span class="text-base text-ink-gray-5">{{ preview || placeholder }}</span>
		</slot>
	</button>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Avatar } from "frappe-ui";
import { currentUserInfo } from "./currentUser";
import { requireComposer } from "./composerContext";

withDefaults(defineProps<{ placeholder?: string }>(), {
	placeholder: "Type a message…",
});

const composer = requireComposer("ComposerTrigger");
const currentUser = computed(() => currentUserInfo());

const preview = computed(() => {
	const active = composer.channels.value.find((c) => c.value === composer.channel.value);
	return active?.surface?.preview() || "";
});

// A resize drag that ends collapsed leaves this bar under the pointer, and the
// browser synthesizes a click on release — swallow it for a moment so the same
// gesture doesn't instantly reopen what it just collapsed.
function onClick() {
	if (Date.now() - composer.dragCollapsedAt.value < 300) return;
	composer.open.value = true;
}
</script>
