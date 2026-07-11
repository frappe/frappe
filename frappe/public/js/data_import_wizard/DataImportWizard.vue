<script setup>
import { ref, provide, onMounted, onBeforeUnmount, watch, computed, nextTick } from "vue";
import {
	WIZARD_STEPS,
	get_wizard_initial_step,
	wizard_step_needs_preview_bootstrap,
} from "./wizard_constants.js";
import WizardStepper from "./components/WizardStepper.vue";
import WizardMobileHeader from "./components/WizardMobileHeader.vue";
import WizardFooter from "./components/WizardFooter.vue";
import WizardStatus from "./components/WizardStatus.vue";
import ConfigStep from "./components/steps/ConfigStep.vue";
import PreviewStep from "./components/steps/PreviewStep.vue";
import FixIssuesStep from "./components/steps/FixIssuesStep.vue";
import LegacyStepMount from "./components/steps/LegacyStepMount.vue";
import PreviewStepSkeleton from "./components/PreviewStepSkeleton.vue";
import FixIssuesSkeleton from "./components/FixIssuesSkeleton.vue";

const props = defineProps({
	frm: { type: Object, required: true },
});

provide("frm", props.frm);

const preview_loading = ref(false);
const initial_step = cint(get_wizard_initial_step(props.frm));
props.frm.wizard_step = cint(props.frm.wizard_step ?? initial_step);
const current_step = ref(cint(props.frm.wizard_step ?? initial_step));
const wizard_bootstrapping = ref(
	wizard_step_needs_preview_bootstrap(props.frm, current_step.value)
);

provide("preview_loading", preview_loading);
provide("wizard_bootstrapping", wizard_bootstrapping);

function set_preview_loading(loading) {
	preview_loading.value = Boolean(loading);
}

const footer_ref = ref(null);
const preview_ref = ref(null);
const fix_issues_ref = ref(null);
const status_ref = ref(null);
const docname = ref(props.frm.doc.name);
const viewport_width = ref(window.innerWidth);
const viewport_height = ref(window.innerHeight);
const stats_tick = ref(0);
const fix_issues_success_icon = frappe.utils.icon("check", "lg", "", "", "", true);
let resize_raf = null;
let sync_from_frm_token = 0;

function on_document_form_refresh(_event, refreshed_frm) {
	if (refreshed_frm !== props.frm) return;
	sync_from_frm();
}

/** One card height for every step — sized to the viewport, not step content. */
const card_min_height = computed(() => {
	const is_mobile = viewport_width.value <= 768;
	const reserved = is_mobile ? 180 : 220;
	const floor = is_mobile ? 400 : 520;
	const ceiling = 720;
	return Math.max(floor, Math.min(ceiling, viewport_height.value - reserved));
});

const card_style = computed(() => {
	const height = `${card_min_height.value}px`;
	const is_mobile = viewport_width.value <= 768;

	if (is_mobile) {
		return {
			minHeight: height,
		};
	}

	return {
		minHeight: height,
		height,
		maxHeight: height,
	};
});

function update_viewport_size() {
	if (resize_raf) {
		cancelAnimationFrame(resize_raf);
	}
	resize_raf = requestAnimationFrame(() => {
		viewport_width.value = window.innerWidth;
		viewport_height.value = window.innerHeight;
		resize_raf = null;
	});
}

function set_step(step, options = {}) {
	step = Math.max(0, Math.min(step, WIZARD_STEPS.length - 1));
	const changed = step !== current_step.value;
	current_step.value = step;
	props.frm.wizard_step = step;

	if (changed || options.refresh_ui) {
		footer_ref.value?.bump?.();
		status_ref.value?.sync_status?.();
	}

	if (!options.skip_primary_action && (changed || options.refresh_primary_action)) {
		props.frm.trigger("update_primary_action");
	}

	if (step === 1 && props.frm.has_import_file?.()) {
		props.frm.events.refresh_wizard_table_preview?.(props.frm);
	}

	if (step === 2 && props.frm.has_import_file?.()) {
		props.frm.events.prepare_fix_issues_step?.(props.frm);
		stats_tick.value += 1;
	}
}

function bump_ui() {
	footer_ref.value?.bump?.();
	status_ref.value?.sync_status?.();
	stats_tick.value += 1;
	$(props.frm.wrapper).trigger("diw-import-preview-state");
}

