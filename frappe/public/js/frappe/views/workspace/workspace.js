import EditorJS from '@editorjs/editorjs';
import Undo from 'editorjs-undo';

frappe.standard_pages['Workspaces'] = function() {
	var wrapper = frappe.container.add_page('Workspaces');

	frappe.ui.make_app_page({
		parent: wrapper,
		name: 'Workspaces',
		title: __("Workspace"),
	});

	frappe.workspace = new frappe.views.Workspace(wrapper);
	$(wrapper).bind('show', function () {
		frappe.workspace.show();
	});
};

frappe.views.Workspace = class Workspace {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = wrapper.page;
		this.blocks = frappe.wspace_block.blocks;
		this.is_read_only = true;
		this.new_page = null;
		this.pages = {};
		this.sorted_public_items = [];
		this.sorted_private_items = [];
		this.current_page = {};
		this.sidebar_items = {
			'public': {},
			'private': {}
		};
		this.sidebar_categories = [
			'My Workspaces',
			'Public'
		];

		this.prepare_container();
		this.setup_pages();
	}

	prepare_container() {
		let list_sidebar = $(`
			<div class="list-sidebar overlay-sidebar hidden-xs hidden-sm">
				<div class="desk-sidebar list-unstyled sidebar-menu"></div>
			</div>
		`).appendTo(this.wrapper.find(".layout-side-section"));
		this.sidebar = list_sidebar.find(".desk-sidebar");
		this.body = this.wrapper.find(".layout-main-section");
	}

	async setup_pages(reload) {
		this.create_page_skeleton();
		this.create_sidebar_skeleton();
		this.sidebar_pages = !this.discard ? await this.get_pages() : this.sidebar_pages;
		this.all_pages = this.sidebar_pages.pages;
		this.has_access = this.sidebar_pages.has_access;

		this.all_pages.forEach(page => {
			page.is_editable = !page.public || this.has_access;
		});

		this.public_pages = this.all_pages.filter(page => page.public);
		this.private_pages = this.all_pages.filter(page => !page.public);

		if (this.all_pages) {
			frappe.workspaces = {};
			for (let page of this.all_pages) {
				frappe.workspaces[frappe.router.slug(page.name)] = {title: page.title};
			}
			if (this.new_page && this.new_page.name) {
				if (!frappe.workspaces[frappe.router.slug(this.new_page.label)]) {
					this.new_page = { 
						name: this.all_pages[0].title, 
						public: this.all_pages[0].public 
					};
				}

				let pre_url = this.new_page.public ? '' : 'private/';
				let route = pre_url + frappe.router.slug(this.new_page.name);
				frappe.set_route(route);

				this.new_page = null;
			}
			this.make_sidebar();
			reload && this.show();
		}
	}

	get_pages() {
		return frappe.xcall("frappe.desk.desktop.get_wspace_sidebar_items");
	}

	sidebar_item_container(item) {
		return $(`
			<div class="sidebar-item-container ${item.is_editable ? "is-draggable" : ""}" item-parent="${item.parent_page}" item-name="${item.title}" item-public="${item.public || 0}">
				<div class="desk-sidebar-item standard-sidebar-item ${item.selected ? "selected" : ""}">
					<a
						href="/app/${item.public ? frappe.router.slug(item.title) : 'private/'+frappe.router.slug(item.title) }"
						class="item-anchor ${item.is_editable ? "" : "block-click" }" title="${__(item.title)}"
					>
						<span class="sidebar-item-icon" item-icon=${item.icon || "folder-normal"}>${frappe.utils.icon(item.icon || "folder-normal", "md")}</span>
						<span class="sidebar-item-label">${__(item.title)}<span>
					</a>
					<div class="sidebar-item-control"></div>
				</div>
				<div class="sidebar-child-item nested-container"></div>
			</div>
		`);
	}

	make_sidebar() {
		if (this.sidebar.find('.standard-sidebar-section')[0]) {
			this.sidebar.find('.standard-sidebar-section').remove();
		}

		this.sidebar_categories.forEach(category => {
			let root_pages = this.public_pages.filter(page => page.parent_page == '' || page.parent_page == null);
			if (category != 'Public') {
				root_pages = this.private_pages.filter(page => page.parent_page == '' || page.parent_page == null);
			}
			this.build_sidebar_section(category, root_pages);
		});

		// Scroll sidebar to selected page if it is not in viewport.
		this.sidebar.find('.selected').length && !frappe.dom.is_element_in_viewport(this.sidebar.find('.selected'))
			&& this.sidebar.find('.selected')[0].scrollIntoView();

		this.remove_sidebar_skeleton();
	}

	build_sidebar_section(title, root_pages) {
		let sidebar_section = $(`<div class="standard-sidebar-section nested-container"></div>`);

		let $title = $(`<div class="standard-sidebar-label">
			<span>${frappe.utils.icon("small-down", "xs")}</span>
			<span class="section-title">${__(title)}<span>
		</div>`).appendTo(sidebar_section);
		this.prepare_sidebar(root_pages, sidebar_section, this.sidebar);

		$title.on('click', (e) => {
			let icon = $(e.target).find("span use").attr("href")==="#icon-small-down" ? "#icon-right" : "#icon-small-down";
			$(e.target).find("span use").attr("href", icon);
			$(e.target).parent().find('.sidebar-item-container').toggleClass('hidden');
		});

		if (Object.keys(root_pages).length === 0) {
			sidebar_section.addClass('hidden');
		}
	}

	prepare_sidebar(items, child_container, item_container) {
		items.forEach(item => this.append_item(item, child_container));
		child_container.appendTo(item_container);
	}

	append_item(item, container) {
		let is_current_page = frappe.router.slug(item.title) == frappe.router.slug(this.get_page_to_show().name)
			&& item.public == this.get_page_to_show().public;
		item.selected = is_current_page;
		if (is_current_page) {
			this.current_page = { name: item.title, public: item.public };
		}

		let $item_container = this.sidebar_item_container(item);
		let sidebar_control = $item_container.find('.sidebar-item-control');

		this.add_sidebar_actions(item, sidebar_control);
		let pages = item.public ? this.public_pages : this.private_pages;

		let child_items = pages.filter(page => page.parent_page == item.title);
		if (child_items.length > 0) {
			let child_container = $item_container.find('.sidebar-child-item');
			child_container.addClass('hidden');
			this.prepare_sidebar(child_items, child_container, $item_container);
		}

		$item_container.appendTo(container);
		this.sidebar_items[item.public ? 'public' : 'private'][item.title] = $item_container;

		if ($item_container.parent().hasClass('hidden') && is_current_page) {
			$item_container.parent().toggleClass('hidden');
		}

		this.add_drop_icon(item, sidebar_control, $item_container);
	}

	add_drop_icon(item, sidebar_control, item_container) {
		let drop_icon = 'small-down';
		if (item_container.find(`[item-name="${this.current_page.name}"]`).length) {
			drop_icon = 'small-up';
		}

		let $child_item_section = item_container.find('.sidebar-child-item');
		let $drop_icon = $(`<span class="drop-icon hidden">${frappe.utils.icon(drop_icon, "sm")}</span>`)
			.appendTo(sidebar_control);
		let pages = item.public ? this.public_pages : this.private_pages;
		if (pages.some(e => e.parent_page == item.title)) {
			$drop_icon.removeClass('hidden');
			$drop_icon.on('click', () => {
				let icon = $drop_icon.find("use").attr("href")==="#icon-small-down" ? "#icon-small-up" : "#icon-small-down";
				$drop_icon.find("use").attr("href", icon);
				$child_item_section.toggleClass("hidden");
			});
		}
	}

	show() {
		if (!this.all_pages) {
			// pages not yet loaded, call again after a bit
			setTimeout(() => this.show(), 100);
			return;
		}

		let page = this.get_page_to_show();
		this.page.set_title(`${__(page.name)}`);

		this.update_selected_sidebar(this.current_page, false); //remove selected from old page
		this.update_selected_sidebar(page, true); //add selected on new page

		this.show_page(page);
	}

	update_selected_sidebar(page, add) {
		let section = page.public ? 'public' : 'private';
		if (this.sidebar && this.sidebar_items[section] && this.sidebar_items[section][page.name]) {
			let $sidebar = this.sidebar_items[section][page.name];
			let pages = page.public ? this.public_pages : this.private_pages;
			let sidebar_page = pages.find(p => p.title == page.name);

			if (add) {
				$sidebar[0].firstElementChild.classList.add("selected");
				if (sidebar_page) sidebar_page.selected = true;

				// open child sidebar section if closed 
				$sidebar.parent().hasClass('hidden') &&
					$sidebar.parent().removeClass('hidden');

				this.current_page = { name: page.name, public: page.public };
				localStorage.current_page = page.name;
				localStorage.is_current_page_public = page.public;
			} else {
				$sidebar[0].firstElementChild.classList.remove("selected");
				if (sidebar_page) sidebar_page.selected = false;
			}
		}
	}

	get_data(page) {
		return frappe.xcall("frappe.desk.desktop.get_desktop_page", {
			page: page
		}).then(data => {
			this.page_data = data;

			// caching page data
			this.pages[page.name] && delete this.pages[page.name];
			this.pages[page.name] = data;

			if (!this.page_data || Object.keys(this.page_data).length === 0) return;

			if (this.page_data.charts && this.page_data.charts.items.length === 0) return; 

			return frappe.dashboard_utils.get_dashboard_settings().then(settings => {
				if (settings) {
					let chart_config = settings.chart_config ? JSON.parse(settings.chart_config) : {};
					this.page_data.charts.items.map(chart => {
						chart.chart_settings = chart_config[chart.chart_name] || {};
					});
					this.pages[page.name] = this.page_data;
				}
			});
		});
	}

	get_page_to_show() {
		let default_page;

		if (localStorage.current_page && this.all_pages.filter(page => page.title == localStorage.current_page).length != 0) {
			default_page = { name: localStorage.current_page, public: localStorage.is_current_page_public == 'true' };
		} else if (Object.keys(this.all_pages).length !== 0) {
			default_page = { name: this.all_pages[0].title, public: true };
		} else {
			default_page = { name: "Build", public: true };
		}

		let page = (frappe.get_route()[1] == 'private' ? frappe.get_route()[2] : frappe.get_route()[1]) || default_page.name;
		let is_public = frappe.get_route()[1] ? frappe.get_route()[1] != 'private' : default_page.public;
		return { name: page, public: is_public };
	}

	async show_page(page) {
		if (!this.body.find('#editorjs')[0]) {
			this.$page = $(`
				<div id="editorjs" class="desk-page page-main-content"></div>
			`).appendTo(this.body);
		}

		if (this.all_pages) {
			this.create_page_skeleton();
			let pages = page.public ? this.public_pages : this.private_pages;
			let current_page = pages.filter(p => p.title == page.name)[0];
			this.setup_actions(page);
			this.content = current_page && JSON.parse(current_page.content);

			this.add_custom_cards_in_content();

			$('.item-anchor').addClass('disable-click');

			if (this.pages && this.pages[current_page.name]) {
				this.page_data = this.pages[current_page.name];
			} else {
				await this.get_data(current_page);
			}

			this.prepare_editorjs();
			$('.item-anchor').removeClass('disable-click');
			this.remove_page_skeleton();
		}
	}

	add_custom_cards_in_content() {
		let index = -1;
		this.content.find((item, i) => {
			if (item.type == 'card') index = i;
		});
		if (index !== -1) {
			this.content.splice(index+1, 0, {"type": "card", "data": {"card_name": "Custom Documents", "col": 4}});
			this.content.splice(index+2, 0, {"type": "card", "data": {"card_name": "Custom Reports", "col": 4}});
		}
	}

	prepare_editorjs() {
		if (this.editor) {
			this.editor.isReady.then(() => {
				this.editor.configuration.tools.chart.config.page_data = this.page_data;
				this.editor.configuration.tools.shortcut.config.page_data = this.page_data;
				this.editor.configuration.tools.card.config.page_data = this.page_data;
				this.editor.configuration.tools.onboarding.config.page_data = this.page_data;
				this.editor.render({ blocks: this.content || [] });
			});
		} else {
			this.initialize_editorjs(this.content);
		}
	}

	setup_actions(page) {
		let pages = page.public ? this.public_pages : this.private_pages;
		let current_page = pages.filter(p => p.title == page.name)[0];

		if (!this.is_read_only) {
			this.setup_customization_buttons(current_page);
			return;
		}

		this.clear_page_actions();

		current_page.is_editable && this.page.set_secondary_action(__("Edit"), async () => {
			if (!this.editor || !this.editor.readOnly) return;
			this.is_read_only = false;
			await this.editor.readOnly.toggle();
			this.editor.isReady.then(() => {
				this.initialize_editorjs_undo();
				this.setup_customization_buttons(current_page);
				this.show_sidebar_actions();
				this.make_sidebar_sortable();
				this.make_blocks_sortable();
			});
		});

		this.page.add_inner_button(__("Create Workspace"), () => {
			this.initialize_new_page();
		});
	}

	initialize_editorjs_undo() {
		this.undo = new Undo({ editor: this.editor });
		this.undo.initialize({ blocks: this.content || [] });
		this.undo.readOnly = false;
	}

	clear_page_actions() {
		this.page.clear_primary_action();
		this.page.clear_secondary_action();
		this.page.clear_inner_toolbar();
	}

	setup_customization_buttons(page) {
		this.clear_page_actions();

		page.is_editable && this.page.set_primary_action(
			__("Save Customizations"),
			() => {
				this.clear_page_actions();
				this.undo.readOnly = true;
				this.save_page();
				this.editor.readOnly.toggle();
				this.is_read_only = true;
			},
			null,
			__("Saving")
		);

		this.page.set_secondary_action(
			__("Discard"),
			async () => {
				this.discard = true;
				this.clear_page_actions();
				await this.editor.readOnly.toggle();
				this.is_read_only = true;
				this.reload();
				frappe.show_alert({ message: __("Customizations Discarded"), indicator: "info" });
			}
		);

		page.name && this.page.add_inner_button(__("Settings"), () => {
			frappe.set_route(`workspace/${page.name}`);
		});
	}

	show_sidebar_actions() {
		this.sidebar.find('.standard-sidebar-section').addClass('show-control');
	}

	add_sidebar_actions(item, sidebar_control) {
		if (!item.is_editable) {
			$(`<span class="sidebar-info">${frappe.utils.icon("lock", "sm")}</span>`)
				.appendTo(sidebar_control);
			sidebar_control.parent().click(() => {
				!this.is_read_only && frappe.show_alert({
					message: __("Only Workspace Manager can sort or edit this page"),
					indicator: 'info'
				}, 5);
			});
		} else {
			frappe.utils.add_custom_button(
				frappe.utils.icon('drag', 'xs'),
				null,
				"drag-handle",
				`${__('Drag')}`,
				null,
				sidebar_control
			);

			this.add_settings_button(item, sidebar_control);
		}
	}

	edit_page(item) {
		this.public_parent_pages = ['', ...this.public_pages.filter(page => !page.parent_page).map(page => page.title)];
		this.private_parent_pages = ['', ...this.private_pages.filter(page => !page.parent_page).map(page => page.title)];
		var me = this;
		let old_item = item;
		const d = new frappe.ui.Dialog({
			title: __('Update Details'),
			fields: [
				{
					label: __('Title'),
					fieldtype: 'Data',
					fieldname: 'title',
					reqd: 1,
					default: item.title
				},
				{
					label: __('Parent'),
					fieldtype: 'Select',
					fieldname: 'parent',
					options: item.public ? this.public_parent_pages : this.private_parent_pages,
					default: item.parent_page
				},
				{
					label: __('Public'),
					fieldtype: 'Check',
					fieldname: 'is_public',
					depends_on: `eval:${this.has_access}`,
					default: item.public,
					onchange: function() {
						d.set_df_property('parent', 'options',
							this.get_value() ? me.public_parent_pages : me.private_parent_pages);
					}
				},
				{
					fieldtype: 'Column Break'
				},
				{
					label: __('Icon'),
					fieldtype: 'Icon',
					fieldname: 'icon',
					default: item.icon
				},
			],
			primary_action_label: __('Update'),
			primary_action: (values) => {
				let is_title_changed = values.title != old_item.title;
				let is_section_changed = values.is_public != old_item.public;
				if ((is_title_changed || is_section_changed) && !this.validate_page(values, old_item)) return;
				d.hide();

				frappe.call({
					method: "frappe.desk.doctype.workspace.workspace.update_page",
					args: {
						name: old_item.name,
						title: values.title,
						icon: values.icon || '',
						parent: values.parent || '',
						public: values.is_public || 0,
					}
				});

				this.update_sidebar(old_item, values);

				if (this.make_page_selected) {
					let pre_url = values.is_public ? '' : 'private/';
					let route = pre_url + frappe.router.slug(values.title);
					frappe.set_route(route);

					this.make_page_selected = false;
				}

				this.make_sidebar();
				this.show_sidebar_actions();
			}
		});
		d.show();
	}

	update_sidebar(old_item, new_item) {
		let is_section_changed = old_item.public != (new_item.is_public || 0);
		let is_title_changed = old_item.title != new_item.title;
		let new_updated_item = {...old_item};

		let pages = old_item.public ? this.public_pages : this.private_pages;

		let child_items = pages.filter(page => page.parent_page == old_item.title);

		this.make_page_selected = old_item.selected;

		new_updated_item.title = new_item.title;
		new_updated_item.icon = new_item.icon;
		new_updated_item.parent_page = new_item.parent || "";
		new_updated_item.public = new_item.is_public;

		if (is_title_changed || is_section_changed){
			if (new_item.is_public) {
				new_updated_item.name = new_item.title;
				new_updated_item.label = new_item.title;
				new_updated_item.for_user = "";
			} else {
				let user = frappe.session.user;
				new_updated_item.name = `${new_item.title}-${user}`;
				new_updated_item.label = `${new_item.title}-${user}`;
				new_updated_item.for_user = user;
			}

			this.update_cached_values(old_item, new_updated_item);
		}

		if (child_items.length) {
			child_items.forEach(child => {
				child.parent_page = new_item.title;
				is_section_changed && this.update_child_sidebar(child, new_item);
			});
		}
	}

	update_child_sidebar(child, new_item) {
		let old_child = {...child};
		this.make_page_selected = child.selected;

		child.public = new_item.is_public;
		if (new_item.is_public) {
			child.name = child.title;
			child.label = child.title;
			child.for_user = "";
		} else {
			let user = frappe.session.user;
			child.name = `${child.title}-${user}`;
			child.label = `${child.title}-${user}`;
			child.for_user = user;
		}

		this.update_cached_values(old_child, child);
	}

	update_cached_values(old_item, new_item) {
		let [from_pages, to_pages] = old_item.public ? 
			[this.public_pages, this.private_pages] : [this.private_pages, this.public_pages];
		
		let old_item_index = from_pages.findIndex(page => page.title == old_item.title);

		// update frappe.workspaces
		if (frappe.workspaces[frappe.router.slug(old_item.name)]) {
			delete frappe.workspaces[frappe.router.slug(old_item.name)];
			if (new_item) {
				frappe.workspaces[frappe.router.slug(new_item.name)] = {'title': new_item.title};
			}
		}

		// update page block data
		if (this.pages && this.pages[old_item.name]) {
			if (new_item) {
				this.pages[new_item.name] = this.pages[old_item.name];
			}
			delete this.pages[old_item.name];
		}

		// update public and private pages
		if (new_item) {
			let is_section_changed = old_item.public != (new_item.is_public || new_item.public || 0);

			if (is_section_changed) {
				from_pages.splice(old_item_index, 1);
				to_pages.push(new_item);
			} else {
				from_pages.splice(old_item_index, 1, new_item);
			}
		} else {
			from_pages.splice(old_item_index, 1);
		}

		this.sidebar_pages.pages = [...this.public_pages, ...this.private_pages];
	}

	add_settings_button(item, sidebar_control) {
		this.dropdown_list = [
			{
				label: 'Edit',
				title: 'Edit Workspace',
				icon: frappe.utils.icon('edit', 'sm'),
				action: () => this.edit_page(item)
			},
			{
				label: 'Delete',
				title: 'Delete Workspace',
				icon: frappe.utils.icon('delete-active', 'sm'),
				action: () => this.delete_page(item)
			},
			{
				label: 'Duplicate',
				title: 'Duplicate Workspace',
				icon: frappe.utils.icon('duplicate', 'sm'),
				action: () => this.duplicate_page(item)
			},
			{
				label: 'Settings',
				title: 'Settings',
				icon: frappe.utils.icon('setting-gear', 'sm'),
				action: () => frappe.set_route(`workspace/${item.name}`)
			},
		]

		let $button = $(`
			<div class="btn btn-secondary btn-xs setting-btn dropdown-btn" title="${__('Setting')}">
				${frappe.utils.icon('dot-horizontal', 'xs')}
			</div>
			<div class="dropdown-list hidden"></div>
		`);

		let dropdown_item = function(label, title, icon, action) {
			let html = $(`
				<div class="dropdown-item" title="${title}">
					<span class="dropdown-item-icon">${icon}</span>
					<span class="dropdown-item-label">${label}</span>
				</div>
			`);

			html.click(event => {
				event.stopPropagation();
				action && action();
			});

			return html;
		}

		$button.filter('.dropdown-btn').click(event => {
			event.stopPropagation();
			if ($button.filter('.dropdown-list.hidden').length) {
				$('.dropdown-list:not(.hidden)').addClass('hidden');
			}
			$button.filter('.dropdown-list').toggleClass('hidden');
		});

		$(document).click(event => {
			event.stopPropagation();
			$('.dropdown-list:not(.hidden)').addClass('hidden');
		})

		sidebar_control.append($button);

		this.dropdown_list.forEach((i) => {
			$button.filter('.dropdown-list').append(dropdown_item(i.label, i.title, i.icon, i.action));
		})
	}

	delete_page(page) {
		frappe.confirm(__("Are you sure you want to delete page {0}?", [page.title]), () => {
			let me = this;
			this.sidebar
				.find(`.standard-sidebar-section [item-name="${page.title}"][item-public="${page.public}"]`)
				.addClass('hidden');

			frappe.call({
				method: "frappe.desk.doctype.workspace.workspace.delete_page",
				args: {
					page: page
				},
				callback: function(res) {
					res.message && me.update_cached_values(res.message);
				}
			});

			if (this.current_page.name == page.title && this.current_page.public == page.public) {
				frappe.set_route('/');
			}
		});
	}

	make_sidebar_sortable() {
		let me = this;
		$('.nested-container').each( function() {
			new Sortable(this, {
				handle: ".drag-handle",
				draggable: ".sidebar-item-container.is-draggable",
				group: 'nested',
				animation: 150,
				fallbackOnBody: true,
				swapThreshold: 0.65,
				onEnd: function (evt) {
					let is_public = $(evt.item).attr('item-public') == '1';
					me.prepare_sorted_sidebar(is_public);
				}
			});
		});
	}

	prepare_sorted_sidebar(is_public) {
		if (is_public) {
			this.sorted_public_items = this.sort_sidebar(this.sidebar.find('.standard-sidebar-section').last());
		} else {
			this.sorted_private_items = this.sort_sidebar(this.sidebar.find('.standard-sidebar-section').first());
		}
	}

	sort_sidebar($sidebar_section) {
		let sorted_items = [];
		for (let page of $sidebar_section.find('.sidebar-item-container')) {
			let parent_page = "";
			if (page.closest('.nested-container').classList.contains('sidebar-child-item')) {
				parent_page = page.parentElement.parentElement.attributes["item-name"].value;
			}
			sorted_items.push({
				title: page.attributes['item-name'].value,
				parent_page: parent_page,
				public: page.attributes['item-public'].value
			});
		}
		return sorted_items;
	}

	make_blocks_sortable() {
		let me = this;
		this.page_sortable = Sortable.create(this.page.main.find(".codex-editor__redactor").get(0), {
			handle: ".drag-handle",
			draggable: ".ce-block",
			animation: 150,
			onEnd: function (evt) {
				me.editor.blocks.move(evt.newIndex, evt.oldIndex);
			},
			setData: function () {
				//Do Nothing
			}
		});
	}

	initialize_new_page() {
		this.public_parent_pages = ['', ...this.public_pages.filter(page => !page.parent_page).map(page => page.title)];
		this.private_parent_pages = ['', ...this.private_pages.filter(page => !page.parent_page).map(page => page.title)];
		var me = this;
		const d = new frappe.ui.Dialog({
			title: __('New Workspace'),
			fields: [
				{
					label: __('Title'),
					fieldtype: 'Data',
					fieldname: 'title',
					reqd: 1
				},
				{
					label: __('Parent'),
					fieldtype: 'Select',
					fieldname: 'parent',
					options: this.private_parent_pages
				},
				{
					label: __('Public'),
					fieldtype: 'Check',
					fieldname: 'is_public',
					depends_on: `eval:${this.has_access}`,
					onchange: function() {
						d.set_df_property('parent', 'options',
							this.get_value() ? me.public_parent_pages : me.private_parent_pages);
					}
				},
				{
					fieldtype: 'Column Break'
				},
				{
					label: __('Icon'),
					fieldtype: 'Icon',
					fieldname: 'icon'
				},
			],
			primary_action_label: __('Create'),
			primary_action: (values) => {
				if (!this.validate_page(values)) return;
				d.hide();
				this.initialize_editorjs_undo();
				this.setup_customization_buttons({is_editable: true});
				this.title = values.title;
				this.icon = values.icon;
				this.parent = values.parent;
				this.public = values.is_public;
				this.editor.render({
					blocks: [{
						type: "header",
						data: { text: this.title }
					}]
				}).then(async () => {
					if (this.editor.configuration.readOnly) {
						this.is_read_only = false;
						await this.editor.readOnly.toggle();
					}
					this.add_page_to_sidebar(values);
					this.show_sidebar_actions();
					this.make_sidebar_sortable();
					this.make_blocks_sortable();
					this.prepare_sorted_sidebar(values.is_public);

					this.update_selected_sidebar(this.current_page, false); //remove selected from old page
				});
			}
		});
		d.show();
	}

	validate_page(new_page, old_page) {
		let message = "";
		let [from_pages, to_pages] = new_page.is_public ? 
			[this.private_pages, this.public_pages] : [this.public_pages, this.private_pages];

		let section = this.sidebar_categories[new_page.is_public];

		if (to_pages && to_pages.filter(p => p.title == new_page.title)[0]) {
			message = `Page with title ${new_page.title} already exist.`;
		} 
		
		if (frappe.router.doctype_route_exist(frappe.router.slug(new_page.title))) {
			message = "Doctype with same route already exist. Please choose different title.";
		}

		let child_pages = old_page && from_pages.filter(p => p.parent_page == old_page.title);
		if (child_pages) {
			child_pages.every(child_page => {
				if(to_pages && to_pages.find(p => p.title == child_page.title)) {
					message = `One of the child page with name <b>${child_page.title}</b> already exist in <b>${section}</b> Section. Please update the name of the child page first before moving`;
					cur_dialog.hide();
					return false;
				}
				return true;
			});
		}

		if (message) {
			frappe.throw(__(message));
			return false;
		}
		return true;
	}

	add_page_to_sidebar({title, icon, parent, is_public}) {
		let $sidebar = $('.standard-sidebar-section');
		let item = {
			title: title,
			icon: icon,
			parent_page: parent,
			public: is_public,
			selected: true
		};
		let $sidebar_item = this.sidebar_item_container(item);
		$sidebar_item.addClass('is-draggable');

		frappe.utils.add_custom_button(
			frappe.utils.icon('drag', 'xs'),
			null,
			"drag-handle",
			`${__('Drag')}`,
			null,
			$sidebar_item.find('.sidebar-item-control')
		);

		$sidebar_item.find('.sidebar-item-control .drag-handle').css('margin-right', '8px');

		let $sidebar_section = is_public ? $sidebar[1] : $sidebar[0];

		if (!parent) {
			!is_public && $sidebar.first().removeClass('hidden');
			$sidebar_item.appendTo($sidebar_section);
		} else {
			let $item_container = $($sidebar_section).find(`[item-name="${parent}"]`);
			let $child_section = $item_container.find('.sidebar-child-item');
			let $drop_icon = $item_container.find('.drop-icon');
			if (!$child_section[0]) {
				$child_section = $(`<div class="sidebar-child-item hidden nested-container"></div>`)
					.appendTo($item_container);
				$drop_icon.toggleClass('hidden');
			}
			$sidebar_item.appendTo($child_section);
			$child_section.removeClass('hidden');
			$item_container.find('.drop-icon use').attr("href", "#icon-small-up");
		}
	}

	initialize_editorjs(blocks) {
		this.tools = {
			header: {
				class: this.blocks['header'],
				inlineToolbar: ['HeaderSize', 'bold', 'italic', 'link'],
				config: {
					default_size: 4
				}
			},
			paragraph: {
				class: this.blocks['paragraph'],
				inlineToolbar: ['HeaderSize', 'bold', 'italic', 'link'],
				config: {
					placeholder: 'Choose a block or continue typing'
				}
			},
			chart: {
				class: this.blocks['chart'],
				config: {
					page_data: this.page_data || []
				}
			},
			card: {
				class: this.blocks['card'],
				config: {
					page_data: this.page_data || []
				}
			},
			shortcut: {
				class: this.blocks['shortcut'],
				config: {
					page_data: this.page_data || []
				}
			},
			onboarding: {
				class: this.blocks['onboarding'],
				config: {
					page_data: this.page_data || []
				}
			},
			spacer: this.blocks['spacer'],
			HeaderSize: frappe.wspace_block.tunes['header_size'],
		};
		this.editor = new EditorJS({
			data: {
				blocks: blocks || []
			},
			tools: this.tools,
			autofocus: false,
			readOnly: true,
			logLevel: 'ERROR'
		});
	}

	save_page() {
		frappe.dom.freeze();
		this.create_page_skeleton();
		let me = this;
		let save = true;

		if (!this.title && this.current_page) {
			this.title = this.current_page.name;
			this.public = this.current_page.public;
			save = false;
		} else {
			this.current_page = { name: this.title, public: this.public };
		}

		this.editor.save().then((outputData) => {
			let new_widgets = {};

			outputData.blocks.forEach(item => {
				if (item.data.new) {
					if (!new_widgets[item.type]) {
						new_widgets[item.type] = [];
					}
					new_widgets[item.type].push(item.data.new);
					delete item.data['new'];
				}
			});

			let blocks = outputData.blocks.filter(
				item => item.type != 'card' ||
					(item.data.card_name !== 'Custom Documents' &&
					item.data.card_name !== 'Custom Reports')
			);

			frappe.call({
				method: "frappe.desk.doctype.workspace.workspace.save_page",
				args: {
					title: me.title,
					icon: me.icon || '',
					parent: me.parent || '',
					public: me.public || 0,
					sb_public_items: me.sorted_public_items,
					sb_private_items: me.sorted_private_items,
					new_widgets: new_widgets,
					blocks: JSON.stringify(blocks),
					save: save
				},
				callback: function(res) {
					frappe.dom.unfreeze();
					if (res.message) {
						me.new_page = res.message;
						me.pages[res.message.label] && delete me.pages[res.message.label];
						me.reload();
						frappe.show_alert({ message: __("Page Saved Successfully"), indicator: "green" });
					}
				}
			});
		}).catch((error) => {
			error;
			// console.log('Saving failed: ', error);
		});
	}

	reload() {
		this.title = '';
		this.icon = '';
		this.parent = '';
		this.public = false;
		this.sorted_public_items = [];
		this.sorted_private_items = [];
		this.setup_pages(true);
		this.discard = false;
		this.undo.readOnly = true;
	}

	create_page_skeleton() {
		if ($('.layout-main-section').find('.workspace-skeleton').length) return;

		$('.layout-main-section').prepend(frappe.render_template('workspace_loading_skeleton'));
		$('.layout-main-section').find('.codex-editor').addClass('hidden');
	}

	remove_page_skeleton() {
		$('.layout-main-section').find('.codex-editor').removeClass('hidden');
		$('.layout-main-section').find('.workspace-skeleton').remove();
	}

	create_sidebar_skeleton() {
		if ($('.list-sidebar').find('.workspace-sidebar-skeleton').length) return;

		$('.list-sidebar').prepend(frappe.render_template('workspace_sidebar_loading_skeleton'));
		$('.desk-sidebar').addClass('hidden');
	}

	remove_sidebar_skeleton() {
		$('.desk-sidebar').removeClass('hidden');
		$('.list-sidebar').find('.workspace-sidebar-skeleton').remove();
	}
};
