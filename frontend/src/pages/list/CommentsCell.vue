<!-- The Comments column: how many comments the record has, as desk v1's list row counts them. -->
<template>
	<div class="flex items-center gap-1 text-base text-ink-gray-7">
		<LucideMessageCircle class="size-3.5" />
		<span>{{ count > 99 ? "99+" : count }}</span>
	</div>
</template>

<script setup lang="ts">
import LucideMessageCircle from "~icons/lucide/message-circle";
import { computed } from "vue";
import { commentCountOf } from "@/list/rowParts";

const props = defineProps<{ doctype: string; name: string }>();

const count = computed(() => commentCountOf(props.doctype, props.name) ?? 0);
</script>
