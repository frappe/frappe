<!--
  One icon, drawn from a name.

  `fieldtype: Icon` stores an emoji glyph or a bare sprite symbol name, and its picker
  writes both. A name the sprite does not hold draws nothing and logs once.
-->
<template>
	<span v-if="emoji" :class="SLOT" aria-hidden="true">{{ name }}</span>

	<svg
		v-else-if="symbol"
		:class="SLOT"
		viewBox="0 0 24 24"
		fill="none"
		stroke="currentColor"
		stroke-width="1.5"
		stroke-linecap="round"
		stroke-linejoin="round"
		aria-hidden="true"
	>
		<use :href="`#${symbolId(name!)}`" />
	</svg>

	<span v-else-if="reserve" :class="SLOT" aria-hidden="true" />
</template>

<script setup lang="ts">
import { computed, watchEffect } from "vue";
import { hasSymbol, isEmoji, reportMissingIcon, spriteLoaded, symbolId } from "./sprite";

// `shrink-0` because a row truncates its label and must never truncate the icon instead.
const SLOT = "size-4 shrink-0 text-center leading-4";

// Every shape is `aria-hidden`: the icon sits beside the label it illustrates, and naming
// it would read the row twice.
const props = defineProps<{
	/** An emoji glyph, or a sprite symbol name. */
	name?: string;
	/** Hold the slot open when there is nothing to draw. */
	reserve?: boolean;
}>();

const emoji = computed(() => !!props.name && isEmoji(props.name));
// Reads `spriteLoaded` through `hasSymbol`, so this recomputes when the sprite lands.
const symbol = computed(() => !!props.name && !emoji.value && hasSymbol(props.name));

watchEffect(() => {
	// Before the sprite lands every name is legitimately absent.
	if (!props.name || emoji.value || symbol.value || !spriteLoaded.value) return;
	reportMissingIcon(props.name);
});
</script>
