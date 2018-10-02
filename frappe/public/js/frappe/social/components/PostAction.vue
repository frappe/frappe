<template>
	<div class="post-action-container text-muted">
		<div class="pin" v-if="is_pinnable">
			<i class="fa fa-thumb-tack" :class="{'pinned': is_pinned}" @click="$emit('toggle_pin')"></i>
		</div>
		<div class="reply">
			<i class="fa fa-reply" @click="$emit('new_reply')"></i>
			<span @click="$emit('toggle_reply')">{{ reply_count }}</span>
		</div>
		<div class="like" @click="$emit('toggle_like');">
			<i class="fa fa-heart" :class="{'liked': post_liked}"></i>
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
		},
		'post_liked': {
			'type': Boolean,
			'default': true
		},
		'is_pinnable': {
			'type': Boolean,
			'default': false
		},
		'is_pinned': {
			'type': Number,
			'default': 0
		}
	},
}
</script>
<style lang='less' scoped>
.post-action-container {
	clear: both;
	display: flex;
	justify-content: flex-end;
	.reply, .like, .pin {
		cursor: pointer;
		padding: 10px;
		span {
			margin-left: 5px;
		}
		i:hover, span:hover {
			color: black;
		}
	}
	.liked {
		color: red;
		&:hover {
			color: lighten(red, 20%) !important;
		}
	}
	.pinned {
		color: black;
	}
}
</style>