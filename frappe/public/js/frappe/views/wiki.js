import EditorJS from '@editorjs/editorjs';
import Undo from 'editorjs-undo';

frappe.views.Wiki = class Wiki {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = wrapper.page;
		this.pages = {};
		this.sections = {};
		this.sidebar_items = {};
		this.sorted_sidebar_items = [];
		this.deleted_sidebar_items = [];
		this.isReadOnly = true;
		this.new_page = null;
		this.prepare_container();
		this.setup_wiki_pages();
		this.tools = {
			header: {
				class: frappe.wiki_block.blocks['header'],
				inlineToolbar: true
			},
			paragraph: {
				class: frappe.wiki_block.blocks['paragraph'],
				inlineToolbar: true
			},
			chart: {
				class: frappe.wiki_block.blocks['chart'],
				config: {
					page_data: this.page_data || []
				}
			},
			card: {
				class: frappe.wiki_block.blocks['card'],
				config: {
					page_data: this.page_data || []
				}
			},
			shortcut: {
				class: frappe.wiki_block.blocks['shortcut'],
				config: {
					page_data: this.page_data || []
				}
			},
			spacer: frappe.wiki_block.blocks['spacer'],
			spacingTune: frappe.wiki_block.tunes['spacing_tune'],
		};
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

	setup_wiki_pages() {
		this.get_pages().then(() => {
			if (this.all_pages) {
				frappe.wiki_pages = {};
				let root_pages = this.all_pages.filter(page => page.parent_page == '' || page.parent_page == null);
				for (let page of this.all_pages) {
					frappe.wiki_pages[frappe.router.slug(page.name)] = page;
				}
				if (this.new_page) {
					frappe.set_route(`wiki/${frappe.router.slug(this.new_page)}`);
					this.new_page = null;
				}
				this.make_sidebar(root_pages);
				frappe.router.route();
			}
		});
	}

	get_pages() {
		return frappe.xcall("frappe.desk.doctype.internal_wiki_page.internal_wiki_page.get_pages").then(data => {
			this.all_pages = data;
		});
	}

	make_sidebar(items) {
		if (this.sidebar.find('.standard-sidebar-section')[0]) {
			this.sidebar.find('.standard-sidebar-section')[0].remove();
		}
		let sidebar_section = $(`<div class="standard-sidebar-section nested-container"></div>`);
		this.prepare_sidebar(items, sidebar_section, this.sidebar);
	}

	prepare_sidebar(items, child_container, item_container) {
		items.forEach(item => this.append_item(item, child_container));
		child_container.appendTo(item_container);
	}

	append_item(item, container) {
		let is_current_page = frappe.router.slug(item.name) == frappe.router.slug(this.get_page_to_show());
		if (is_current_page) {
			item.selected = true;
			this.current_page_name = item.name;
		}

		let $item_container = this.sidebar_item_container(item);
		let sidebar_control = $item_container.find('.sidebar-item-control');

		this.add_sidebar_actions(item, sidebar_control);

		let child_items = this.all_pages.filter(page => page.parent_page == item.name);
		if (child_items.length > 0) {
			let child_container = $(`<div class="sidebar-child-item hidden nested-container"></div>`);
			this.prepare_sidebar(child_items, child_container, $item_container);
		}

		$item_container.appendTo(container);
		this.sidebar_items[item.name] = $item_container;

		if ($item_container.parent().hasClass('hidden') && is_current_page) {
			$item_container.parent().toggleClass('hidden');
		}

		let $drop_icon = $(`<span class="drop-icon hidden">${frappe.utils.icon("small-down", "sm")}</span>`);
		$drop_icon.appendTo(sidebar_control);
		let drop_icon = $item_container.find('.drop-icon').get(0);
		let child_item_section = $item_container.find('.sidebar-child-item').get(0);
		if (this.all_pages.some(e => e.parent_page == item.name)) {
			drop_icon.classList.remove('hidden');
			drop_icon.addEventListener('click', () => {
				child_item_section.classList.toggle("hidden");
				let icon = $(drop_icon).find("use").attr("href")==="#icon-small-down" ? "#icon-small-up" : "#icon-small-down";
				$(drop_icon).find("use").attr("href", icon);
			});
		}
	}

	sidebar_item_container(item) {
		return $(`
			<div class="sidebar-item-container" item-parent="${item.parent_page}" item-name="${item.name}">
				<div class="desk-sidebar-item standard-sidebar-item ${item.selected ? "selected" : ""}">
					<a
						href="/app/wiki/${frappe.router.slug(item.name)}"
						class="item-anchor" title="${item.name}"
					>
						<span>${frappe.utils.icon(item.icon || "folder-normal", "md")}</span>
						<span class="sidebar-item-label">${item.label || item.name}<span>
					</a>
					<div class="sidebar-item-control"></div>
				</div>
			</div>
		`);
	}

	show() {
		if (!this.all_pages) {
			// pages not yet loaded, call again after a bit
			setTimeout(() => {
				this.show();
			}, 500);
			return;
		}
		let page = this.get_page_to_show();
		this.page.set_title(`${__(page)}`);
		this.show_page(page);
		this.get_content(page).then(() => {
			this.get_data(page).then(() => {
				if (this.content) {
					if (this.editor) {
						this.editor.isReady.then(() => {
							this.editor.configuration.tools.chart.config.page_data = this.page_data;
							this.editor.configuration.tools.shortcut.config.page_data = this.page_data;
							this.editor.configuration.tools.card.config.page_data = this.page_data;
							this.editor.render({
								blocks: JSON.parse(this.content) || []
							});
						});
					} else {
						this.initialize_editorjs(JSON.parse(this.content));
					}
				}
			});
		});
	}

	get_content(page) {
		return frappe.xcall("frappe.desk.doctype.internal_wiki_page.internal_wiki_page.get_page_content", {
			page: page
		}).then(data => {
			this.content = data;
		});
	}

	get_data(page) {
		return frappe.xcall("frappe.desk.desktop.get_desktop_page", {
			page: page
		}).then(data => {
			this.page_data = data;
			if (!this.page_data) return;

			return frappe.dashboard_utils.get_dashboard_settings().then(settings => {
				let chart_config = settings.chart_config ? JSON.parse(settings.chart_config) : {};
				if (this.page_data.charts.items) {
					this.page_data.charts.items.map(chart => {
						chart.chart_settings = chart_config[chart.chart_name] || {};
					});
				}
			});
		});
	}

	get_page_to_show() {
		let default_page;

		if (localStorage.current_wiki_page) {
			default_page = localStorage.current_wiki_page;
		} else if (this.all_pages) {
			default_page = this.all_pages[0].name;
		} else {
			default_page = "Build";
		}

		let page = frappe.get_route()[1] || default_page;
		return page;
	}

	show_page(page) {
		if (this.current_page_name && this.pages[this.current_page_name]) {
			this.pages[this.current_page_name].hide();
		}

		if (this.sidebar_items && this.sidebar_items[this.current_page_name]) {
			this.sidebar_items[this.current_page_name][0].firstElementChild.classList.remove("selected");
			this.sidebar_items[page][0].firstElementChild.classList.add("selected");
		}
		this.current_page_name = page;
		localStorage.current_wiki_page = page;

		this.current_page = this.pages[page];

		if (!this.body.find('#editorjs')[0]) {
			this.$page = $(`
				<div id="editorjs" class="wiki-page page-main-content"></div>
			`).appendTo(this.body);
		}

		this.setup_actions();
	}

	setup_actions() {
		if (!this.isReadOnly) return;
		this.page.clear_inner_toolbar();
		this.page.set_secondary_action(
			__("Customize"),
			() => {
				this.isReadOnly = false;
				this.editor.readOnly.toggle();
				this.editor.isReady
					.then(() => {
						this.initialize_editorjs_undo();
						this.setup_customization_buttons();
						this.show_sidebar_actions();
						this.make_sidebar_sortable();
						this.make_blocks_sortable();
					});
			},
		);

		this.page.add_inner_button(__('Create Page'), () => {
			this.initialize_new_page();
		});
	}

	initialize_editorjs_undo() {
		this.undo = new Undo({ editor: this.editor });
		this.undo.initialize({blocks: JSON.parse(this.content)});
		this.undo.readOnly = false;
	}

	show_sidebar_actions() {
		this.sidebar.find('.standard-sidebar-section').addClass('show-control');
	}

	add_sidebar_actions(item, sidebar_control) {
		this.add_custom_button(
			frappe.utils.icon('drag', 'xs'),
			null,
			"drag-handle",
			`${__('Drag')}`,
			null,
			sidebar_control
		);
		this.add_custom_button(
			frappe.utils.icon('delete', 'xs'),
			() => this.delete_page(item.name),
			"delete-page",
			`${__('Delete')}`,
			null,
			sidebar_control
		);
	}

	add_custom_button(html, action, class_name = "", title="", btn_type, wrapper) {
		if (!btn_type) btn_type = 'btn-secondary';
		let button = $(
			`<button class="btn ${btn_type} btn-xs ${class_name}" title="${title}">${html}</button>`
		);
		button.click(event => {
			event.stopPropagation();
			action && action();
		});
		button.appendTo(wrapper);
	}

	delete_page(name) {
		if (!this.deleted_sidebar_items.includes(name)) {
			this.deleted_sidebar_items.push(name);
		}
		frappe.confirm(__("Are you sure you want to delete page {0}?", [name]), () => {
			this.sidebar.find(`.standard-sidebar-section [item-name="${name}"]`).addClass('hidden');
		});
	}

	make_sidebar_sortable() {
		let me = this;
		$('.nested-container').each( function() {
			new Sortable(this, {
				handle: ".drag-handle",
				draggable: ".sidebar-item-container",
				group: 'nested',
				animation: 150,
				fallbackOnBody: true,
				swapThreshold: 0.65,
				onEnd: function () {
					me.sorted_sidebar_items = [];
					for (let page of $('.standard-sidebar-section').find('.sidebar-item-container')) {
						let parent_page = "";
						if (page.closest('.nested-container').classList.contains('sidebar-child-item')) {
							parent_page = page.parentElement.parentElement.attributes["item-name"].value;
						}
						me.sorted_sidebar_items.push({
							name: page.attributes['item-name'].value,
							parent_page: parent_page
						});
					}
				}
			});
		});
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

	setup_customization_buttons() {
		this.page.clear_primary_action();
		this.page.clear_secondary_action();
		this.page.clear_inner_toolbar();

		this.page.set_primary_action(
			__("Save Customizations"),
			() => {
				this.page.clear_primary_action();
				this.page.clear_secondary_action();
				this.undo.readOnly = true;
				this.save_page();
				this.editor.readOnly.toggle();
				this.isReadOnly = true;
			},
			null,
			__("Saving")
		);

		this.page.set_secondary_action(
			__("Discard"),
			() => {
				this.page.clear_primary_action();
				this.page.clear_secondary_action();
				this.editor.readOnly.toggle();
				this.isReadOnly = true;
				this.deleted_sidebar_items = [];
				this.reload();
				frappe.show_alert({ message: __("Customizations Discarded"), indicator: "info" });
			}
		);
	}

	initialize_new_page() {
		const d = new frappe.ui.Dialog({
			title: __('Set Title'),
			fields: [
				{
					label: __('Title'),
					fieldtype: 'Data',
					fieldname: 'title'
				},
				{
					label: __('Parent'),
					fieldtype: 'Select',
					fieldname: 'parent',
					options: this.all_pages.filter(page => !page.parent_page).map(page => page.name)
				}
			],
			primary_action_label: __('Create'),
			primary_action: (values) => {
				d.hide();
				this.initialize_editorjs_undo();
				this.setup_customization_buttons();
				this.title = values.title;
				this.parent = values.parent;
				this.editor.render({
					blocks: [
						{
							type: "header",
							data: {
								text: this.title,
								level: 2
							}
						}
					]
				}).then(() => {
					if (this.editor.configuration.readOnly) {
						this.isReadOnly = false;
						this.editor.readOnly.toggle();
					}
					this.add_page_to_sidebar(values);
					this.show_sidebar_actions();
					this.make_sidebar_sortable();
					this.make_blocks_sortable();
				});
			}
		});
		d.show();
	}

	add_page_to_sidebar({title, parent}) {
		let $sidebar = $('.standard-sidebar-section');
		let item = {
			name: title,
			parent_page: parent,
		};
		let $sidebar_item = this.sidebar_item_container(item);

		this.add_custom_button(
			frappe.utils.icon('drag', 'xs'),
			null,
			"drag-handle",
			`${__('Drag')}`,
			null,
			$sidebar_item.find('.sidebar-item-control')
		);

		if (!parent) {
			$sidebar_item.appendTo($sidebar);
		} else {
			let $child_section = $sidebar.find(`[item-name="${parent}"] .sidebar-child-item`);
			$sidebar_item.appendTo($child_section);
			$child_section.removeClass('hidden');
		}
	}

	initialize_editorjs(blocks) {
		const data = {
			blocks: blocks || []
		};
		this.editor = new EditorJS({
			tools: this.tools,
			autofocus: false,
			data,
			tunes: ['spacingTune'],
			readOnly: true,
			logLevel: 'ERROR'
		});
	}

	save_page() {
		frappe.dom.freeze();
		let save = true;
		if (!this.title && this.current_page_name) {
			this.title = this.current_page_name;
			save = '';
		} else {
			this.current_page_name = this.title;
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

			frappe.call({
				method: "frappe.desk.doctype.internal_wiki_page.internal_wiki_page.save_wiki_page",
				args: {
					title: me.title,
					parent: me.parent || '',
					sb_items: me.sorted_sidebar_items,
					deleted_pages: me.deleted_sidebar_items,
					new_widgets: new_widgets,
					blocks: JSON.stringify(outputData.blocks),
					save: save
				},
				callback: function(res) {
					frappe.dom.unfreeze();
					if (res.message) {
						frappe.show_alert({ message: __("Page Saved Successfully"), indicator: "green" });
						me.title = '';
						me.parent = '';
						me.sorted_sidebar_items = [];
						me.deleted_sidebar_items = [];
						me.new_page = res.message;
						me.reload();
					}
				}
			});
		}).catch((error) => {
			error;
			// console.log('Saving failed: ', error);
		});
	}

	reload() {
		this.setup_wiki_pages();
		this.undo.readOnly = true;
	}
};
