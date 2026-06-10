<template>
	<Button :label="field.label" :disabled="field.readOnly" @click="emit('change', modelValue)" />
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import type { FieldComponentEmits, FieldComponentProps } from "../types";

// A Button carries no value: it triggers an action. `FormLayout` exposes no
// action seam (the registry is the only extension point), so the click rides the
// existing commit seam — `emit('change')` surfaces as `FormLayout`'s
// `@change(fieldname, value)`. The host dispatches on `fieldname` exactly as CRM
// dispatches `triggerButton(fieldname)`. No `update:modelValue` is emitted, so
// the doc is untouched.
//
// Renders a plain button (frappe-ui's default subtle/gray). Theming and icons
// (CRM's `button_color`/`icon`) are app-override territory: an app that wants
// them registers its own `Button` field — the lib keeps `FieldMeta` lean.

defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();
</script>
