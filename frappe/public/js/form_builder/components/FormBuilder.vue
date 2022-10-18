<script setup>
import Sidebar from "./Sidebar.vue";
import Tabs from "./Tabs.vue";
import { computed, onMounted } from "vue";
import { useStore } from "../store";

let store = useStore();

let should_render = computed(() => {
	return Object.keys(store.layout).length !== 0;
});

onMounted(() => store.fetch());
</script>

<template>
	<div class="layout-main-section row" v-if="should_render">
		<div class="form-controls col-3">
			<div class="form-sidebar">
				<Sidebar />
			</div>
		</div>
		<div class="form-container col-9">
			<div class="form-main">
				<Tabs />
			</div>
		</div>
	</div>
</template>

<style lang="scss" scoped>
.layout-main-section {
	margin-bottom: -60px;

	.form-sidebar,
	.form-main {
		max-height: calc(100vh - 160px);
		overflow-y: auto;
		border-radius: var(--border-radius);
		box-shadow: var(--card-shadow);
		background-color: var(--card-bg);
	}
}
</style>