function on_preview_state_change() {
	stats_tick.value += 1;
}

function refresh_fix_issues() {
	stats_tick.value += 1;
	fix_issues_ref.value?.remount?.();
}

async function prepare_step_bootstrap(target_step) {
	target_step = cint(target_step);
	if (!wizard_step_needs_preview_bootstrap(props.frm, target_step)) {
		wizard_bootstrapping.value = false;
		return;
	}

	wizard_bootstrapping.value = true;
	// Step 2 uses FixIssuesSkeleton in Vue — avoid injecting the preview table skeleton.
	if (target_step === 1) {
		set_preview_loading(true);
	}
	try {
		await props.frm.events.ensure_import_preview_ready?.(props.frm);
		if (target_step === 2) {
			props.frm.events.prepare_fix_issues_step?.(props.frm);
		}
	} finally {
		wizard_bootstrapping.value = false;
		if (target_step === 1) {
			set_preview_loading(false);
		}
	}
}

/** Show step skeleton while preview is in-flight for Preview / Fix Issues. */
const show_step_skeleton = computed(() => {
	stats_tick.value;
	preview_loading.value;
	const step = cint(current_step.value);
	if (step !== 1 && step !== 2) return false;
	if (!props.frm.has_import_file?.()) return false;
	if (wizard_bootstrapping.value) return true;
	return Boolean(
		props.frm._import_preview_loading ||
			props.frm._import_preview_promise ||
			wizard_step_needs_preview_bootstrap(props.frm, step)
	);
});

const bootstrap_skeleton = computed(() => {
	const step = cint(current_step.value);
	if (step === 1) return "preview";
	if (step === 2) return "fix_issues";
	return null;
});

const bootstrap_panel_step = computed(() => cint(current_step.value));

provide("show_step_skeleton", show_step_skeleton);

async function sync_from_frm() {
	const token = ++sync_from_frm_token;

	if (props.frm.doc.name !== docname.value) {
		docname.value = props.frm.doc.name;
		if (!props.frm._wizard_navigation_in_progress) {
			props.frm._wizard_step_initialized = false;
		}
	}
	stats_tick.value += 1;
	if (props.frm._wizard_navigation_in_progress) {
		bump_ui();
		return;
	}

	let target_step;
	const is_first_sync = !props.frm._wizard_step_initialized;
	if (is_first_sync) {
		target_step = cint(get_wizard_initial_step(props.frm));
		current_step.value = target_step;
		props.frm.wizard_step = target_step;
	} else {
		target_step = cint(props.frm.wizard_step ?? current_step.value);
	}

	if (wizard_step_needs_preview_bootstrap(props.frm, target_step)) {
		wizard_bootstrapping.value = true;
	}

	await prepare_step_bootstrap(target_step);
	if (token !== sync_from_frm_token) {
		return;
	}

	if (is_first_sync) {
		props.frm._wizard_step_initialized = true;
	}

	if (target_step !== current_step.value) {
		set_step(target_step);
		if (target_step === 2) {
			nextTick(() => refresh_fix_issues());
		}
	} else {
		bump_ui();
		if (target_step === 2) {
			nextTick(() => refresh_fix_issues());
		}
	}
}

onMounted(() => {
	// Sync if a preview fetch started before the wizard mounted.
	set_preview_loading(Boolean(props.frm._import_preview_loading));
	props.frm._wizard_step_initialized = props.frm._wizard_step_initialized ?? false;
	void sync_from_frm();
	window.addEventListener("resize", update_viewport_size, { passive: true });
	$(props.frm.wrapper).on("form-refresh.data_import_vue_root", sync_from_frm);
	$(props.frm.wrapper).on(
		"diw-import-preview-state.data_import_vue_root diw-import-preview-ready.data_import_vue_root",
		on_preview_state_change
	);
	$(document).on("form-refresh.data_import_vue_root", on_document_form_refresh);
});

onBeforeUnmount(() => {
	if (resize_raf) {
		cancelAnimationFrame(resize_raf);
		resize_raf = null;
	}
	window.removeEventListener("resize", update_viewport_size);
	$(props.frm.wrapper).off("form-refresh.data_import_vue_root", sync_from_frm);
	$(props.frm.wrapper).off(
		"diw-import-preview-state.data_import_vue_root diw-import-preview-ready.data_import_vue_root",
		on_preview_state_change
	);
	$(document).off("form-refresh.data_import_vue_root", on_document_form_refresh);
});

