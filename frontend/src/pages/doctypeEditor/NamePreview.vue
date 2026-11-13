<!-- A next-name preview: the parts the app cannot know yet (a field's value) in a lighter gray. -->
<template>
	<span class="font-mono text-sm text-ink-gray-8" data-next-name>
		<span v-for="(part, at) in parts" :key="at" :class="part.gray && 'text-ink-gray-4'">{{
			part.text
		}}</span>
	</span>
</template>

<script setup lang="ts">
import type { NamePart } from "./namingPattern";

defineProps<{ parts: NamePart[] }>();
</script>
