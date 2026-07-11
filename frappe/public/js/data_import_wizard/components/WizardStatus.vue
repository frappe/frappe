<script setup>
import { ref, onMounted, onBeforeUnmount, inject } from "vue";

const frm = inject("frm");
const el = ref(null);

function sync_status() {
	if (!el.value) return;
	el.value.innerHTML = "";
	const in_import_step = cint(frm.wizard_step) === 3;
	const import_running = Boolean(frm.import_in_progress || frm.doc?.status === "In Progress");
	if (in_import_step && import_running) {
		return;
	}

	const $msg = frm.layout?.msg_area;
	if ($msg?.length) {
		const raw_message = ($msg.text() || "").trim();
		if (raw_message) {
			const safe_message = frappe.utils.escape_html(raw_message).replace(/\n/g, "<br>");
			$(`<div class="diw-headline">${safe_message}</div>`).appendTo(el.value);
		}
	}

	const $progress = frm.dashboard?.progress_area;
	let rendered_progress = false;
	if ($progress?.length && $progress.html()?.trim()) {
		$(el.value).append($progress.clone(false, false));
		rendered_progress = true;
	}

	if (!rendered_progress && frm._wizard_import_progress) {
		const title = frappe.utils.escape_html(
			frm._wizard_import_progress.title || __("Import Progress")
		);
		const message = frappe.utils.escape_html(frm._wizard_import_progress.message || "");
		const raw_percent = Number(frm._wizard_import_progress.percent);
		const has_percent = Number.isFinite(raw_percent);
		const percent = has_percent ? Math.max(0, Math.min(100, Math.floor(raw_percent))) : 100;
		const bar_class = has_percent ? "" : " progress-bar-striped active";

		$(el.value).append(`
			<div class="diw-headline diw-headline-progress-fallback">
				<div class="small text-muted">${title}</div>
				<div class="progress" role="progressbar" aria-label="${title}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${
			has_percent ? percent : 0
		}">
					<div class="progress-bar${bar_class}" style="width: ${percent}%"></div>
				</div>
				${message ? `<div class="small text-muted">${message}</div>` : ""}
			</div>
		`);
	}
}

onMounted(() => {
	sync_status();
	$(frm.wrapper).on("form-refresh.data_import_vue_status", sync_status);
});

onBeforeUnmount(() => {
	$(frm.wrapper).off("form-refresh.data_import_vue_status", sync_status);
});

defineExpose({ sync_status });
</script>

<template>
	<div ref="el" class="diw-status-area" />
</template>
