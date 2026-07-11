<!-- Fix Issues step: warnings list and value-mapping grid reparented from the std form. -->
<script setup>
import { ref, inject, onMounted, onBeforeUnmount, watch } from "vue";

const frm = inject("frm");
const el = ref(null);

/** Render warnings/mappings into the step panel; always rebuild so both sections stay in sync. */
function mount() {
	if (!el.value) return;

	// Run after form-refresh layout work so reparented grids keep live field wrappers.
	setTimeout(() => {
		if (!el.value) return;
		const state = frm.events.mount_fix_issues_step?.(frm, el.value) || {};
		render_empty_state(state);
	}, 0);
}

function render_empty_state(state = {}) {
	if (!el.value) return;
	if (state.has_issues) return;
	if (el.value.querySelector(".diw-empty-state")) return;
	if (el.value.children.length > 0) return;

	let title = __("No issues to fix");
	let subtitle = "";
	if (!frm.has_import_file?.()) {
		subtitle = __("Attach an import file to validate rows and mappings.");
	} else if (["Success", "Partial Success"].includes(frm.doc.status)) {
		subtitle = __("This import is complete. There are no pending warnings or mapping issues.");
	} else {
		subtitle = __("No warnings or mapping issues were found for this import.");
	}

	$(el.value).append(`
		<div class="diw-empty-state">
			<div class="diw-empty-title">${frappe.utils.escape_html(title)}</div>
			<div class="diw-empty-subtitle text-muted">${frappe.utils.escape_html(subtitle)}</div>
		</div>
	`);
}

onMounted(() => {
	mount();
	// Re-mount when preview finishes or warnings/mappings are recomputed.
	$(frm.wrapper).on(
		"form-refresh.diw_fix_issues_step diw-fix-issues-changed.diw_fix_issues_step diw-import-preview-ready.diw_fix_issues_step",
		mount
	);
});

onBeforeUnmount(() => {
	$(frm.wrapper).off(
		"form-refresh.diw_fix_issues_step diw-fix-issues-changed.diw_fix_issues_step diw-import-preview-ready.diw_fix_issues_step",
		mount
	);
	if (el.value) {
		// Detach live field wrappers first — .empty() would strip their event handlers.
		for (const fieldname of ["import_warnings", "value_mappings"]) {
			frm.fields_dict?.[fieldname]?.$wrapper?.detach();
		}
		$(el.value).empty();
	}
});

watch(
	() => frm.doc.name,
	() => mount()
);

defineExpose({ remount: mount });
</script>

<template>
	<div ref="el" class="diw-legacy-step diw-fix-issues-step" />
</template>
