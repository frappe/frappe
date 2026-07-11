<script setup>
import { computed, inject, ref } from "vue";
import DeskButton from "./DeskButton.vue";

const props = defineProps({
	current_step: { type: Number, required: true },
});

const emit = defineEmits(["back", "next", "apply"]);
const frm = inject("frm");
const preview_loading = inject("preview_loading", ref(false));
const show_step_skeleton = inject("show_step_skeleton", ref(false));
const step_loading = computed(() => preview_loading.value || show_step_skeleton.value);
const next_icon = frappe.utils.icon("arrow-right", "sm", "", "", "", true);
const back_icon = frappe.utils.icon("arrow-left", "sm", "", "", "", true);

const footer = computed(() => {
	const step = props.current_step;
	const is_finished = ["Success", "Partial Success"].includes(frm.doc.status);
	const can_import = !frm.is_new() && frm.has_import_file?.() && frm.doc.status !== "Success";
	const import_blocked = frm.is_dirty();
	const next_blocked = import_blocked;

	let apply_label = __("Import");

	return {
		show_back: step !== 0,
		show_next: step === 0 || step === 1 || (step === 2 && is_finished),
		next_disabled: step_loading.value || next_blocked,
		next_tooltip: next_blocked ? __("Save the form before continuing.") : "",
		show_apply: step === 2 && can_import && !is_finished,
		apply_disabled: import_blocked || step_loading.value,
		apply_tooltip: import_blocked ? __("Save your changes before importing.") : "",
		apply_label,
	};
});

defineExpose({
	bump: () => {},
});
</script>

<template>
	<footer class="diw-footer">
		<div class="diw-footer-left">
			<DeskButton v-if="footer.show_back" class="diw-btn-back" @click="emit('back')">
				<span class="diw-btn-back-icon" v-html="back_icon" />
				{{ __("Back") }}
			</DeskButton>
		</div>
		<div class="diw-footer-right">
			<DeskButton
				v-if="footer.show_next"
				class="diw-btn-next"
				:disabled="footer.next_disabled"
				:title="footer.next_tooltip"
				@click="emit('next')"
			>
				{{ __("Next") }}
				<span class="diw-btn-next-icon" v-html="next_icon" />
			</DeskButton>
			<DeskButton
				v-if="footer.show_apply"
				variant="primary"
				class="diw-btn-apply"
				:label="footer.apply_label"
				:disabled="footer.apply_disabled"
				:title="footer.apply_tooltip"
				@click="emit('apply')"
			/>
		</div>
	</footer>
</template>
