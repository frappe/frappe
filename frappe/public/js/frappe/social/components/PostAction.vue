<template>
	<div class="post-action-container">
		<div class="like" @click="$emit('toggle_like')">
			<i class="octicon octicon-heart" :class="{'liked': post_liked}"></i>
			<span class="likes" :data-liked-by="liked_by_data">{{ like_count }}</span>
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
		},
		liked_by_data() {
			return JSON.stringify(this.split_string(this.liked_by));
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
		color: #8d99a6;
		span {
			padding: 5px;
		}
		&:hover {
			color: darken(#8d99a6, 10%);
		}
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