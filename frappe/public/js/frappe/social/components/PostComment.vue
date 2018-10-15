<template>
	<div>
		<div class="comment-box">
			<div class="text-muted comment-label">Add a comment</div>
			<textarea v-model="comment_content"></textarea>
			<button class="pull-right btn btn-primary btn-sm" @click="$emit('create_comment', comment_content); comment_content = ''">Comment</button>
		</div>
		<div class="comment-list">
			<div class="comment" v-for="comment in comments" :key="comment.name">
				<span class="pull-right text-muted" v-html="get_time(comment.creation)"></span>
				<span v-html="get_avatar(comment.owner)"></span>
				<span>{{comment.content}}</span>
			</div>
		</div>
	</div>
</template>
<script>
export default {
	props: ['comments'],
	data() {
		return {
			comment_content: ''
		}
	},
	methods: {
		get_avatar(user) {
			return frappe.avatar(user)
		},
		get_time(timestamp) {
			return comment_when(timestamp)
		},
	}
}
</script>
<style lang="less" scoped>
.comment-box {
	.comment-label {
		margin-bottom: 5px;
	}
	textarea {
		width: 100%;
		border-radius: 4px;
		outline: none;
		border: none;
		margin-bottom: 5px;
		clear: both;
		height: 40px;
		padding: 5px;
		border: 1px solid #d1d8dd;
	}
	button {
		padding: 2px 5px;
		font-size: 10px;
	}
}
.comment-list {
	margin-top: 30px;
	clear: both;
	.comment {
		padding: 5px 0;
	}
}
</style>