watch(
	() => props.frm.doc.name,
	() => sync_from_frm()
);

async function on_go(step) {
	if (step === current_step.value) return;

	if (step < current_step.value) {
		props.frm.events.go_to_wizard_step(props.frm, step);
		set_step(step);
		return;
	}

	const ok = await props.frm.events.handle_wizard_go_to_step(
		props.frm,
		step,
		current_step.value
	);
	if (ok !== false) {
		set_step(props.frm.wizard_step);
	}
}

async function on_next() {
	const ok = await props.frm.events.handle_wizard_go_to_step(
		props.frm,
		current_step.value + 1,
		current_step.value
	);
	if (ok !== false) {
		set_step(props.frm.wizard_step);
	}
}

async function on_apply() {
	if (props.frm.is_dirty()) {
		frappe.show_alert({
			message: __("Save your changes before importing."),
			indicator: "orange",
		});
		return;
	}
	await props.frm.events.handle_wizard_apply(props.frm);
	set_step(props.frm.wizard_step);
}

const fix_issues_empty_stats = computed(() => {
	stats_tick.value;
	current_step.value;
	docname.value;
	const fix_state = props.frm.events.get_fix_issues_state?.(props.frm) || {};
	const warnings_count = fix_state.warnings_count || 0;
	const value_mappings_count = fix_state.value_mappings_count || 0;
	const preview_data = props.frm.import_preview?.preview_data;
	const rows_checked =
		props.frm.doc.payload_count ||
		preview_data?.total_number_of_rows ||
		preview_data?.data?.length ||
		0;
	const columns = preview_data?.columns || [];
	let columns_matched = columns.filter((col) => {
		const is_row_number_col =
			col.header_title === "Sr. No" || col.header_title === __("Sr. No");
		if (is_row_number_col) return false;

		const mapped_field =
			col.map_to_field || col.df?.fieldname || col.df?.fieldname_without_parent || "";
		const explicitly_skipped = Boolean(col.skip_import || mapped_field === "dont_import");
		if (explicitly_skipped) return false;

		return Boolean(col.df || mapped_field);
	}).length;

	if (!columns_matched) {
		let mapped_columns = [];
		try {
			const template_options = JSON.parse(props.frm.doc.template_options || "{}");
			mapped_columns = Object.values(template_options?.column_to_field_map || {});
		} catch (_e) {
			mapped_columns = [];
		}

		columns_matched = mapped_columns.filter((fieldname) => {
			if (!fieldname) return false;
			return !["Don't Import", "dont_import"].includes(fieldname);
		}).length;
	}
	const rows_skipped = fix_state.skipped_rows_count || (props.frm.doc.skipped_rows || []).length;
	const issues_found = fix_state.has_issues
		? warnings_count + value_mappings_count + rows_skipped
		: 0;

	return {
		warnings_count,
		value_mappings_count,
		rows_checked,
		columns_matched,
		rows_skipped,
		issues_found,
	};
});

const fix_issues_empty_state = computed(() => {
	stats_tick.value;
	const fix_state = props.frm.events.get_fix_issues_state?.(props.frm) || {};
	const has_import_file = Boolean(props.frm.has_import_file?.());
	const is_complete = fix_state.is_complete;
	const has_issues = Boolean(fix_state.has_issues);

	let subtitle = "";
	if (!has_import_file) {
		subtitle = __("Attach an import file to validate rows and mappings.");
	} else if (is_complete) {
		subtitle = __("Import is complete and no warnings or mappings need fixes.");
	} else {
		subtitle = __("No warnings or mappings found so far. You can continue to import.");
	}

	return {
		show: !has_issues,
		subtitle,
		show_stats: has_import_file && fix_issues_empty_stats.value.rows_checked > 0,
	};
});

function show_fix_issues_empty_state(step_index) {
	if (step_index !== 2) return false;
	return fix_issues_empty_state.value.show;
}

defineExpose({
	set_step,
	sync_from_frm,
	bump_ui,
	refresh_fix_issues,
	set_preview_tab,
	set_preview_loading,
});

