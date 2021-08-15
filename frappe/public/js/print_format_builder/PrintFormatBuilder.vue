<template>
	<div class="layout-main-section row" v-if="shouldRender">
		<div class="col-3">
			<PrintFormatControls />
		</div>
		<div class="print-format-container col-9">
			<PrintFormat />
		</div>
	</div>
</template>

<script>
import PrintFormat from "./PrintFormat.vue";
import PrintFormatControls from "./PrintFormatControls.vue";
import { getStore } from "./store";

export default {
	name: "PrintFormatBuilder",
	props: ["print_format_name"],
	components: {
		PrintFormat,
		PrintFormatControls
	},
	provide() {
		return {
			$store: this.$store
		};
	},
	mounted() {
		this.$store.fetch();
	},
	computed: {
		$store() {
			return getStore(this.print_format_name);
		},
		shouldRender() {
			return Boolean(
				this.$store.print_format && this.$store.meta && this.$store.layout
			);
		}
	}
};
</script>

<style scoped>
.print-format-container {
	height: calc(100vh - 140px);
	overflow-y: auto;
	padding-top: 0.5rem;
	padding-bottom: 4rem;
}
</style>
