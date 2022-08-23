import Widget from "./base_widget.js";
import Embed from './../views/workspace/blocks/embed.js';
import { debounce } from 'debounce';
//npm install debounce was run
frappe.provide("frappe.utils");

export default class EmbedWidget extends Widget {
	constructor(opts) {
		opts.shadow = true;
		super(opts);
		//this.height = this.i_height || 240;
	}

	get_config() {
		return {
			document_type: this.document_type,
			label: this.label,
			service: this.service,
			source: this.source,
			embed: this.embed,
			i_width: this.i_width,
			i_height: this.i_height
			//embed_filter: this.embed_filter
		};
	}

	//these are the buttons on top of the widget.
	set_actions() {
		if (this.in_customize_mode) return;
		//this.setup_add_new_button();
		this.setup_refresh_list_button();
	}

	setup_add_new_button() {
		this.add_new_button = $(
			`<div class="add-new btn btn-xs pull-right" title="${__("Add New " + this.document_type)}">
				${frappe.utils.icon('add', 'sm')}
			</div>`
		);

		this.add_new_button.appendTo(this.action_area);
		this.add_new_button.on("click", () => {
			frappe.set_route(
				frappe.utils.generate_route({ type: 'doctype', name: this.document_type, doc_view: 'New' })
			);
		});
	}

	setup_refresh_list_button() {
		this.refresh_list = $(
			`<div class="refresh-list btn btn-xs pull-right" title="${__("Refresh List")}">
				${frappe.utils.icon('refresh', 'sm')}
			</div>`
		);

		this.refresh_list.appendTo(this.action_area);
		this.refresh_list.on("click", () => {
			this.body.empty();
			this.set_body();
		});
	}


	render_loading_state() {
		this.body.empty();
		this.loading = $(
			`<div class="list-loading-state text-muted">${__(
				"Loading..."
			)}</div>`
		);
		this.loading.appendTo(this.body);
	}

	render_no_data_state() {
		this.loading = $(
			`<div class="list-no-data-state text-muted">${__(
				"No Data..."
			)}</div>`
		);
		this.loading.appendTo(this.body);
	}

	/**
   * Checks that mutations in DOM have finished after appending iframe content
   *
   * @param {HTMLElement} targetNode - HTML-element mutations of which to listen
   * @returns {Promise<any>} - result that all mutations have finished
   */


	embedIsReady(targetNode) {
		const PRELOADER_DELAY = 450;

		let observer = null;

		return new Promise((resolve, reject) => {
			observer = new MutationObserver(debounce(resolve, PRELOADER_DELAY));
			observer.observe(targetNode, {
				childList: true,
				subtree: true,
			});
		}).then(() => {
			observer.disconnect();
		});
	}

	set_body() {
		this.widget.addClass("quick-list-widget-box");

		let meta = frappe.get_meta(this.document_type);
		//	this.render_loading_state();
		if (!this.service) {
			this.loading = $(
				`<div class="chart-loading-state text-muted" style="height: ${this.height}px;">${__(
					"No service selected..."
				)}</div>`
			);
			this.body.empty();
			this.loading.appendTo(this.body);
		} else if (!this.source) {
			this.loading = $(
				`<div class="chart-loading-state text-muted" style="height: ${this.height}px;">${__(
					"No source address entered"
				)}</div>`
			);
			this.body.empty();
			this.loading.appendTo(this.body);
		} else {
			this.loading = $(
				`<div class="chart-loading-state text-muted" style="height: ${this.height}px;">${__(
					"Loading..."
				)}</div>`
			);
			this.loading.appendTo(this.body);
			

			try {
				const { regex, embedUrl, width, height, id = (ids) => ids.shift() } = Embed.services[this.service];
				const result = regex.exec(this.source).slice(1);
				this.embed = embedUrl.replace(/<%= remote_id %>/g, id(result));
				// this.caption = "some caption bro";
				this._data = {
					service: this.service,
					source: this.source,
					embed: this.embed,
					width: this.i_width,
					i_height: this.i_height,
					caption: this.caption || '',
				};

				if (!this.service) {
					const container = document.createElement('div');
					//this.wrapper = container;
					return container;
				}
				let b = Embed.services[this.service];
				const { html } = Embed.services[this.service];
				const container = document.createElement('div');
				//this.new('embed'); //make this happen later by merging some of this stuff over there
				const caption = document.createElement('div');
				const template = document.createElement('template');
				// const preloader = this.createPreloader();

				//  container.classList.add(this.CSS.baseClass, this.CSS.container, this.CSS.containerLoading);
				//  caption.classList.add(this.CSS.input, this.CSS.caption);

				// container.appendChild(preloader);
				caption.contentEditable = false;
				// caption.dataset.placeholder = this.api.i18n.t('Enter a caption');
				caption.innerHTML = this.caption || '';

				template.innerHTML = html;
				template.content.firstChild.setAttribute('src', this.embed);
				template.content.firstChild.setAttribute('height', this.i_height);
				template.content.firstChild.setAttribute('width', this.i_width);
				//  template.content.firstChild.classList.add(this.CSS.content);
				const embedIsReady = this.embedIsReady(container);
				container.appendChild(template.content.firstChild);
				container.appendChild(caption);
				embedIsReady
					.then(() => {
						//  window.alert('yo yo Im ready');
						this.body.remove(".chart-loading-state");
					});

				this.body.empty();
				this.wrapper = $(`<div>` + container.innerHTML + `</div>`);;
				this.wrapper.appendTo(this.body);
		} catch (error) {
			this.body.empty();
			debugger;
			//not sure if this is best practice but will at least inform the user something went wrong.
			frappe.msgprint(error + " - Check embed source field is correct");
		  }
		}
	}

}