function set_preview_tab(tab) {
	const preview = Array.isArray(preview_ref.value)
		? preview_ref.value.find(Boolean)
		: preview_ref.value;
	preview?.set_preview_tab?.(tab);
}
</script>

<template>
	<div class="data-import-custom-ui">
		<div class="diw-shell">
			<div class="diw-stepper-wrap">
				<WizardStepper :current_step="current_step" @go="on_go" />
			</div>
			<div class="diw-card" :style="card_style">
				<WizardMobileHeader :current_step="current_step" />
				<div v-if="show_step_skeleton" class="diw-panels-wrap">
					<div class="diw-panels">
						<section class="diw-step-panel" :data-step="bootstrap_panel_step">
							<div class="diw-step-content">
								<PreviewStepSkeleton v-if="bootstrap_skeleton === 'preview'" />
								<FixIssuesSkeleton
									v-else-if="bootstrap_skeleton === 'fix_issues'"
								/>
							</div>
						</section>
					</div>
				</div>
				<div v-else class="diw-panels-wrap">
					<div class="diw-panels">
						<section
							v-for="(step, index) in WIZARD_STEPS"
							:key="step.id"
							class="diw-step-panel"
							:class="{ hidden: index !== current_step }"
							:data-step="index"
						>
							<div
								v-if="step.header_title && !show_fix_issues_empty_state(index)"
								class="diw-step-header"
							>
								<h4 class="diw-step-title">{{ step.header_title }}</h4>
								<p
									v-if="step.header_subtitle"
									class="diw-step-subtitle text-muted"
								>
									{{ step.header_subtitle }}
								</p>
							</div>
							<div class="diw-step-content">
								<ConfigStep
									v-if="step.vue && index === current_step"
									:key="`config-${docname}`"
									:docname="docname"
								/>
								<PreviewStep
									v-else-if="index === 1 && index === current_step"
									ref="preview_ref"
									:key="`preview-${docname}`"
								/>
								<FixIssuesStep
									v-else-if="
										index === 2 &&
										index === current_step &&
										!show_fix_issues_empty_state(index)
									"
									ref="fix_issues_ref"
									:key="`fix-issues-${docname}`"
								/>
								<LegacyStepMount
									v-else-if="
										!step.vue &&
										index !== 1 &&
										index !== 2 &&
										index === current_step
									"
									:step="index"
								/>
								<div
									v-if="show_fix_issues_empty_state(index)"
									class="diw-empty-state diw-step-inline-empty diw-fix-issues-empty"
								>
									<div
										class="diw-fix-issues-empty-icon"
										v-html="fix_issues_success_icon"
									/>
									<div class="diw-empty-title">{{ __("No issues to fix") }}</div>
									<div class="diw-empty-subtitle text-muted">
										{{ fix_issues_empty_state.subtitle }}
									</div>
									<div
										v-if="fix_issues_empty_state.show_stats"
										class="diw-fix-issues-empty-stats"
										role="list"
										:aria-label="__('Import summary')"
									>
										<div class="diw-fix-issues-empty-stat" role="listitem">
											<div class="diw-fix-issues-empty-stat-value">
												{{ fix_issues_empty_stats.rows_checked }}
											</div>
											<div class="diw-fix-issues-empty-stat-label">
												{{ __("Rows checked") }}
											</div>
										</div>
										<div class="diw-fix-issues-empty-stat" role="listitem">
											<div class="diw-fix-issues-empty-stat-value">
												{{ fix_issues_empty_stats.columns_matched }}
											</div>
											<div class="diw-fix-issues-empty-stat-label">
												{{ __("Columns matched") }}
											</div>
										</div>
										<div class="diw-fix-issues-empty-stat" role="listitem">
											<div class="diw-fix-issues-empty-stat-value is-good">
												{{ fix_issues_empty_stats.rows_skipped }}
											</div>
											<div class="diw-fix-issues-empty-stat-label">
												{{ __("Rows skipped") }}
											</div>
										</div>
									</div>
								</div>
							</div>
						</section>
					</div>
				</div>
				<WizardStatus v-if="!show_step_skeleton" ref="status_ref" />
				<WizardFooter
					ref="footer_ref"
					:current_step="current_step"
					@back="set_step(current_step - 1)"
					@next="on_next"
					@apply="on_apply"
				/>
			</div>
		</div>
	</div>
</template>

<style>
@import "./data_import_wizard.css";
</style>
