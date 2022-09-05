<template>
	<div class="layout-main-section row" v-if="shouldRender">
		<div class="form-controls col-2">
			<FormControls />
		</div>
		<div class="form-container col-10">
			<Tabs class="form-main"/>
		</div>
	</div>
</template>

<script>
import FormControls from "./FormControls.vue";
import Tabs from "./Tabs.vue";
import { getStore } from "./store";

export default {
	name: "FormBuilder",
	props: ["doctype"],
	components: {
		Tabs,
		FormControls
	},
	provide() {
		return {
			$store: this.$store
		};
	},
	mounted() {
		this.$store.fetch().then(() => {
			if (!this.$store.layout) {
				this.$store.layout = this.$store.get_layout();
			}
		});
	},
	computed: {
		$store() {
			return getStore(this.doctype);
		},
		shouldRender() {
			return Boolean(
				this.$store.doctype &&
					this.$store.fields &&
					this.$store.layout
			);
		}
	}
};
</script>

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
