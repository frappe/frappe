// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// My HTTP Request

frappe.provide("frappe.request");
frappe.provide("frappe.request.error_handlers");
frappe.request.url = "/";
frappe.request.ajax_count = 0;
frappe.request.waiting_for_ajax = [];
frappe.request.logs = {};

frappe.xcall = function (method, params, type, opts = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method: method,
			args: params,
			type: type || "POST",
			callback: (r) => {
				resolve(r.message);
			},
			error: (r) => {
				reject(r?.message);
			},
			...opts,
		});
	});
};

// generic server call (call page, object)
frappe.call = function (opts) {
	const helpers = frappe.call._helpers;

	// Check connectivity (side effect, but informational)
	helpers.check_connectivity();

	// Parse caller arguments (handle legacy calling convention)
	var parsed = helpers.parse_caller_arguments(opts, arguments);
	var options = parsed.opts;

	// Validate API version and doc_origin
	helpers.validate_api_version(options.api_version);
	helpers.validate_doc_origin(options.doc_origin);

	// Validate call type ONLY if no custom URL is provided
	// When using custom URL, method/doc/page are optional since URL is already specified
	if (!options.url) {
		helpers.validate_call_type({
			method: options.method,
			doc: options.doc,
			module: options.module,
			page: options.page,
		});
	}

	// Resolve parameters precedence
	var input_args = options.args || {};
	var resolved_params = helpers.resolve_parameter_precedence({
		opts: { freeze: options.freeze, freeze_message: options.freeze_message },
		args: { freeze: input_args.freeze, freeze_message: input_args.freeze_message },
	});

	// Resolve effective doc_origin and api_version
	var doc_origin_resolution = helpers.resolve_doc_origin_and_api_version({
		api_version: options.api_version,
		doc_origin: options.doc_origin,
		has_doc: !!options.doc,
	});

	// Build server payload
	var payload_result = helpers.build_server_payload({
		method: options.method,
		args: input_args,
		doc: options.doc,
		doc_origin: doc_origin_resolution.doc_origin,
		api_version: doc_origin_resolution.api_version,
		module: options.module,
		page: options.page,
		has_custom_url: !!options.url,
	});

	// Build request URL
	var url_result = helpers.build_request_url({
		custom_url: options.url,
		doc: options.doc,
		doc_origin: doc_origin_resolution.doc_origin,
		api_version: doc_origin_resolution.api_version,
		cmd: payload_result.cmd,
		method: options.method,
	});

	// Check debounce status
	var debounce_check = helpers.check_debounce_status({
		debounce: options.debounce,
		cmd: payload_result.cmd,
		payload: payload_result.payload,
	});

	if (debounce_check.should_skip) {
		return Promise.resolve();
	}

	// Create success handler
	var realtime_opts = $.extend({}, options, {
		freeze: resolved_params.freeze,
		freeze_message: resolved_params.freeze_message,
		api_version: doc_origin_resolution.api_version,
		args: payload_result.payload,
	});
	var success_wrapper = helpers.route_success_callback({
		callback: options.callback,
		queued: options.queued,
		realtime_opts: realtime_opts,
	});

	// Dispatch request
	return frappe.request.call({
		type: options.type || "POST",
		args: payload_result.payload,
		success: success_wrapper.handler,
		error: options.error,
		always: options.always,
		btn: options.btn,
		freeze: resolved_params.freeze,
		freeze_message: resolved_params.freeze_message,
		headers: options.headers || {},
		error_handlers: options.error_handlers || {},
		async: options.async,
		silent: options.silent,
		api_version: doc_origin_resolution.api_version,
		url: url_result.url,
		cache: options.cache,
	});
};

