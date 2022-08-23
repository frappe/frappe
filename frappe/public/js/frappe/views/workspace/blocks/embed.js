import Block from "./block.js";
import SERVICES from './embed_services.js';

import { debounce } from 'debounce';
//npm install debounce was run


/**
 * @typedef {object} EmbedData
 * @description Embed Tool data
 * @property {string} service - service name
 * @property {string} url - source URL of embedded content
 * @property {string} embed - URL to source embed page
 * @property {number} [width] - embedded content width
 * @property {number} [height] - embedded content height
 * @property {string} [caption] - content caption
 */
/**
 * @typedef {object} PasteEvent
 * @typedef {object} HTMLElement
 * @typedef {object} Service
 * @description Service configuration object
 * @property {RegExp} regex - pattern of source URLs
 * @property {string} embedUrl - URL scheme to embedded page. Use '<%= remote_id %>' to define a place to insert resource id
 * @property {string} html - iframe which contains embedded content
 * @property {Function} [id] - function to get resource id from RegExp groups
 */
/**
 * @typedef {object} EmbedConfig
 * @description Embed tool configuration object
 * @property {object} [services] - additional services provided by user. Each property should contain Service object
 */

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

  static get isReadOnlySupported() {
      return true;
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
   * @param {EmbedData} data - embed data
   * @param {RegExp} [data.regex] - pattern of source URLs
   * @param {string} [data.embedUrl] - URL scheme to embedded page. Use '<%= remote_id %>' to define a place to insert resource id
   * @param {string} [data.html] - iframe which contains embedded content
   * @param {number} [data.height] - iframe height
   * @param {number} [data.width] - iframe width
   * @param {string} [data.caption] - caption
   */

  //these data set/get conflict with embed code. I guess this data should be stored in
  // set data(data) {
  //   if (!(data instanceof Object)) {
  //     throw Error('Embed Tool data should be object');
  //   }

  //   const { service, source, embed, width, height, caption = '' } = data;

  //   this._data = {
  //     service: service || this.data.service,
  //     source: source || this.data.source,
  //     embed: embed || this.data.embed,
  //     width: width || this.data.width,
  //     height: height || this.data.height,
  //     caption: caption || this.data.caption || '',
  //   };

  //   const oldView = this.element;

  //   if (oldView) {
  //     oldView.parentNode.replaceChild(this.render(), oldView);
  //   }
  // }

  // /**
  //  * @returns {EmbedData}
  //  */
  // get data() {
  //   if (this.element) {
  //     const caption = this.element.querySelector(`.${this.api.styles.input}`);

  //     this._data.caption = caption ? caption.innerHTML : '';
  //   }

  //   return this._data;
  // }



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
   * Paste configuration to enable pasted URLs processing by Editor
   *
   * @returns {object} - object of patterns which contain regx for pasteConfig
   */
  static get pasteConfig() {
    return {
      patterns: Embed.patterns,
    };
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
