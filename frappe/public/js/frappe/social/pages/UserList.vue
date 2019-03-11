<template>
	<div class="flex justify-center">
		<div class="col-md-6">
			<div class="flex justify-between padding search-bar">
				<div class="flex col-md-6">
					<button class="btn" @click="frappe.set_route('social', 'home')">← {{ __('Back') }}</button>
					<input type="text" class="form-control" :placeholder="__('Search for a user...')" v-model="search_text">
				</div>
			</div>
			<ul class="list-unstyled user-list">
				<li
					class="padding cursor-pointer flex user-card"
					v-for="user in filtered_users" :key="user.name"
					@click="go_to_profile_page(user.name)">
					<span v-html="get_avatar(user.name)"></span>
					<div class="user-details">
						{{ user.fullname }}
						<div class="text-muted text-medium" :class="{'italic': !user.bio}">{{ frappe.ellipsis(user.bio, 100) || 'No Bio'}}</div>
					</div>
				</li>
				<li class="text-muted" v-if="!filtered_users.length">{{__('No user found')}}</li>
			</ul>
		</div>
	</div>
</template>
<script>
export default {
	data() {
		return {
			users: [],
			search_text: ''
		}
	},
	computed: {
		filtered_users() {
			let filtered = this.users;
			if (this.search_text !== '') {
				filtered = filtered.filter(user => {
					if (user.fullname.toLowerCase().includes(this.search_text.toLowerCase())) {
						return true;
					}
				})
			}
			return filtered;
		}
	},
	created() {
		const standard_users = ['Administrator', 'Guest', 'guest@example.com'];
		this.users = frappe.boot.user_info;
		// delete standard users from the list
		standard_users.forEach(user => delete this.users[user]);
		this.users = Object.values(this.users);
	},
	methods: {
		get_avatar(user) {
			return frappe.avatar(user, 'avatar-medium')
		},
		go_to_profile_page(user) {
			frappe.set_route('social', 'profile', user)
		}
	}
}
</script>
<style lang="less" scoped>
.user-list {
	// similar to search bar height
	margin-top: 75px;
	.user-card {
		&:hover {
			border: 1px solid #d1d8dd;
		}
		border-radius: 5px;
		.user-details {
			margin-left: 10px;
			.italic {
				font-style: italic;
			}
		}
	}
}
.search-bar {
	position: fixed;
	background: white;
	height: 75px;
	text-align: center;
	div {
		margin: auto;
	}
	width: 100%;
	left: 0;
}
</style>



