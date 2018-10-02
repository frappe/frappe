<template>
	<div class="backdrop">
		<img :src="src">
		<i class="fa fa-close close" @click="$root.$emit('hide_preview')"></i>
	</div>
</template>
<script>
export default {
	props: ['src'],
	created() {
		document.addEventListener('keyup', this.close_preview_on_escape);
	},
	destroyed() {
		document.removeEventListener('keyup', this.close_preview_on_escape);
	},
	methods: {
		close_preview_on_escape(e) {
			if (e.keyCode === 27) {
				this.$root.$emit('hide_preview')
			}
		}
	}
}
</script>
<style lang="less" scoped>
.backdrop {
	position: fixed;
	height: 100%;
	width: 100%;
	background: #0000006e;
	z-index: 1030;
	top: 0;
	right: 0;
	padding-top: 100px;
	img {
		margin: auto;
		display: block;
		width: 80%;
		max-width: 700px;
	}
	.close {
		position: absolute;
		top: 15px;
		right: 35px;
		color: #f1f1f1;
		font-size: 30px;
	}
}
</style>


