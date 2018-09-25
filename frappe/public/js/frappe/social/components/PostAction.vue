<template>
	<div class="flex text-muted justify-center">
		<div class="comment" @click="$emit('comment')">
			<i class="fa fa-reply"></i>
			<span>{{comment_count}}</span>
		</div>
		<div class="like" @click="$emit('like')">
			<i class="fa fa-heart"></i>
			<span>{{like_count}}</span>
		</div>
	</div>
</template>
<script>
export default {
	props: {
		'like_count': {
			'type': Number,
			'default': 0,
		},
		'comment_count': {
			'type': Number,
			'default': 0,
		}
	},
}
</script>
<style lang='less' scoped>
.comment, .like{
	padding: 10px;
	span {
		margin-left: 5px;
	}
}
</style>