frappe.call._helpers = {
	// Methods here are defined here to keep them encapsulated, without exposing them globally

	/**
	 * Shows connectivity warning if offline.
	 * @returns {{ is_online: boolean }}
	 */
	check_connectivity() {
		var is_online = frappe.is_online();
		if (!is_online) {
			frappe.show_alert(
				{
					indicator: "orange",
					message: __("Connection Lost"),
					subtitle: __("You are not connected to Internet. Retry after sometime."),
				},
				3 // Display time in seconds
			);
		}
		return { is_online };
	},

	/**
	 * Handles legacy calling convention: frappe.call(method, args, callback, headers)
	 * @param {string|object} first_arg - The first argument passed to frappe.call
	 * @param {IArguments} caller_arguments - The full arguments object from frappe.call
	 * @returns {{ opts: object }}
	 */
	parse_caller_arguments(first_arg, caller_arguments) {
		if (typeof first_arg === "string") {
			var [ method, args, callback, headers ] = caller_arguments;

			return {
				opts: {
					method,
					args,
					callback,
					headers,
				},
			};
		}
		return { opts: first_arg };
	},

	/**
	 * Resolves parameter precedence between top-level opts and args.
	 * Top-level options take precedence over args options.
	 * @param {{ opts: object, args: object }} config
	 * @returns {{ freeze: boolean, freeze_message: string|undefined }}
	 */
	resolve_parameter_precedence(config) {
		var { opts, args } = config;

		var resolved_freeze = opts.freeze || args.freeze || false;
		var resolved_freeze_message = opts.freeze_message || args.freeze_message;

		return {
			freeze: resolved_freeze,
			freeze_message: resolved_freeze_message,
		};
	},

	/**
	 * Validates API version parameter.
	 * Throws if the provided version is not supported.
	 * @param {string|undefined} api_version
	 * @returns {{ is_valid: boolean }}
	 */
	validate_api_version(api_version) {
		var valid_versions = ["v1", "v2"];
		let is_valid = !api_version || valid_versions.includes(api_version);
		if (!is_valid) {
			console.error("frappe.call unsupported api_version");
			throw new Error(
				`frappe.call: api_version '${api_version}' is not supported. Use one of: ${valid_versions.join(", ")}`
			);
		}
		return { is_valid };
	},

	/**
	 * Validates doc_origin parameter.
	 * Throws if the provided origin is not supported.
	 * @param {string|undefined} doc_origin
	 * @returns {{ is_valid: boolean }}
	 */
	validate_doc_origin(doc_origin) {
		var valid_origins = ["memory", "database"];
		let is_valid = !doc_origin || valid_origins.includes(doc_origin);
		if (!is_valid) {
			console.error("frappe.call unsupported doc_origin");
			throw new Error(
				`frappe.call: doc_origin '${doc_origin}' is not supported. Use one of: ${valid_origins.join(", ")}`
			);
		}
		return { is_valid };
	},

	/**
	 * Validates that at least one valid call type is specified.
	 * Valid call types are: page method (module + page), document method (doc), or direct method (method).
	 * Throws if none of the valid call types is specified.
	 * @param {{ method: string|undefined, doc: object|undefined, module: string|undefined, page: string|undefined }} config
	 * @returns {{ is_valid: boolean }}
	 */
	validate_call_type(config) {
		var { method, doc, module, page } = config;
		
		var has_page_call = module != null && page != null;
		var has_doc_call = doc != null;
		var has_method_call = method != null;

		let is_valid = has_page_call || has_doc_call || has_method_call;
		if (is_valid) {
			return { is_valid };
		}

		var missing_options = [
			!has_method_call && "'method' (direct method call)",
			!has_doc_call && "'doc' (document method call)",
			!has_page_call && "'module' and 'page' (page method call)",
		].filter(Boolean);

		console.error("frappe.call invalid call configuration");
		throw new Error(
			`frappe.call: invalid call configuration. Must provide one of: ${missing_options.join(", ")}`
		);
	},

	/**
	 * Resolves the effective doc_origin and api_version based on provided options.
	 * Both API v1 and v2 support both origins:
	 * - 'memory' (default): Uses run_doc_method, sends full in-memory document to server
	 * - 'database': Server loads document from DB (lighter payload)
	 *
	 * @param {{ api_version: string|undefined, doc_origin: string|undefined, has_doc: boolean }} config
	 * @returns {{ api_version: string|undefined, doc_origin: string|undefined }}
	 */
	resolve_doc_origin_and_api_version(config) {
		var { api_version, doc_origin, has_doc } = config;

		// doc_origin is only relevant when doc is provided
		if (!has_doc) {
			return {
				api_version: api_version,
				doc_origin: undefined,
			};
		}

		var resolved_api_version = api_version;
		var resolved_doc_origin = doc_origin || "memory";

		// When api_version is not specified and doc_origin='database' is requested,
		// we default to v1 for the database origin endpoint
		if (resolved_doc_origin === "database" && !resolved_api_version) {
			resolved_api_version = "v1";
		}

		return {
			api_version: resolved_api_version,
			doc_origin: resolved_doc_origin,
		};
	},

	/**
	 * Builds and prepares the server payload
	 * Determinates the appropriate cmd and payload structure based on call type and doc_origin.
	 * @param {{ method: string, args: object, doc: object|undefined, doc_origin: string|undefined, api_version: string|undefined, module: string|undefined, page: string|undefined, has_custom_url: boolean }} config
	 * @returns {{ payload: object, cmd: string|undefined }}
	 */
	build_server_payload(config) {
		var { method, args, doc, doc_origin, api_version, module, page, has_custom_url } = config;

		var base_payload;
		var cmd_value;

		if (module && page) {
			// Page method call
			base_payload = $.extend({}, args);
			cmd_value = `${module}.page.${page}.${page}.${method}`
			
			// Add cmd to payload if custom URL
			if (has_custom_url) {
				base_payload.cmd = cmd_value;
			}
		} else if (doc && doc_origin === "memory") {
			// Document method call with memory origin
			cmd_value = "run_doc_method";

			const { doctype, name } = doc;
			// Retrieve full document
			// from in-memory cache if available, or from server if not in cache
			const docs = frappe.get_doc(doctype, name);

			base_payload = {
				docs,
				method,
				args,
			};
			
			// Add cmd to payload if custom URL
			if (has_custom_url) {
				base_payload.cmd = cmd_value;
			}
		} else if (doc && doc_origin === "database") {
			// Document method call with database origin
			// Server loads document from DB (lighter payload).
			cmd_value = undefined; // database origin doesn't use cmd
			base_payload = $.extend({}, args);

			// For v1: method is passed via run_method in form data
			// For v2: method is in URL path, no need to add inside payload
			if (api_version === "v1") {
				base_payload.run_method = method;
			}
		} else if (method) {
			// Direct method call
			cmd_value = method;
			base_payload = $.extend({}, args);
			
			// Add cmd to payload if custom URL
			if (has_custom_url) {
				base_payload.cmd = cmd_value;
			}
		} else {
			// No call pattern specified (custom URL case)
			// Just use args as-is, no cmd
			cmd_value = undefined;
			base_payload = $.extend({}, args);
		}

		return {
			payload: base_payload,
			cmd: cmd_value,
		};
	},

	/**
	 * Validates required parameters for database origin document method calls.
	 * Throws if any required parameter is missing.
	 * @param {{ doctype: string|undefined, name: string|undefined, method: string|undefined }} config
	 * @returns {{ is_valid: boolean }}
	 */
	validate_document_method_params(config) {
		var { doctype, name, method } = config;
		
		var has_doctype = doctype != null;
		var has_name = name != null;
		var has_method = method != null;

		var is_valid = has_doctype && has_name && has_method;
		if (!is_valid) {
			var missing = [
				!has_doctype && "doc.doctype (document doctype)",
				!has_name && "doc.name (document name)",
				!has_method && "method (method name to run on the document)",
			].filter(Boolean);

			if (missing.length) {
				console.error("frappe.call missing parameters");
				throw new Error(
					`frappe.call: missing '${missing.join("', '")}' required for database origin document method calls`
				);
			}
		}

		return { is_valid };
	},

	/**
	 * Builds URL for database origin document method calls.
	 * Supports both v1 and v2 API versions:
	 * - v1: POST to /api/v1/resource/<doctype>/<name>/ with run_method in form data
	 * - v2: method is part of the URL path /api/v2/document/<doctype>/<name>/method/<method>/
	 * @param {{ api_version: string, doctype: string, name: string, method?: string }} config
	 * @returns {{ url: string }}
	 */
	build_doc_db_origin_url(config) {
		var { api_version, doctype, name, method } = config;

		var identifier = `${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`;
		var version = api_version || "v1";
		var method_name = null;
		var route;

		switch (version) {
			case "v2":
				method_name = `method/${encodeURIComponent(method)}`;
				route = "document";
				break;
			
			case "v1":
			default:
				method_name = ""; // method is passed via form data in v1, not in URL
				route = "resource";
				break;
		}
		
		var url = `/api/${version}/${route}/${identifier}`;
		if (method_name) url += `/${method_name}`;
		
		return { url };
	},

	/**
	 * Builds URL for standard method calls.
	 * @param {{ api_version: string|undefined, cmd: string }} config
	 * @returns {{ url: string }}
	 */
	build_standard_method_url(config) {
		var { api_version, cmd } = config;

		var prefix = "/api/method";
		if (api_version) {
			// Both 'v1' and 'v2' use same prefix for non-doc calls
			prefix = `/api/${api_version}/method`;
		}
		return { url: `${prefix}/${cmd}` };
	},

	/**
	 * Applies Cordova host prefix to URL.
	 * @param {string} url
	 * @returns {{ url: string }}
	 */
	apply_cordova_host(url) {
		var host = frappe.request.url;
		host = host.slice(0, host.length - 1);
		return { url: `${host}${url}` };
	},

	/**
	 * Builds the complete request URL if needed.
	 * Throws (via validate_document_method_params) if required params are missing for database origin calls.
	 * @param {{ custom_url: string|undefined, doc: object|undefined, doc_origin: string|undefined, api_version: string|undefined, cmd: string|undefined, method: string|undefined }} config
	 * @returns {{ url: string }}
	 */
	build_request_url(config) {
		var { custom_url, doc, doc_origin, api_version, cmd, method } = config;

		// Use custom URL if provided
		if (custom_url) {
			return { url: custom_url };
		}

		var url;

		// Database origin document method URL
		if (doc && doc_origin === "database") {
			// Validate required params for database origin — throws if missing
			this.validate_document_method_params({
				doctype: doc.doctype,
				name: doc.name,
				method: method,
			});

			var doc_url = this.build_doc_db_origin_url({
				api_version: api_version,
				doctype: doc.doctype,
				name: doc.name,
				method: method,
			});
			url = doc_url.url;
		} else {
			// Standard method URL
			var std_url = this.build_standard_method_url({
				api_version: api_version,
				cmd: cmd,
			});
			url = std_url.url;
		}

		// Apply Cordova host if needed
		if (window.cordova) {
			var cordova_url = this.apply_cordova_host(url);
			url = cordova_url.url;
		}

		return { url };
	},

	/**
	 * Creates the success callback handler.
	 * For async tasks, the realtime_opts object is passed to frappe.realtime.subscribe
	 * which requires the full set of callback and cleanup options.
	 * @param {{ callback: function|undefined, queued: function|undefined, realtime_opts: object }} config
	 * @returns {function}
	 */
	route_success_callback(config) {
		var { callback, queued, realtime_opts } = config;

		const handler = (data, response_text) => {
			// Async task: subscribe to realtime updates
			if (data.task_id) {
				frappe.realtime.subscribe(data.task_id, realtime_opts);

				if (queued) {
					queued(data);
				}
				return;
			}

			// Regular callback
			if (callback) {
				return callback(data, response_text);
			}
		};

		return { handler };
	},

	/**
	 * Checks if request should be debounced (skipped due to recent identical request).
	 * @param {{ debounce: number|undefined, cmd: string, payload: object }} config
	 * @returns {{ should_skip: boolean }}
	 */
	check_debounce_status(config) {
		var { debounce, cmd, payload } = config;

		if (!debounce) {
			return { should_skip: false };
		}

		// Build args object with cmd for is_fresh check
		var args_with_cmd = $.extend({}, payload, { cmd: cmd });
		var is_fresh = frappe.request.is_fresh(args_with_cmd, debounce);

		return { should_skip: is_fresh };
	},
};

