<template>
	<div class="user-list-container">
		<ul class="list-unstyled user-list">
			<li class="user-card user-list-header text-medium">
				<span class="user-details text-muted">
					{{ __('User') }}
				</span>
				<span class="user-points text-muted">
					{{ __('Energy Points') }}
				</span>
				<span class="user-points text-muted">
					{{ __('Review Points') }}
				</span>
				<span class="user-points text-muted">
					{{ __('Points Given') }}
				</span>
			</li>
			<li
				v-for="user in filtered_users"
				:key="user.name"
				@click="toggle_log(user.name)">
				<div class="user-card">
					<div class="user-details flex">
						<span v-html="get_avatar(user.name)"></span>
						<span>
							<a @click="go_to_profile_page(user.name)">{{ user.fullname }}</a>
							<div class="text-muted text-medium" :class="{'italic': !user.bio}">
								{{ frappe.ellipsis(user.bio, 100) || 'No Bio'}}
							</div>
						</span>
					</div>
					<span class="text-muted text-nowrap user-points">
						{{ user.energy_points }}
					</span>
					<span class="text-muted text-nowrap user-points">
						{{ user.review_points }}
					</span>
					<span class="text-muted text-nowrap user-points">
						{{ user.given_points }}
					</span>
				</div>
				<energy-point-history
					v-if="show_log_for===user.name"
					class="energy-point-history"
					:user="user.name">
				</energy-point-history>
			</li>
			<li class="user-card text-muted" v-if="!filtered_users.length">{{__('No user found')}}</li>
		</ul>
	</div>
</template>
<script>
import EnergyPointHistory from '../components/EnergyPointHistory.vue';
export default {
	components: {
		EnergyPointHistory
	},
	data() {
		return {
			users: [],
			filter_users_by: null,
			sort_users_by: 'energy_points',
			sort_order: 'desc',
			show_log_for: null
		}
	},
	computed: {
		filtered_users() {
			let filtered = this.users.slice();

			if (this.filter_users_by) {
				filtered = filtered.filter(user =>
					user.fullname.toLowerCase().includes(this.filter_users_by.toLowerCase())
				)
			}

			if (this.sort_users_by) {
				filtered.sort((a, b) => {
					const value_a = a[this.sort_users_by];
					const value_b = b[this.sort_users_by];

					let return_value = 0;
					if (value_a > value_b) {
						return_value = 1;
					}

					if (value_a < value_b) {
						return_value = -1;
					}

					if (this.sort_order === 'desc') {
						return_value = -return_value
					}

					return return_value
				});
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
		this.fetch_users_energy_points_and_update_users();
		frappe.realtime.on('update_points', () => {
			this.fetch_users_energy_points_and_update_users();
		});
	},
	methods: {
		get_avatar(user) {
			return frappe.avatar(user, 'avatar-medium')
		},
		go_to_profile_page(user) {
			frappe.set_route('social', 'profile', user)
		},
		fetch_users_energy_points_and_update_users() {
			frappe.xcall(
				'frappe.social.doctype.energy_point_log.energy_point_log.get_user_energy_and_review_points'
			).then(data => {
				let users = this.users.slice();
				this.users = users.map(user => {
					const points = data[user.name] || {};
					user.energy_points = points.energy_points || 0;
					user.review_points = points.review_points || 0;
					user.given_points = points.given_points || 0;
					return user;
				});
			});
		},
		toggle_log(user) {
			if (this.show_log_for === user) {
				this.show_log_for = null
			} else {
				this.show_log_for = user
			}
		}
	}
}
</script>
<style lang="less" scoped>
@import "frappe/public/less/variables";
.user-list {
	border-left: 1px solid @border-color;
	border-right: 1px solid @border-color;
	.user-card {
		display: flex;
		cursor: pointer;
		padding: 12px 15px;
		border-bottom: 1px solid @border-color;
		.user-details {
			flex: 1;
			.italic {
				font-style: italic;
			}
		}
	}
}
.user-points {
	flex: 0 0 20%;
	text-align: right;
	align-self: center;
}
.user-list-header {
	background-color: @light-bg;
}
.search-bar {
	position: sticky;
	top: 0;
	background: white;
	height: 75px;
	text-align: center;
	div {
		margin: auto;
	}
	width: 100%;
	left: 0;
}
.energy-point-history {
	border-bottom: 1px solid @border-color;
	max-height: 300px;
	overflow: scroll;
	background-color: @light-bg;
}
</style>



