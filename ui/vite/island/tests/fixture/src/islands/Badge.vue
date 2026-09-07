<template>
	<div class="flex items-center gap-2">
		<span :class="toneClass(-1)">{{ label }}</span>
		<Button variant="subtle">{{ label }}</Button>
	</div>
</template>

<script setup>
import { Button } from "frappe-ui";

import { toneClass } from "./tone.js";

defineProps({ label: { type: String, default: "badge" } });
</script>