frappe.request.call = function (opts) {
	frappe.request.prepare(opts);

	var statusCode = {
		200: function (data, xhr) {
			opts.success_callback && opts.success_callback(data, xhr.responseText);
		},
		401: function (xhr) {
			if (frappe.app.session_expired_dialog && frappe.app.session_expired_dialog.display) {
				frappe.app.redirect_to_login();
			} else {
				frappe.app.handle_session_expired();
			}
			opts.error_callback && opts.error_callback();
		},
		404: function (xhr) {
			frappe.msgprint({
				title: __("Not found"),
				indicator: "red",
				message: __("The resource you are looking for is not available"),
			});
			opts.error_callback && opts.error_callback();
		},
		403: function (xhr) {
			if (frappe.session.user === "Guest" && frappe.session.logged_in_user !== "Guest") {
				// session expired
				frappe.app.handle_session_expired();
			} else if (xhr.responseJSON && xhr.responseJSON._error_message) {
				frappe.msgprint({
					title: __("Not permitted"),
					indicator: "red",
					message: xhr.responseJSON._error_message,
					re_route: true,
				});

				xhr.responseJSON._server_messages = null;
			} else if (xhr.responseJSON && xhr.responseJSON._server_messages) {
				var _server_messages = JSON.parse(xhr.responseJSON._server_messages);

				// avoid double messages
				if (_server_messages.indexOf(__("Not permitted")) !== -1) {
					return;
				}
			} else {
				frappe.msgprint({
					title: __("Not permitted"),
					indicator: "red",
					message: __(
						"You do not have enough permissions to access this resource. Please contact your manager to get access."
					),
				});
			}
			opts.error_callback && opts.error_callback();
		},
		508: function (xhr) {
			frappe.utils.play_sound("error");
			frappe.msgprint({
				title: __("Please try again"),
				indicator: "red",
				message: __(
					"Another transaction is blocking this one. Please try again in a few seconds."
				),
			});
			opts.error_callback && opts.error_callback();
		},
		413: function (data, xhr) {
			frappe.msgprint({
				indicator: "red",
				title: __("File too big"),
				message: __("File size exceeded the maximum allowed size of {0} MB", [
					(frappe.boot.max_file_size || 5242880) / 1048576,
				]),
			});
			opts.error_callback && opts.error_callback();
		},
		417: function (xhr) {
			var r = xhr.responseJSON;
			if (!r) {
				try {
					r = JSON.parse(xhr.responseText);
				} catch (e) {
					r = xhr.responseText;
				}
			}

			opts.error_callback && opts.error_callback(r);
		},
		501: function (data, xhr) {
			if (typeof data === "string") data = JSON.parse(data);
			opts.error_callback && opts.error_callback(data, xhr.responseText);
		},
		500: function (xhr) {
			frappe.utils.play_sound("error");
			try {
				opts.error_callback && opts.error_callback();
				frappe.request.report_error(xhr, opts);
			} catch (e) {
				frappe.request.report_error(xhr, opts);
			}
		},
		504: function (xhr) {
			frappe.msgprint(__("Request Timed Out"));
			opts.error_callback && opts.error_callback();
		},
		502: function (xhr) {
			frappe.msgprint(__("Internal Server Error"));
			opts.error_callback && opts.error_callback();
		},
	};

	var exception_handlers = {
		QueryTimeoutError: function () {
			frappe.utils.play_sound("error");
			frappe.msgprint({
				title: __("Request Timeout"),
				indicator: "red",
				message: __("Server was too busy to process this request. Please try again."),
			});
		},
		QueryDeadlockError: function () {
			frappe.utils.play_sound("error");
			frappe.msgprint({
				title: __("Deadlock Occurred"),
				indicator: "red",
				message: __(
					"Server failed to process this request because of a concurrent conflicting request. Please try again."
				),
			});
		},
	};

	var ajax_args = {
		url: opts.url || frappe.request.url,
		data: opts.args,
		type: opts.type,
		dataType: opts.dataType || "json",
		async: opts.async,
		headers: Object.assign(
			{
				"X-Frappe-CSRF-Token": frappe.csrf_token,
				Accept: "application/json",
				"X-Frappe-CMD": (opts.args && opts.args.cmd) || "" || "",
			},
			opts.headers
		),
		cache: window.dev_server ? false : opts.cache || false,
	};

	if (opts.args && opts.args.doctype) {
		ajax_args.headers["X-Frappe-Doctype"] = encodeURIComponent(opts.args.doctype);
	}

	frappe.last_request = ajax_args.data;

	return $.ajax(ajax_args)
		.done(function (data, textStatus, xhr) {
			try {
				if (typeof data === "string") data = JSON.parse(data);

				// sync attached docs
				if (data.docs || data.docinfo) {
					frappe.model.sync(data);
				}

				// sync translated messages
				if (data.__messages) {
					$.extend(frappe._messages, data.__messages);
				}

				// sync link titles
				if (data._link_titles) {
					if (!frappe._link_titles) {
						frappe._link_titles = {};
					}
					$.extend(frappe._link_titles, data._link_titles);
				}

				// callbacks
				var status_code_handler = statusCode[xhr.statusCode().status];
				if (status_code_handler) {
					status_code_handler(data, xhr);
				}
			} catch (e) {
				console.log("Unable to handle success response", data);
				console.error(e);
			}
		})
		.always(function (data, textStatus, xhr) {
			try {
				if (typeof data === "string") {
					data = JSON.parse(data);
				}
				if (data.responseText) {
					var xhr = data; // eslint-disable-line
					data = JSON.parse(data.responseText);
				}
			} catch (e) {
				data = null;
				// pass
			}
			frappe.request.cleanup(opts, data);
			if (opts.always) {
				opts.always(data);
			}
		})
		.fail(function (xhr, textStatus) {
			try {
				if (
					xhr.getResponseHeader("content-type") == "application/json" &&
					xhr.responseText
				) {
					var data;
					try {
						data = JSON.parse(xhr.responseText);
					} catch (e) {
						console.log("Unable to parse reponse text");
						console.log(xhr.responseText);
						console.log(e);
					}
					if (data && data.exception) {
						// frappe.exceptions.CustomError: (1024, ...) -> CustomError
						var exception = data.exception.split(".").at(-1).split(":").at(0);
						var exception_handler = exception_handlers[exception];
						if (exception_handler) {
							exception_handler(data);
							return;
						}
					}
				}
				var status_code_handler = statusCode[xhr.statusCode().status];
				if (status_code_handler) {
					status_code_handler(xhr);
					return;
				}
				// if not handled by error handler!
				opts.error_callback && opts.error_callback(xhr);
			} catch (e) {
				console.log("Unable to handle failed response");
				console.error(e);
			}
		});
};

