<template>
	<div class="post-action-container text-muted">
		<div class="reply">
			<i class="fa fa-reply" @click="$emit('new_reply')"></i>
			<span @click="$emit('toggle_reply')">{{ reply_count }}</span>
		</div>
		<div class="like" @click="$emit('like')">
			<i class="fa fa-heart"></i>
			<span>{{ like_count }}</span>
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
		'reply_count': {
			'type': Number,
			'default': 0,
		}
	},
}
</script>
<style lang='less' scoped>
.post-action-container {
	display: flex;
	justify-content: flex-end;
	.reply, .like {
		padding: 10px;
		span {
			margin-left: 5px;
		}
	}
}
</style>