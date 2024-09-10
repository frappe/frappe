<template>
	<div v-if="shouldRender" style="display: flex; width: 100%">
		<div style="padding: var(--padding-md)">
			<PrintFormatControls />
		</div>
		<div class="print-format-container">
			<KeepAlive>
				<component :is="Preview" v-if="show_preview" />
				<component :is="PrintFormat" v-else />
			</KeepAlive>
		</div>
	</div>
</template>

<script setup>
import PrintFormat from "./PrintFormat.vue";
import Preview from "./Preview.vue";
import PrintFormatControls from "./PrintFormatControls.vue";
import { getStore } from "./store";
import { computed, ref, onMounted, provide } from "vue";

// props
const props = defineProps(["print_format_name"]);

// variables
let show_preview = ref(false);

// computed
let $store = computed(() => {
	return getStore(props.print_format_name);
});

let shouldRender = computed(() => {
	return Boolean(
		$store.value.print_format.value && $store.value.meta.value && $store.value.layout.value
	);
});

// provide
provide("$store", $store.value);

// methods
function toggle_preview() {
	show_preview.value = !show_preview.value;
}

// mounted
onMounted(() => {
	$store.value.fetch().then(() => {
		if (!$store.value.layout.value) {
			$store.value.layout.value = $store.value.get_default_layout();
			$store.value.save_changes();
		}
	});
});

defineExpose({ toggle_preview, $store });
</script>

<style scoped>
.print-format-container {
	height: calc(100vh - 95px);
	width: 100%;
	overflow-y: auto;
	padding-top: 0.5rem;
	padding-bottom: 4rem;
}
</style>
