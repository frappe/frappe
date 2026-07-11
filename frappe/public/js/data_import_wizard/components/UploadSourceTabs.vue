<!-- frappe-ui Tabs chrome — desk bundle has no frappe-ui (ui/CLAUDE.md).
     Matches TabList.vue from frappe-ui: https://ui.frappe.io/docs/components/tabs -->
<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from "vue";

const props = defineProps({
	modelValue: { type: String, required: true },
});

const emit = defineEmits(["update:modelValue"]);

const tabs = [
	{
		id: "file_upload",
		label_desktop: __("File upload"),
		label_mobile: __("Attach file"),
	},
	{
		id: "google_sheet",
		label_desktop: __("Google Sheet"),
		label_mobile: __("Google sheet"),
	},
];

const tab_refs = ref([]);
const indicator_ref = ref(null);
let resize_raf = null;

function select_tab(tab_id) {
	emit("update:modelValue", tab_id);
}

function set_tab_ref(index, el) {
	if (el) {
		tab_refs.value[index] = el;
	}
}

/** Slide the bottom indicator to the active tab, same as frappe-ui TabList. */
function move_indicator() {
	const index = tabs.findIndex((tab) => tab.id === props.modelValue);
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

onMounted(() => {
	nextTick(() => {
		move_indicator();
	});
	window.addEventListener("resize", schedule_indicator_update, { passive: true });
});

onBeforeUnmount(() => {
	if (resize_raf) {
		cancelAnimationFrame(resize_raf);
	}
	window.removeEventListener("resize", schedule_indicator_update);
});

watch(
	() => props.modelValue,
	() => nextTick(move_indicator)
);
</script>

<template>
	<div class="diw-fui-tabs" role="tablist" :aria-label="__('Upload source')">
		<div class="diw-fui-tabs-list">
			<button
				v-for="(tab, index) in tabs"
				:key="tab.id"
				:ref="(el) => set_tab_ref(index, el)"
				type="button"
				class="diw-fui-tab"
				:class="{ 'is-selected': modelValue === tab.id }"
				role="tab"
				:aria-selected="modelValue === tab.id"
				@click="select_tab(tab.id)"
			>
				<span class="diw-upload-tab-label diw-upload-tab-label--desktop">{{
					tab.label_desktop
				}}</span>
				<span class="diw-upload-tab-label diw-upload-tab-label--mobile">{{
					tab.label_mobile
				}}</span>
			</button>
			<div ref="indicator_ref" class="diw-fui-tab-indicator" aria-hidden="true" />
		</div>
	</div>
</template>
