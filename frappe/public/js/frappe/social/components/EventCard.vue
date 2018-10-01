<template>
	<div class="event-card">
		<div class="content" v-html="event.content"/>
	</div>
</template>
<script>
export default {
	props: ['event'],
}
</script>
<style lang="less" scoped>
.event-card {
	margin-bottom: 5px;
	max-width: 500px;
	max-height: 500px;
	min-height: 70px;
	overflow: scroll;
	text-align: center;
	border: 1px solid #c2c3c4;
	border-radius: 3px;
	padding: 10px 10px 5px 10px;
	.content {
		font-size: 14px;
		img, iframe {
			border-radius: 5px;
			border: none;
		}
	}
}
</style>