frappe.request.is_fresh = function (args, threshold) {
	// return true if a request with similar args has been sent recently
	if (!frappe.request.logs[args.cmd]) {
		frappe.request.logs[args.cmd] = [];
	}

	for (let past_request of frappe.request.logs[args.cmd]) {
		// check if request has same args and was made recently
		if (
			new Date() - past_request.timestamp < threshold &&
			frappe.utils.deep_equal(args, past_request.args)
		) {
			console.log("throttled");
			return true;
		}
	}

	// log the request
	frappe.request.logs[args.cmd].push({ args: args, timestamp: new Date() });
	return false;
};

// call execute serverside request
frappe.request.prepare = function (opts) {
	$("body").attr("data-ajax-state", "triggered");

	// btn indicator
	if (opts.btn) $(opts.btn).prop("disabled", true);

	// freeze page
	if (opts.freeze) frappe.dom.freeze(opts.freeze_message);

	// stringify args if required
	for (var key in opts.args) {
		if (opts.args[key] && ($.isPlainObject(opts.args[key]) || $.isArray(opts.args[key]))) {
			opts.args[key] = JSON.stringify(opts.args[key]);
		}
	}

	// no cmd?
	if (!opts.args.cmd && !opts.url) {
		console.log(opts);
		throw "Incomplete Request";
	}

	opts.success_callback = opts.success;
	opts.error_callback = opts.error;
	delete opts.success;
	delete opts.error;
};

