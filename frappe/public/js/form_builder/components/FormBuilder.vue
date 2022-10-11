<script setup>
import Sidebar from "./Sidebar.vue";
import Layout from "./Layout.vue";
import { onMounted } from "vue";
import { useStore } from "../store";

let store = useStore();

onMounted(() => store.fetch());
</script>

<template>
	<div class="layout-main-section row">
		<div class="form-controls col-3">
			<Sidebar />
		</div>
		<div class="form-container col-9">
			<Layout />
		</div>
	</div>
</template>
