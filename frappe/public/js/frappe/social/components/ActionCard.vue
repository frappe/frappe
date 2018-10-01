<template>
	<div class="action-card">
		<div class="content">
			<b>Add daily work summary</b><h6><span style="color: rgb(54, 65, 76);">Did you do something interesting or fun today?</span></h6>
			<h6><span style="color: rgb(54, 65, 76);">Worked on a cool hack or discovered a new feature?</span></h6>
			<h6><span style="color: rgb(54, 65, 76);">Sharing it with others is always good. Inspire and be inspired 😊</span></h6>
			<h6><span style="color: rgb(54, 65, 76);"><br></span></h6>
		</div>
		<div class="flex justify-flex-end">
			<a class="action" v-for="action in ['Reply', 'Dismiss']" :key=action href="">{{ action }}</a>
		</div>
	</div>
</template>
<script>
export default {
	data() {
		return {
		}
	}
}
</script>
<style lang="less" scoped>
.action-card {
	margin-bottom: 5px;
	max-width: 500px;
	max-height: 500px;
	min-height: 70px;
	border: 1px solid #c2c3c4;
	border-radius: 3px;
	padding: 15px 15px 5px 15px;
	.content {
		font-size: 14px;
		img, iframe {
			border-radius: 5px;
			border: none;
		}
	}
	.action {
		padding: 5px;
	}
}
</style>