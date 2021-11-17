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
		this.deleted_sidebar_items = [];
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
					this.new_page = { name: this.all_pages[0].title, public: this.all_pages[0].public };
				}
				if (this.new_page.public) {
					frappe.set_route(`${frappe.router.slug(this.new_page.name)}`);
				} else {
					frappe.set_route(`private/${frappe.router.slug(this.new_page.name)}`);
				}
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
		!frappe.dom.is_element_in_viewport(this.sidebar.find('.selected'))
			&& this.sidebar.find('.selected')[0].scrollIntoView();
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
			let child_container = $(`<div class="sidebar-child-item hidden nested-container"></div>`);
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
		let $child_item_section = item_container.find('.sidebar-child-item');
		let $drop_icon = $(`<span class="drop-icon hidden">${frappe.utils.icon("small-down", "sm")}</span>`)
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

		this.show_page(page);
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
		let section = this.current_page.public ? 'public' : 'private';
		if (this.sidebar_items && this.sidebar_items[section] && this.sidebar_items[section][this.current_page.name]) {
			this.sidebar_items[section][this.current_page.name][0].firstElementChild.classList.remove("selected");
			this.sidebar_items[page.public ? 'public':'private'][page.name][0].firstElementChild.classList.add("selected");

			if (this.sidebar_items[page.public ? 'public':'private'][page.name].parents('.sidebar-item-container')[0]) {
				this.sidebar_items[page.public ? 'public':'private'][page.name]
					.parents('.sidebar-item-container')
					.find('.drop-icon use')
					.attr("href", "#icon-small-up");
			}
		}

		this.current_page = { name: page.name, public: page.public };
		localStorage.current_page = page.name;
		localStorage.is_current_page_public = page.public;

		if (!this.body.find('#editorjs')[0]) {
			this.$page = $(`
				<div id="editorjs" class="desk-page page-main-content"></div>
			`).appendTo(this.body);
		}
		this.create_skeleton();

		if (this.all_pages) {
			let pages = page.public ? this.public_pages : this.private_pages;
			let this_page = pages.filter(p => p.title == page.name)[0];
			this.setup_actions(page);
			this.content = this_page && JSON.parse(this_page.content);

			this.add_custom_cards_in_content();

			$('.item-anchor').addClass('disable-click');

			if (this.pages && this.pages[this_page.name]) {
				this.page_data = this.pages[this_page.name];
			} else {
				await this.get_data(this_page);
			}

			this.prepare_editorjs();
			$('.item-anchor').removeClass('disable-click');
			this.remove_skeleton();
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

		this.page.clear_primary_action();
		this.page.clear_secondary_action();
		this.page.clear_inner_toolbar();

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

	setup_customization_buttons(page) {
		let me = this;
		this.page.clear_primary_action();
		this.page.clear_secondary_action();
		this.page.clear_inner_toolbar();

		page.is_editable && this.page.set_primary_action(
			__("Save Customizations"),
			() => {
				this.page.clear_primary_action();
				this.page.clear_secondary_action();
				this.page.clear_inner_toolbar();
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
				this.page.clear_primary_action();
				this.page.clear_secondary_action();
				this.page.clear_inner_toolbar();
				await this.editor.readOnly.toggle();
				this.is_read_only = true;
				this.reload();
				frappe.show_alert({ message: __("Customizations Discarded"), indicator: "info" });
			}
		);

		page.name && this.page.add_inner_button(__("Settings"), () => {
			frappe.set_route(`workspace/${page.name}`);
		});

		Object.keys(this.blocks).forEach(key => {
			this.page.add_inner_button(`
				<span class="block-menu-item-icon">${this.blocks[key].toolbox.icon}</span>
				<span class="block-menu-item-label">${__(this.blocks[key].toolbox.title)}</span>
			`, function() {
				const index = me.editor.blocks.getBlocksCount() + 1;
				me.editor.blocks.insert(key, {}, {}, index, true);
				me.editor.caret.setToLastBlock('start', 0);
				$('.ce-block:last-child')[0].scrollIntoView();
			}, __('Add Block'));
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
			frappe.utils.add_custom_button(
				frappe.utils.icon('delete', 'xs'),
				() => this.delete_page(item),
				"delete-page",
				`${__('Delete')}`,
				null,
				sidebar_control
			);
		}
	}

	delete_page(item) {
		frappe.confirm(__("Are you sure you want to delete page {0}?", [item.title]), () => {
			this.deleted_sidebar_items.push(item);
			this.sidebar.find(`.standard-sidebar-section [item-name="${item.title}"][item-public="${item.public}"]`).addClass('hidden');
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
			title: __('Set Title'),
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
					blocks: [
						{
							type: "header",
							data: {
								text: this.title,
								level: 4
							}
						}
					]
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
				});
			}
		});
		d.show();
	}

	validate_page(values) {
		let message = "";
		let pages = values.is_public ? this.public_pages : this.private_pages;

		if (pages && pages.filter(p => p.title == values.title)[0]) {
			message = "Page with title '{0}' already exist.";
		} else if (frappe.router.doctype_route_exist(frappe.router.slug(values.title))) {
			message = "Doctype with same route already exist. Please choose different title.";
		}

		if (message) {
			frappe.throw(__(message, [__(values.title)]));
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
			public: is_public
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
				inlineToolbar: true,
				config: {
					defaultLevel: 4
				}
			},
			paragraph: {
				class: this.blocks['paragraph'],
				inlineToolbar: true
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
			spacingTune: frappe.wspace_block.tunes['spacing_tune'],
		};
		this.editor = new EditorJS({
			data: {
				blocks: blocks || []
			},
			tools: this.tools,
			autofocus: false,
			tunes: ['spacingTune'],
			readOnly: true,
			logLevel: 'ERROR'
		});
	}

	save_page() {
		frappe.dom.freeze();
		this.create_skeleton();
		let save = true;
		if (!this.title && this.current_page) {
			let pages = this.current_page.public ? this.public_pages : this.private_pages;
			this.title = this.current_page.name;
			this.public = pages.filter(p => p.title == this.title)[0].public;
			save = false;
		} else {
			this.current_page = { name: this.title, public: this.public };
		}
		let me = this;
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
					deleted_pages: me.deleted_sidebar_items,
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
		this.deleted_sidebar_items = [];
		this.create_skeleton();
		this.setup_pages(true);
		this.discard = false;
		this.undo.readOnly = true;
	}

	create_skeleton() {
		this.$page.prepend(frappe.render_template('workspace_loading_skeleton'));
		this.$page.find('.codex-editor').addClass('hidden');
	}

	remove_skeleton() {
		this.$page.find('.codex-editor').removeClass('hidden');
		this.$page.find('.workspace-skeleton').remove();
	}
};
