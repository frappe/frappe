<template>
	<div>
		<div class="flex">
			<input class="fill-width" v-model="comment" type="text">
			<button class="btn btn-primary" @click="post_comment">Post</button>
		</div>
		<div class="flex" v-for="comment in comments" :key="comment.name">
			<span v-html="get_user_avatar(comment.owner)"></span>
			<span class="fill-width">{{ comment.content }}</span>
			<div class="text-muted" v-html="format_timestamp(comment.modified)"></div>
		</div>
	</div>
</template>
<script>
export default {
	props: ['comments'],
	data() {
		return {
			comment: ''
		}
	},
	methods: {
		get_user_avatar(user) {
			return frappe.avatar(user)
		},
		post_comment() {
			this.$emit('post_comment', this.comment);
			this.comment = '';
		},
		format_timestamp(timestamp) {
			return comment_when(timestamp, true)
		}
	}
}
</script>
<style>
</style>