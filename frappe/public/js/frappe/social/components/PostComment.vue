<template>
	<div>
		<div class="comment-box flex-column">
			<div class="text-muted comment-label">{{ __('Add a comment') }}</div>
			<textarea v-model="comment_content"></textarea>
			<button
				:disabled="comment_content === ''"
				class="btn btn-primary btn-sm"
				@click="create_comment">
				{{ __('Comment') }}
			</button>
		</div>
		<div v-if="comments.length" class="comment-list">
			<div class="comment" v-for="comment in comments" :key="comment.name">
				<span
					class="pull-right text-muted"
					v-html="get_time(comment.creation)">
				</span>
				<span
					class="cursor-pointer"
					@click="go_to_profile_page(comment.owner)"
					v-html="get_avatar(comment.owner)">
				</span>
				<span>{{ comment.content }}</span>
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
			return comment_when(timestamp, true)
		},
		create_comment() {
			this.$emit('create_comment', this.comment_content);
			this.comment_content = '';
		},
		go_to_profile_page(user) {
			frappe.set_route('social', 'profile', user)
		}
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
		margin-bottom: 15px;
		height: 60px;
		padding: 5px;
		border: 1px solid #d1d8dd;
		resize: none;
	}
	button {
		padding: 2px 5px;
		font-size: 10px;
		align-self: flex-end;
	}
}
.comment-list {
	margin-top: 10px;
	.comment {
		padding: 5px 0;
	}
}
</style>
