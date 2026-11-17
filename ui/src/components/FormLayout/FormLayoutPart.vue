<template>
	<div class="part" :data-part="part.name">
		<FormLabel v-if="part.label" :label="part.label" class="mb-1.5" />
		<component :is="part.component" v-bind="part.props" />
	</div>
</template>

<script setup lang="ts">
import { FormLabel } from "frappe-ui";
import type { FormPart } from "./types";

defineProps<{ part: FormPart }>();
</script>
