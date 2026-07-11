<!-- Preview step: table preview, with optional tree/table tabs for tree imports. -->
<script setup>
import { ref, inject, onMounted, onBeforeUnmount, watch, computed, nextTick } from "vue";

import { is_tree_reference_doctype } from "../../wizard_constants.js";

const frm = inject("frm");
const tree_el = ref(null);
const table_el = ref(null);
const active_tab = ref("tree");
const tab_refs = ref([]);
const indicator_ref = ref(null);
const meta_tick = ref(0);
let resize_raf = null;

/** Tree imports get tree + table tabs on the Preview step. */
// frappe.get_meta() is not reactive — the reference DocType meta may load after mount,
// so re-evaluate whenever mount_previews runs (form refresh / preview ready events).
const show_tree_tabs = computed(() => {
	meta_tick.value;
	return is_tree_reference_doctype(frm);
});

function is_preview_field_mounted(fieldname, host_el) {
	const field = frm.fields_dict[fieldname];
	return Boolean(field?.$wrapper?.length && host_el?.contains(field.$wrapper.get(0)));
}

function mount_previews() {
	if (!table_el.value) return;

	meta_tick.value++;
	const is_tree = is_tree_reference_doctype(frm);
	const table_mounted = is_preview_field_mounted("import_preview", table_el.value);
	const tree_mounted =
		!is_tree ||
		(tree_el.value && is_preview_field_mounted("import_tree_preview", tree_el.value));

	if (table_mounted && tree_mounted) {
		if (is_tree && frm.fields_dict.import_tree_preview?.$wrapper?.hasClass("hide-control")) {
			frm.toggle_display("import_tree_preview", true);
		}
		return;
	}

	frm.events.mount_preview_step?.(frm, {
		tree_el: tree_el.value,
		table_el: table_el.value,
	});
	render_empty_state();
}

function render_empty_state() {
	const host = table_el.value;
	if (!host) return;
	if (host.querySelector(".diw-empty-state")) return;
	if (host.children.length > 0 || tree_el.value?.children.length > 0) return;
	if (frm.has_import_file?.()) return;

	const title = __("Preview is not available");
	const subtitle = __(
		"Attach an import file or provide a Google Sheets URL to see the preview."
	);

	$(host).append(`
		<div class="diw-empty-state">
			<div class="diw-empty-title">${frappe.utils.escape_html(title)}</div>
			<div class="diw-empty-subtitle text-muted">${frappe.utils.escape_html(subtitle)}</div>
		</div>
	`);
}

function select_tab(tab_id) {
	active_tab.value = tab_id;
	if (tab_id === "table") {
		nextTick(() => frm.events.refresh_wizard_table_preview?.(frm));
	}
}

function set_tab_ref(index, el) {
	if (el) {
		tab_refs.value[index] = el;
	}
}

function move_indicator() {
	if (!show_tree_tabs.value) return;
	const tabs = ["tree", "table"];
	const index = tabs.indexOf(active_tab.value);
	const tab_el = tab_refs.value[index];
	const indicator_el = indicator_ref.value;
	if (!tab_el || !indicator_el) return;

	indicator_el.style.width = `${tab_el.offsetWidth}px`;
	indicator_el.style.left = `${tab_el.offsetLeft}px`;
}

function schedule_indicator_update() {
	if (resize_raf) {
		cancelAnimationFrame(resize_raf);
	}
	resize_raf = requestAnimationFrame(() => {
		move_indicator();
		resize_raf = null;
	});
}

function set_preview_tab(tab_id) {
	if (!show_tree_tabs.value) return;
	select_tab(tab_id === "tree" ? "tree" : "table");
}

onMounted(() => {
	mount_previews();
	nextTick(schedule_indicator_update);
	window.addEventListener("resize", schedule_indicator_update, { passive: true });
	$(frm.wrapper).on(
		"form-refresh.diw_preview_step diw-import-preview-ready.diw_preview_step diw-import-preview-state.diw_preview_step",
		mount_previews
	);
});

onBeforeUnmount(() => {
	if (resize_raf) {
		cancelAnimationFrame(resize_raf);
	}
	window.removeEventListener("resize", schedule_indicator_update);
	$(frm.wrapper).off(
		"form-refresh.diw_preview_step diw-import-preview-ready.diw_preview_step diw-import-preview-state.diw_preview_step"
	);
	if (tree_el.value) $(tree_el.value).empty();
	if (table_el.value) $(table_el.value).empty();
});

watch(active_tab, () => {
	nextTick(() => {
		move_indicator();
	});
});
watch(show_tree_tabs, (visible) => {
	if (visible && is_tree_reference_doctype(frm) && active_tab.value !== "tree") {
		active_tab.value = "tree";
	}
	if (!visible && active_tab.value === "tree") {
		active_tab.value = "table";
	}
	if (visible) {
		nextTick(() => mount_previews());
	}
	nextTick(schedule_indicator_update);
});

defineExpose({ set_preview_tab });
</script>

<template>
	<div class="diw-preview-step">
		<div
			v-if="show_tree_tabs"
			class="diw-fui-tabs diw-preview-tabs"
			role="tablist"
			:aria-label="__('Preview')"
		>
			<div class="diw-fui-tabs-list">
				<button
					:ref="(el) => set_tab_ref(0, el)"
					type="button"
					class="diw-fui-tab"
					:class="{ 'is-selected': active_tab === 'tree' }"
					role="tab"
					:aria-selected="active_tab === 'tree'"
					@click="select_tab('tree')"
				>
					{{ __("Tree preview") }}
				</button>
				<button
					:ref="(el) => set_tab_ref(1, el)"
					type="button"
					class="diw-fui-tab"
					:class="{ 'is-selected': active_tab === 'table' }"
					role="tab"
					:aria-selected="active_tab === 'table'"
					@click="select_tab('table')"
				>
					{{ __("Table preview") }}
				</button>
				<div ref="indicator_ref" class="diw-fui-tab-indicator" aria-hidden="true" />
			</div>
		</div>

		<div
			v-if="show_tree_tabs"
			v-show="active_tab === 'tree'"
			ref="tree_el"
			class="diw-preview-pane diw-preview-pane-tree"
		/>
		<div
			v-show="!show_tree_tabs || active_tab === 'table'"
			ref="table_el"
			class="diw-preview-pane diw-preview-pane-table"
		/>
	</div>
</template>
