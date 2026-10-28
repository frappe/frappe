<!-- A Data field's arrow to where its value leads: a web page in a new tab, or a new email. -->
<template>
	<a
		:href="address.href"
		:target="web ? '_blank' : undefined"
		:rel="web ? 'noopener noreferrer' : undefined"
		:aria-label="label"
		:title="label"
		:data-slot="web ? 'open-url' : 'mail-arrow'"
		class="size-4 place-items-center rounded-1 text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-7 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
		@click.stop
		@pointerdown.stop
	>
		<span class="lucide-arrow-up-right size-3.5" />
	</a>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { translate as __ } from "../../utils/translate";
import type { DataHref } from "./dataOptions";

const props = defineProps<{ address: DataHref }>();

const web = computed(() => props.address.kind === "web");
const label = computed(() => (web.value ? __("Open Link") : __("Send Email")));
</script>
