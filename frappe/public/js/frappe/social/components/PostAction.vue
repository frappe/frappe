<template>
	<div class="post-action-container">
		<div class="like" @click="$emit('toggle_like')">
			<i class="octicon octicon-heart" :class="{'liked': post_liked}"></i>
			<span class="likes" :data-liked-by="JSON.stringify(split_string(liked_by))">{{ like_count }}</span>
		</div>
		<div class="comment" @click="$emit('toggle_comment')">
			<i class="octicon octicon-comment"></i>
			<span class="comment_count">{{ comment_count }}</span>
		</div>
	</div>
</template>
<script>
export default {
	props: [
		'liked_by',
		'comment_count',
	],
	computed: {
		like_count() {
			return this.split_string(this.liked_by).length;
		},
		post_liked() {
			return this.split_string(this.liked_by).includes(frappe.session.user);
		}
	},
	methods: {
		split_string(str) {
			return str && str !== '' ? str.split('\n') : []
		}
	}
}
</script>
<style lang='less' scoped>
.post-action-container {
	display: flex;
	background-color: #F6F6F6;
	padding: 10px;
	.comment, .like {
		padding-right: 20px;
		cursor: pointer;
		span {
			padding-left: 5px;
		}
		&:hover {
			color: #8d99a6;
		}
	}
	.like {
		color: #8d99a6;
	}
	.likes {
		cursor: pointer;
	}
	.liked {
		color: #fc4f51;
		&:hover {
			color: lighten(#fc4f51, 10%) !important;
		}
	}
	.pinned {
		color: black;
	}
}
</style>