frappe.request.cleanup = function (opts, r) {
	// stop button indicator
	if (opts.btn) {
		$(opts.btn).prop("disabled", false);
	}

	$("body").attr("data-ajax-state", "complete");

	// un-freeze page
	if (opts.freeze) frappe.dom.unfreeze();

	if (r) {
		// session expired? - Guest has no business here!
		if (
			r.session_expired ||
			(frappe.session.user === "Guest" && frappe.session.logged_in_user !== "Guest")
		) {
			frappe.app.handle_session_expired();
			return;
		}

		// error handlers
		let global_handlers = frappe.request.error_handlers[r.exc_type] || [];
		let request_handler = opts.error_handlers ? opts.error_handlers[r.exc_type] : null;
		let handlers = [].concat(global_handlers, request_handler).filter(Boolean);

		if (r.exc_type) {
			handlers.forEach((handler) => {
				handler(r);
			});
		}

		// show messages
		//
		let messages;
		if (opts.api_version == "v2") {
			messages = r.messages;
		} else if (r._server_messages) {
			messages = JSON.parse(r._server_messages);
		}
		if (messages && !opts.silent) {
			// show server messages if no handlers exist
			if (handlers.length === 0) {
				frappe.hide_msgprint();
				frappe.msgprint(messages);
			}
		}

		// show errors
		if (r.exc) {
			r.exc = JSON.parse(r.exc);
			if (r.exc instanceof Array) {
				r.exc.forEach((exc) => {
					if (exc) {
						console.error(exc);
					}
				});
			} else {
				console.error(r.exc);
			}
		}

		// debug messages
		if (r._debug_messages) {
			if (opts.args) {
				console.log("======== arguments ========");
				console.log(opts.args);
			}
			console.log("======== debug messages ========");
			$.each(JSON.parse(r._debug_messages), function (i, v) {
				console.log(v);
			});
			console.log("======== response ========");
			delete r._debug_messages;
			console.log(r);
			console.log("========");
		}
	}

	frappe.last_response = r;
};

