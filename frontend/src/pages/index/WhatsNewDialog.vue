<!-- What's new: each updated app's release notes, newest version first. -->
<template>
	<Dialog v-model="open" :title="__('What\'s new')" size="2xl">
		<div class="flex flex-col gap-8" data-whats-new>
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
import { Dialog } from "frappe-ui";
import { RichTextView } from "@framework/ui/RichText";
import { __ } from "@/i18n";
import type { WhatsNewEntry } from "./notices";

defineProps<{ entries: WhatsNewEntry[] }>();

const open = defineModel<boolean>({ required: true });
</script>
