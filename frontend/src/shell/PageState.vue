<!-- One page state in place of a page's content: what happened, the server's message, and Try again. -->
<template>
	<div
		:role="name === 'empty' || name === 'filtered' ? undefined : 'alert'"
		class="flex min-h-0 flex-1 flex-col overflow-y-auto"
		:data-page-state="name"
	>
		<!-- Centred by auto margins: a tall message then scrolls, where `justify-center` would cut its top. -->
		<div class="m-auto flex flex-col items-center gap-3 px-8 py-16 text-center">
			<span class="size-7 text-ink-gray-4" :class="look.icon" aria-hidden="true" />
			<div class="flex max-w-md flex-col items-center gap-1.5">
				<p class="text-lg font-medium text-ink-gray-8">{{ look.title }}</p>
				<p class="text-p-sm text-ink-gray-6">{{ look.description }}</p>
				<ErrorMessage v-if="message" :message="escaped(message)" />
			</div>
			<Button
				v-if="retry"
				class="mt-1"
				:label="__('Try again')"
				:loading="retrying"
				@click="run"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Button, ErrorMessage } from "frappe-ui";
import { computed, ref } from "vue";
import { __ } from "@/i18n";
import type { PageStateValue } from "./pageState";

const props = defineProps<PageStateValue>();

const looks = {
	empty: {
		icon: "lucide-inbox",
		title: __("Nothing here yet"),
		description: __("There is nothing to show here."),
	},
	filtered: {
		icon: "lucide-funnel-x",
		title: __("No matching records"),
		description: __("Change or clear the filters to see more."),
	},
	notFound: {
		icon: "lucide-search-x",
		title: __("Not found"),
		description: __("This page does not exist, or it was removed."),
	},
	noPermission: {
		icon: "lucide-lock",
		title: __("No permission"),
		description: __("You do not have permission to see this."),
	},
	offline: {
		icon: "lucide-wifi-off",
		title: __("No connection"),
		description: __("Could not reach the server. Check your connection, then try again."),
	},
	failed: {
		icon: "lucide-circle-alert",
		title: __("Something went wrong"),
		description: __("This page could not load."),
	},
};

const look = computed(() => looks[props.name]);

// `ErrorMessage` reads its message as HTML: the text must not become markup again.
function escaped(text: string) {
	return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
const retrying = ref(false);

async function run() {
	retrying.value = true;
	try {
		await props.retry?.();
	} finally {
		retrying.value = false;
	}
}
</script>
