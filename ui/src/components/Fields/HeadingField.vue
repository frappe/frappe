<template>
	<h4 class="text-lg-semibold text-ink-gray-9">{{ field.label }}</h4>
</template>

<script setup lang="ts">
// Display-only: a section heading, no value and no emit. Core renders `Heading`
// as an `<h4>` (controls/heading.js → ControlHTML), mirrored here for parity.
import type { FieldComponentProps } from "./types";

defineProps<FieldComponentProps>();
</script>
