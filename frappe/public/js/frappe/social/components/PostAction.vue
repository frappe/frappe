<template>
	<div class="post-action-container text-muted">
		<div class="pin" v-if="is_pinnable">
			<i class="fa fa-thumb-tack" :class="{'pinned': is_pinned}" @click="$emit('toggle_pin')"></i>
		</div>
		<div class="pin" v-else-if="is_globally_pinnable">
			<i class="fa fa-thumb-tack" :class="{'pinned': is_globally_pinned}" @click="$emit('toggle_global_pin')"></i>
		</div>
		<div class="like" :class="{'liked': post_liked}" @click="$emit('toggle_like')">
				Like
		</div>
		<div class="comment" @click="$emit('toggle_comment')">
			Comment
		</div>
		<div >
			<span class="likes" :data-liked-by="JSON.stringify(split_string(liked_by))">{{ like_count }} likes</span>
			.
			<span>{{ comment_count }} comments</span>
		</div>
	</div>
</template>
<script>
export default {
	props: {
		'liked_by': {
			'type': String,
		},
		'comment_count': {
			'type': Number,
			'default': 0,
		},
		'is_globally_pinnable': {
			'type': Boolean,
			'default': false
		},
		'is_pinnable': {
			'type': Boolean,
			'default': false
		},
		'is_globally_pinned': {
			'type': Number,
			'default': 0
		},
		'is_pinned': {
			'type': Number,
			'default': 0
		}
	},
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
	.comment, .like, .pin {
		padding-right: 20px;
		cursor: pointer;
		span {
			padding-left: 5px;
		}
		i:hover, span:hover {
			color: black;
		}
	}
	.likes {
		cursor: pointer;
	}
	.liked {
		color: #7F7FFF;
		&:hover {
			color: lighten(#7F7FFF, 10%) !important;
		}
	}
	.pinned {
		color: black;
	}
}
</style>