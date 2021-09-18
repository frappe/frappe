<template>
	<div
		v-if="is_shown"
		class="flex justify-between build-success-message align-center"
	>
		<div class="mr-4">Compiled successfully</div>
		<a class="text-white underline" href="/" @click.prevent="reload">
			Refresh
		</a>
	</div>
</template>
<script>
export default {
	name: "BuildSuccess",
	data() {
		return {
			is_shown: false
		};
	},
	methods: {
		show() {
			this.is_shown = true;
			if (this.timeout) {
				clearTimeout(this.timeout);
			}
			this.timeout = setTimeout(() => {
				this.hide();
			}, 10000);
		},
		hide() {
			this.is_shown = false;
		},
		reload() {
			window.location.reload();
		}
	}
};
</script>
<style>
.build-success-message {
	position: fixed;
	z-index: 9999;
	bottom: 0;
	right: 0;
	background: rgba(0, 0, 0, 0.6);
	border-radius: var(--border-radius);
	padding: 0.5rem 1rem;
	color: white;
	font-weight: 500;
	margin: 1rem;
}
</style>
