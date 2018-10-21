<template>
	<div class="flex flex-column">
		<div class="user-details">
			<div class="user-avatar" v-html="user_avatar"></div>
			<a class="user_name" @click="go_to_profile_page()">{{ user.fullname }}</a>
		</div>
		<div class="links" v-if="frequently_visited_list.length">
			<div class="muted-title">
				{{ __('Frequently Visited Links') }}
			</div>
			<div class="flex flex-column">
				<a class="route-link"
					@click.prevent="goto_list(route_obj.route)"
					v-for="route_obj in frequently_visited_list"
					:key="route_obj.route">
					{{ get_label(route_obj.route) }}
				</a>
			</div>
		</div>
	</div>
</template>
<script>
export default {
	data() {
		return {
			frequently_visited_list: [],
			user: frappe.user_info(frappe.session.user),
			user_avatar: frappe.avatar(this.user_id, 'avatar-xl')
		}
	},
	created() {
		this.set_frequently_visited_list()
	},
	methods: {
		goto_list(route) {
			frappe.set_route(route);
		},
		set_frequently_visited_list() {
			frappe.xcall('frappe.social.doctype.post.post.frequently_visited_links')
				.then(data => {
					this.frequently_visited_list = data;
				})
		},
		get_label(route) {
			return frappe.utils.get_route_label(route);
		},
		go_to_profile_page() {
			frappe.set_route('social', 'profile', this.user.name)
		}
	}
}
</script>
<style lang="less" scoped>
.route-link {
	margin: 0px 10px 10px 0;
	text-transform: capitalize;
}
.stats {
	min-height: 150px
}
.links {
	margin-top: 20px;
}
.user-details {
	.user-avatar {
		/deep/.avatar-xl {
			height: 150px;
			width: 150px;
		}
	}
	.user_name {
		display: block;
		margin-top: 10px;
		font-size: 2rem;
		font-weight: 600
	}
}
</style>

