<!-- What's new: each updated app's release notes, read on open, which records them seen. -->
<template>
	<Dialog v-model="open" :title="__('What\'s new')" size="2xl">
		<LoadingText v-if="!entries" />
		<div v-else class="flex flex-col gap-8" data-whats-new>
			<section v-for="entry in entries" :key="entry.title" class="flex flex-col gap-4">
				<h3 class="text-xl-semibold text-ink-gray-9">
					{{ entry.title }} {{ entry.version }}
				</h3>
				<!-- A note's own headings sit under the app's. -->
				<RichTextView
					v-for="note in entry.notes"
					:key="note.version"
					:html="note.html"
					class="[&_h1]:text-lg-semibold [&_h2]:text-base-semibold [&_h3]:text-base-semibold"
				/>
			</section>
		</div>
	</Dialog>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { Dialog, LoadingText, toast } from "frappe-ui";
import { RichTextView } from "@framework/ui/RichText";
import { __ } from "@/i18n";
import { readWhatsNew, type WhatsNewEntry } from "./notices";

const emit = defineEmits<{ failed: [] }>();

const open = defineModel<boolean>({ required: true });
const entries = ref<WhatsNewEntry[] | null>(null);

readWhatsNew().then(
	(read) => (entries.value = read),
	(error: Error) => {
		toast.error(__("Could not load what's new: {0}", [error.message]));
		open.value = false;
		emit("failed");
	}
);
</script>
