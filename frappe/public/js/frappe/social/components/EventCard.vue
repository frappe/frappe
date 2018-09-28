<template>
	<div class="event-card">
		<div class="content" v-html="event.content"/>
	</div>
</template>
<script>
export default {
	props: ['event'],
	data() {
		return {
		}
	},
	created() {
	},
	methods: {
	}
}
</script>
<style lang="less" scoped>
.event-card {
	margin: 10px 0;
	max-width: 500px;
	max-height: 500px;
	min-height: 70px;
	overflow: scroll;
	text-align: center;
	cursor: pointer;
	border: 1px solid #c2c3c4;
	border-radius: 15px;
	padding: 15px 15px 5px 15px;
	.content {
		font-size: 14px;
		img, iframe {
			border-radius: 5px;
			border: none;
		}
	}
}
</style>