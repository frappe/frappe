//Code adapted from https://github.com/editor-js/embed (MIT)
import Block from "./block.js";
import SERVICES from './embed_services.js';

/**
 * @class Embed
 * @classdesc Embed Tool for Editor.js 2.0
 *
 * @property {object} api - Editor.js API
 * @property {EmbedData} _data - private property with Embed data
 * @property {HTMLElement} element - embedded content container
 *
 * @property {object} services - static property with available services
 * @property {object} patterns - static property with patterns for paste handling configuration
 */
export default class Embed extends Block {
  /**
   * @param {{data: EmbedData, config: EmbedConfig, api: object}}
   *   data — previously saved data
   *   config - user config for Tool
   *   api - Editor.js API
   *   readOnly - read-only mode flag
   */
  
  static get toolbox() {
    return {
        title: 'Embed',
        icon: frappe.utils.icon('list', 'sm')
    };
  }


  constructor({ data, api, config, readOnly, block }) {
    super({ data, api, config, readOnly, block });
    this.api = api;
    this._data = {};
    this.element = null;
    this.readOnly = readOnly;
    this.data = data;
    this.col = this.data.col ? this.data.col : "4";
    this.allow_customization = !this.readOnly;
    this.sevices = SERVICES;
    this.options = {
        allow_sorting: this.allow_customization,
        allow_create: this.allow_customization,
        allow_delete: this.allow_customization,
        allow_hiding: false,
        allow_edit: true,
        allow_resize: true,
        min_width: 4,
        max_widget_count: 2
    };
  }

  /**
   * Render Embed tool content
   *
   * @returns {HTMLElement}
   */
   render() {
		this.wrapper = document.createElement('div');
		this.new('embed');
		if (this.data && this.data.embed_name) {
			let has_data = this.make('embed', this.data.embed_name);
			if (!has_data) return;
		}

		if (!this.readOnly) {
			$(this.wrapper).find('.widget').addClass('embed edit-mode');
			this.add_settings_button();
			this.add_new_block_button();
		}

		return this.wrapper;
	}



  /**
   * Save current content and return EmbedData object
   *
   * @returns {EmbedData}
   */
  save() {
		return {
			embed_name: this.wrapper.getAttribute('embed_name'),
			col: this.get_col(),
			new: this.new_block_widget
		};
  }

	validate(savedData) {
		if (!savedData.embed_name) {
			return false;
		}

		return true;
	}


  /**
   * Analyze provided config and make object with services to use
   *
   * @param {EmbedConfig} config - configuration of embed block element
   */
  static prepare({ config = {} }) {
    const { services = {} } = config;

    let entries = Object.entries(SERVICES);

    const enabledServices = Object
      .entries(services)
      .filter(([key, value]) => {
        return typeof value === 'boolean' && value === true;
      })
      .map(([ key ]) => key);

    const userServices = Object
      .entries(services)
      .filter(([key, value]) => {
        return typeof value === 'object';
      })
      .filter(([key, service]) => Embed.checkServiceConfig(service))
      .map(([key, service]) => {
        const { regex, embedUrl, html, height, width, id } = service;

        return [key, {
          regex,
          embedUrl,
          html,
          height,
          width,
          id,
        } ];
      });

    if (enabledServices.length) {
      entries = entries.filter(([ key ]) => enabledServices.includes(key));
    }

    entries = entries.concat(userServices);

    Embed.services = entries.reduce((result, [key, service]) => {
      if (!(key in result)) {
        result[key] = service;

        return result;
      }

      result[key] = Object.assign({}, result[key], service);

      return result;
    }, {});

    Embed.patterns = entries
      .reduce((result, [key, item]) => {
        result[key] = item.regex;

        return result;
      }, {});
  }

  /**
   * Check if Service config is valid
   *
   * @param {Service} config - configuration of embed block element
   * @returns {boolean}
   */
  static checkServiceConfig(config) {
    const { regex, embedUrl, html, height, width, id } = config;

    let isValid = regex && regex instanceof RegExp &&
      embedUrl && typeof embedUrl === 'string' &&
      html && typeof html === 'string';

    isValid = isValid && (id !== undefined ? id instanceof Function : true);
    isValid = isValid && (height !== undefined ? Number.isFinite(height) : true);
    isValid = isValid && (width !== undefined ? Number.isFinite(width) : true);

    return isValid;
  }


  /**
   * Notify core that read-only mode is supported
   *
   * @returns {boolean}
   */
  static get isReadOnlySupported() {
    return true;
  }


}
