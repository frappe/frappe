<template>
	<Button :label="field.label" :disabled="field.readOnly" />
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import type { FieldComponentProps } from "./types";

// A Button carries no value: it triggers an action. There is no emit-on-click
// hack anymore — the click arrives via the node's `ui.on.click` (decorate- or
// schema-supplied), falling through onto this single-root `<Button>`. An
// undecorated Button is an inert plain button (frappe-ui's default subtle/gray);
// theming (variant/theme/icon) and the click handler both ride the `ui` overlay,
// so `FieldMeta` stays lean and the registry is reserved for structural swaps.

defineProps<FieldComponentProps>();
</script>
