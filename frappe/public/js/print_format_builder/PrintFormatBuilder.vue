<template>
	<div class="layout-main-section row" v-if="shouldRender">
		<div class="col-3">
			<PrintFormatControls />
		</div>
		<div class="print-format-container col-9">
			<keep-alive>
				<Preview v-if="show_preview" />
				<PrintFormat v-else />
			</keep-alive>
		</div>
	</div>
</template>

<script>
import PrintFormat from "./PrintFormat.vue";
import Preview from "./Preview.vue";
import PrintFormatControls from "./PrintFormatControls.vue";
import { getStore } from "./store";

export default {
	name: "PrintFormatBuilder",
	props: ["print_format_name"],
	components: {
		PrintFormat,
		PrintFormatControls,
		Preview,
	},
	data() {
		return {
			show_preview: false,
		};
	},
	provide() {
		return {
			$store: this.$store,
		};
	},
	mounted() {
		this.$store.fetch().then(() => {
			if (!this.$store.layout) {
				this.$store.layout = this.$store.get_default_layout();
				this.$store.save_changes();
			}
		});
	},
	methods: {
		toggle_preview() {
			this.show_preview = !this.show_preview;
		},
	},
	computed: {
		$store() {
			return getStore(this.print_format_name);
		},
		shouldRender() {
			return Boolean(this.$store.print_format && this.$store.meta && this.$store.layout);
		},
	},
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