frappe.after_server_call = () => {
	if (frappe.request.ajax_count) {
		return new Promise((resolve) => {
			frappe.request.waiting_for_ajax.push(() => {
				resolve();
			});
		});
	} else {
		return null;
	}
};

frappe.after_ajax = function (fn) {
	return new Promise((resolve) => {
		if (frappe.request.ajax_count) {
			frappe.request.waiting_for_ajax.push(() => {
				if (fn) return resolve(fn());
				resolve();
			});
		} else {
			if (fn) return resolve(fn());
			resolve();
		}
	});
};

frappe.request.report_error = function (xhr, request_opts) {
	var data = JSON.parse(xhr.responseText);
	var exc;
	if (data.exc) {
		try {
			exc = (JSON.parse(data.exc) || []).join("\n");
		} catch (e) {
			exc = data.exc;
		}
		delete data.exc;
	} else {
		exc = "";
	}

	const copy_markdown_to_clipboard = () => {
		const code_block = (snippet) => "```\n" + snippet + "\n```";

		let request_data = Object.assign({}, request_opts);
		request_data.request_id = xhr.getResponseHeader("X-Frappe-Request-Id");
		const traceback_info = [
			"### App Versions",
			code_block(JSON.stringify(frappe.boot.versions, null, "\t")),
			"### Route",
			code_block(frappe.get_route_str()),
			"### Traceback",
			code_block(exc),
			"### Request Data",
			code_block(JSON.stringify(request_data, null, "\t")),
			"### Response Data",
			code_block(JSON.stringify(data, null, "\t")),
		].join("\n");
		frappe.utils.copy_to_clipboard(traceback_info);
	};

	var show_communication = function () {
		var error_report_message = [
			"<h5>Please type some additional information that could help us reproduce this issue:</h5>",
			'<div style="min-height: 100px; border: 1px solid #bbb; \
				border-radius: 5px; padding: 15px; margin-bottom: 15px;"></div>',
			"<hr>",
			"<h5>App Versions</h5>",
			"<pre>" + JSON.stringify(frappe.boot.versions, null, "\t") + "</pre>",
			"<h5>Route</h5>",
			"<pre>" + frappe.get_route_str() + "</pre>",
			"<hr>",
			"<h5>Error Report</h5>",
			"<pre>" + exc + "</pre>",
			"<hr>",
			"<h5>Request Data</h5>",
			"<pre>" + JSON.stringify(request_opts, null, "\t") + "</pre>",
			"<hr>",
			"<h5>Response JSON</h5>",
			"<pre>" + JSON.stringify(data, null, "\t") + "</pre>",
		].join("\n");

		var communication_composer = new frappe.views.CommunicationComposer({
			subject: "Error Report [" + frappe.datetime.nowdate() + "]",
			recipients: error_report_email,
			message: error_report_message,
			doc: {
				doctype: "User",
				name: frappe.session.user,
			},
		});
		communication_composer.dialog.$wrapper.css(
			"z-index",
			cint(frappe.msg_dialog.$wrapper.css("z-index")) + 1
		);
	};

	if (exc) {
		var error_report_email = frappe.boot.error_report_email;

		request_opts = frappe.request.cleanup_request_opts(request_opts);

		// window.msg_dialog = frappe.msgprint({message:error_message, indicator:'red', big: true});

		if (!frappe.error_dialog) {
			frappe.error_dialog = new frappe.ui.Dialog({
				title: __("Server Error"),
			});
		}

		if (error_report_email) {
			frappe.error_dialog.set_primary_action(__("Report"), () => {
				show_communication();
				frappe.error_dialog.hide();
			});
		} else {
			frappe.error_dialog.set_primary_action(__("Copy error to clipboard"), () => {
				copy_markdown_to_clipboard();
				frappe.error_dialog.hide();
			});
		}
		frappe.error_dialog.wrapper.classList.add("msgprint-dialog");

		let parts = strip(exc).split("\n");

		let dialog_html = parts[parts.length - 1];

		if (data._exc_source) {
			dialog_html += "<br>";
			dialog_html += `Possible source of error: ${data._exc_source.bold()} `;
		}

		frappe.error_dialog.$body.html(dialog_html);
		frappe.error_dialog.show();
	}
};

frappe.request.cleanup_request_opts = function (request_opts) {
	let doc = (request_opts.args || {}).doc;
	if (doc) {
		doc = JSON.parse(doc);
		frappe.utils.mask_passwords(doc);
		request_opts.args.doc = JSON.stringify(doc);
	}

	if (request_opts.args) {
		frappe.utils.mask_passwords(request_opts.args);
	}

	return request_opts;
};

frappe.request.on_error = function (error_type, handler) {
	frappe.request.error_handlers[error_type] = frappe.request.error_handlers[error_type] || [];
	frappe.request.error_handlers[error_type].push(handler);
};

$(document).ajaxSend(function () {
	frappe.request.ajax_count++;
});

$(document).ajaxComplete(function () {
	frappe.request.ajax_count--;
	if (!frappe.request.ajax_count) {
		$.each(frappe.request.waiting_for_ajax || [], function (i, fn) {
			fn();
		});
		frappe.request.waiting_for_ajax = [];
	}
});
