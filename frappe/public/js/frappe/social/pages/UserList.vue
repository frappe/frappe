<template>
	<div class="flex justify-center">
		<div class="col-md-6">
			<div class="flex justify-between padding">
				<input type="text" class="form-control" :placeholder="__('Search for a user...')" v-model="search_text">
			</div>
			<ul class="list-unstyled">
				<li
					class="padding cursor-pointer"
					v-for="user in filtered_users" :key="user.name"
					@click="go_to_profile_page(user.name)">
					<span
						v-html="get_avatar(user.name)">
					</span>
					{{ user.fullname }}
				</li>
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
		const standard_users = ['Administrator', 'Guest'];
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


