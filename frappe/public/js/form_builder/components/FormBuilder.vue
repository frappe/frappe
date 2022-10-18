<script setup>
import Sidebar from "./Sidebar.vue";
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
			<Sidebar />
		</div>
		<div class="form-container col-9">
			<div class="form-main">
				<!-- <Tabs /> -->
			</div>
		</div>
	</div>
</template>

<style lang="scss" scoped>
.layout-main-section {
	margin-bottom: -60px;

	.form-container {
		height: calc(100vh - 140px);
		overflow-y: auto;
		padding-top: 0.2rem;
		padding-bottom: 2rem;

		.form-main {
			border-radius: var(--border-radius-md);
			box-shadow: var(--card-shadow);
			background-color: var(--card-bg);
		}
	}
}
</style>
