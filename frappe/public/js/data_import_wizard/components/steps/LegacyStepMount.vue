<!-- Bridge until Preview / Fix issues / Import are rebuilt in Vue. Reparents
     existing layout sections — interim only; new steps should use FrmField. -->
<script setup>
import { ref, onMounted, onBeforeUnmount, watch, inject } from "vue";

const props = defineProps({
	step: { type: Number, required: true },
});

const frm = inject("frm");
const el = ref(null);

function mount() {
	if (!el.value) return;
	frm.events.mount_legacy_step(frm, props.step, el.value);
	render_empty_state();
}

function render_empty_state() {
	if (!el.value) return;
	if (el.value.querySelector(".diw-empty-state")) return;
	if (el.value.children.length > 0) return;

	let title = "";
	let subtitle = "";

	if (props.step === 1) {
		title = __("Preview is not available");
		subtitle = frm.has_import_file?.()
			? __("Unable to render preview for this import right now. Try Recheck.")
			: __("Attach an import file or provide a Google Sheets URL to see the preview.");
	} else {
		return;
	}

	$(el.value).append(`
		<div class="diw-empty-state">
			<div class="diw-empty-title">${frappe.utils.escape_html(title)}</div>
			<div class="diw-empty-subtitle text-muted">${frappe.utils.escape_html(subtitle)}</div>
		</div>
	`);
}

onMounted(mount);

onMounted(() => {
	// diw-fix-issues-changed: warnings/mappings recomputed (e.g. preview fetch resolved,
	// a row was skipped) — re-mount so the Fix Issues step reflects them immediately,
	// without requiring the user to navigate away and back.
	$(frm.wrapper).on(
		"form-refresh.data_import_legacy_step diw-fix-issues-changed.data_import_legacy_step",
		mount
	);
});

watch(
	() => props.step,
	() => mount()
);

onBeforeUnmount(() => {
	$(frm.wrapper).off(
		"form-refresh.data_import_legacy_step diw-fix-issues-changed.data_import_legacy_step",
		mount
	);
	if (el.value) {
		$(el.value).empty();
	}
});
</script>

<template>
	<div ref="el" class="diw-legacy-step" :class="{ 'diw-preview-step': step === 1 }" />
</template>
