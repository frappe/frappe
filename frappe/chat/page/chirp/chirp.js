frappe.pages.chirp.on_page_load = (parent) => {
	const page = new frappe.ui.Page({
		parent: parent,
		 title: 'Chat'
	})

	frappe.pages.chirp.chirp = new frappe.Chirp(parent)
}

frappe.Chirp = class {
	constructor (parent) {
		this.$parent  = $(parent)
		
		this.$sidebar = this.$parent.find('.layout-side-section')
		
		this.make()
	}

	make ( ) {
		this.make_sidebar()
	}

	make_sidebar ( ) {
		this.make_sidebar_header()
		this.make_sidebar_room_list()
	}

	make_sidebar_header ( ) {
		this.make_sidebar_user()
		this.make_sidebar_searchbar()
	}

	make_sidebar_user ( ) {
		const template =
		`
		<div class="dropdown">
			<button class="btn btn-default btn-sm btn-block dropdown-toggle" data-toggle="dropdown">
				
			</button>
			<ul class="dropdown-menu">
				${ frappe.Chirp.STATUSES.map((status) => `<li><a data-status="${status.name}"><span class="indicator ${status.color}"></span> ${status.name}</a></li>`).join("") }
			</ul>
		</div>
		`
		const that = this
		this.$sidebar_dropdown_status = $(template)
		this.$sidebar_dropdown_status.css({
			'margin-top': '15px'
		})
		this.$sidebar_dropdown_status.find('.dropdown-menu li a').click(function () {
			const status = $(this).data('status')
			that.set_user_status(status)
		})

		frappe.call({
			method: 'frappe.chat.setting.get_user_status',
			args: {
				user: frappe.session.user
			},
			callback: (r) => {
				const status = r.message
				this.set_user_status(status)
			}
		})

		this.$sidebar.append(this.$sidebar_dropdown_status)
	}

	set_user_status (status) {
		frappe.call({
			method: 'frappe.chat.setting.set_user_status',
			args: {
				user: frappe.session.user,
				status: status
			},
			callback: (r) => {
				this.make_user_status(status)
			},
			error: ( ) => {
				// TODO: Handle.
			}
		})
	}

	make_user_status (status) {
		const meta = frappe.Chirp.STATUSES.find(s => s.name === status)
		this.$sidebar_dropdown_status.find('.btn').html(
			`<span class="indicator ${meta.color}"></span> ${meta.name}`
		)
	}

	make_sidebar_searchbar ( ) {
		const template = 
		`
		<form>
			<div class="input-group input-group-sm">

				<input class="form-control" placeholder="Search"/>
				<div class="input-group-btn">
					<button class="btn btn-primary dropdown-toggle" data-toggle="dropdown">
						<i class="octicon octicon-pencil"/>
					</button>
					<div class="dropdown-menu dropdown-menu-right">
						<li>
							<a data-action="new-message">
								<span class="octicon octicon-comment"/> New Message
							</a>
						</li>
						<li>
							<a data-action="new-group">
								<span class="octicon octicon-organization"/> New Group
							</a>
						</li>
					</div>
				</div>
			</div>
		</form>
		`
		this.$sidebar_searchbar = $(template)
		this.$sidebar_searchbar.css({
			'margin-top': 15,
		})
		this.$sidebar_searchbar.find('.dropdown-menu').css({
			'min-width': 150
		})

		this.$sidebar_searchbar.submit((e) => {
			if ( !e.isDefaultPrevented() )
				e.preventDefault()
		})

		const that = this
		this.$sidebar_searchbar.find('.dropdown-menu li a').click(function ( ) {
			const action = $(this).data('action')

			if ( action === 'new-message' ) {
				that.on_click_new_message()
			} else if ( action === 'new-group' ) {
				that.on_click_new_group()
			}
		})

		this.$sidebar.append(this.$sidebar_searchbar)
	}

	make_sidebar_room_list ( ) {
		frappe.call({
			method: 'frappe.chat.doctype.chat_room.chat_room.get',
			callback: (r) => {
				const rooms    = r.message
				const template =
				`
				<div class="list-group">
					${ rooms.map(room => this.render_sidebar_room_list_item(room)).join("") }
				</div>
				`

				this.$sidebar_room_list = $(template)
				this.$sidebar_room_list.css({
					'margin-top': '15px'
				})

				this.$sidebar.append(this.$sidebar_room_list)
			},
			error: ( ) => {
				// TODO: Handle.
			}
		})
	}

	render_sidebar_room_list_item (room) {
		const template = 
		`
		<a class="list-group-item">
			${room.name}
		</a>
		`

		return template
	}

	on_click_new_message ( ) {
		frappe.call({
			method: 'frappe.chat.user.get_contact_list',
			callback: (r) => {
				if ( r.message ) {
					const contacts = r.message
					const template = $(this.render_contact_list(contacts))
					
					const dialog = new frappe.ui.Dialog({
						title: __(`New Message`)
					})
					$(dialog.body).append(template)

					dialog.set_primary_action(() => {
						
					})
					dialog.show()
				}
			}
		})
	}

	render_contact_list (contacts) {
		const template = 
		`
		<div class="list-group">
			${ contacts.map(contact => 
				`<a class="list-group-item">
					<div class="h6">
						${contact.first_name} ${contact.last_name !== null ? contact.last_name : ""}
					</div>
					${contact.last_active ? `<small>${contact.last_active}</small>` : ""}
				</a>
				`
			).join("")
			}
		</div>
		`

		return template
	}

	on_click_new_group ( ) {
		const dialog = new frappe.ui.Dialog({
			title: __(`New Group`)
		})
		dialog.set_primary_action(() => {
			console.log('New Group')
		})
		dialog.show()
	}
}
frappe.Chirp.STATUSES = [
	{
		 name: 'Online',
		color: 'green'
	},
	{
		 name: 'Away',
		color: 'yellow'
	},
	{
		 name: 'Busy',
		color: 'red'
	},
	{
		 name: 'Invisible',
		color: 'grey'
	}
]