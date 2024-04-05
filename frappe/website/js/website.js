// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
import hljs from "./syntax_highlight";

frappe.provide("website");
frappe.provide("frappe.awesome_bar_path");
window.cur_frm = null;

Object.assign(frappe, {
	_assets_loaded: [],
	require: async function (links, callback) {
		if (typeof links === "string") {
			links = [links];
		}
		links = links.map((link) => frappe.bundled_asset(link));
		for (let link of links) {
			await this.add_asset_to_head(link);
		}
		callback && callback();
	},
	bundled_asset(path, is_rtl = null) {
		if (!path.startsWith("/assets") && path.includes(".bundle.")) {
			if (path.endsWith(".css") && is_rtl) {
				path = `rtl_${path}`;
			}
			path = frappe.boot.assets_json[path] || path;
			return path;
		}
		return path;
	},
	add_asset_to_head(link) {
		return new Promise((resolve) => {
			if (frappe._assets_loaded.includes(link)) return resolve();
			let el;
			if (link.split(".").pop() === "js") {
				el = document.createElement("script");
				el.type = "text/javascript";
				el.src = link;
			} else {
				el = document.createElement("link");
				el.type = "text/css";
				el.rel = "stylesheet";
				el.href = link;
			}
			document.getElementsByTagName("head")[0].appendChild(el);
			el.onload = () => {
				frappe._assets_loaded.push(link);
				resolve();
			};
		});
	},
	hide_message: function () {
		document.querySelectorAll(".message-overlay").forEach((el) => el.remove());
	},
	xcall: function (method, params) {
		return new Promise((resolve, reject) => {
			frappe.call({
				method: method,
				args: params,
				callback: (r) => {
					resolve(r.message);
				},
				error: (r) => {
					reject(r.message);
				},
			});
		});
	},
	call: async function (opts) {
		// opts = {"method": "PYTHON MODULE STRING", "args": {}, "callback": function(r) {}}
		if (typeof arguments[0] === "string") {
			opts = {
				method: arguments[0],
				args: arguments[1],
				callback: arguments[2],
			};
		}

		frappe.prepare_call(opts);
		if (opts.freeze) {
			frappe.freeze();
		}
		return fetch(opts.url || "/", {
			method: opts.type || "POST",
			headers: {
				"X-Frappe-CSRF-Token": frappe.csrf_token,
				"X-Frappe-CMD": (opts.args && opts.args.cmd) || "" || "",
				"Content-Type": "application/json",
			},
			body: JSON.stringify(opts.args),
		})
			.then((response) => {
				if (response.status === 404) {
					frappe.msgprint(__("Not found"));
				} else if (response.status === 403) {
					frappe.msgprint(__("Not permitted"));
				} else if (response.status === 200) {
					return response.json();
				} else {
					return Promise.reject(response.statusText);
				}
			})
			.then((data) => {
				if (opts.callback) {
					opts.callback(data);
				}
				if (opts.success) {
					opts.success(data);
				}
				if (opts.freeze) {
					frappe.unfreeze();
				}
				frappe.process_response(opts, data);
			})
			.catch((error) => {
				// executed before statusCode functions
				frappe.process_response(opts, { exc: error.toString() });
				return Promise.reject(error);
			});
	},
	prepare_call: function (opts) {
		if (opts.btn) {
			opts.btn.disabled = true;
		}

		if (opts.msg) {
			opts.msg.style.display = "none";
		}

		if (!opts.args) opts.args = {};

		// method
		if (opts.method) {
			opts.args.cmd = opts.method;
		}

		for (let key in opts.args) {
			let val = opts.args[key];
			if (typeof val != "string" && val !== null) {
				opts.args[key] = JSON.stringify(val);
			}
		}

		if (!opts.no_spinner) {
			// NProgress.start();
		}
	},
	process_response: function (opts, data) {
		// if(!opts.no_spinner) NProgress.done();

		if (opts.btn) {
			opts.btn.disabled = true;
		}

		if (data._server_messages) {
			var server_messages = JSON.parse(data._server_messages || "[]");
			server_messages
				.map((msg) => {
					// temp fix for messages sent as dict
					try {
						return JSON.parse(msg);
					} catch (e) {
						return msg;
					}
				})
				.join("<br>");

			if (opts.error_msg) {
				opts.msg.innerHTML = server_messages;
				opts.msg.style.display = "block";
			} else {
				frappe.msgprint(server_messages);
			}
		}

		if (data.exc) {
			try {
				var err = JSON.parse(data.exc);
				if (Array.isArray(err)) {
					err = err.join("\n");
				}
				console.error ? console.error(err) : console.log(err);
			} catch (e) {
				console.log(data.exc);
			}
		}
		if (opts.msg && data.message) {
			opts.msg.innerHTML = data.message;
			opts.msg.style.display = "block";
		}

		if (opts.always) {
			opts.always(data);
		}
	},
	show_message: function (text, icon) {
		frappe.hide_message();
		let messageOverlay = document.createElement("div");
		messageOverlay.classList.add("message-overlay");
		messageOverlay.innerHTML = `
      <div class="content">
        <i class="${icon || "fa fa-refresh fa-spin"} text-muted"></i>
        <br>${text}
      </div>
    `;
		document.body.appendChild(messageOverlay);
	},
	has_permission: function (doctype, docname, perm_type, callback) {
		return frappe.call({
			type: "GET",
			method: "frappe.client.has_permission",
			no_spinner: true,
			args: { doctype: doctype, docname: docname, perm_type: perm_type },
			callback: function (r) {
				if (!r.exc && r.message.has_permission) {
					if (callback) {
						return callback(r);
					}
				}
			},
		});
	},
	render_user: function () {
		if (frappe.is_user_logged_in()) {
			document
				.querySelectorAll(".btn-login-area")
				.forEach((el) => (el.style.display = "none"));
			document.querySelectorAll(".logged-in").forEach((el) => (el.style.display = "block"));
			document.querySelector(".user-image").src = frappe.get_cookie("user_image");

			document.querySelector(".user-image-wrapper").innerHTML = frappe.avatar(
				null,
				"avatar-medium",
				null,
				null,
				null,
				true
			);
			document.querySelector(".user-image-sidebar").innerHTML = frappe.avatar(
				null,
				"avatar-medium",
				null,
				null,
				null,
				true
			);
			document.querySelector(".user-image-myaccount").innerHTML = frappe.avatar(
				null,
				"avatar-large",
				null,
				null,
				null,
				true
			);
		}
	},
	freeze_count: 0,
	freeze: function (msg) {
		// blur
		if (!document.getElementById("freeze")) {
			var freeze = document.createElement("div");
			freeze.id = "freeze";
			freeze.classList.add("modal-backdrop", "fade");
			document.body.appendChild(freeze);

			freeze.innerHTML = repl(
				'<div class="freeze-message-container"><div class="freeze-message">%(msg)s</div></div>',
				{ msg: msg || "" }
			);

			setTimeout(function () {
				freeze.classList.add("in");
			}, 1);
		} else {
			document.getElementById("freeze").classList.add("in");
		}
		frappe.freeze_count++;
	},
	unfreeze: function () {
		if (!frappe.freeze_count) return; // anything open?
		frappe.freeze_count--;
		if (!frappe.freeze_count) {
			var freeze = $("#freeze").removeClass("in");
			setTimeout(function () {
				if (!frappe.freeze_count) {
					freeze.parentNode.removeChild(freeze);
				}
			}, 150);
		}
	},

	trigger_ready: function () {
		frappe.ready_events.forEach(function (fn) {
			fn();
		});
	},

	highlight_code_blocks: function () {
		hljs.highlightAll();
	},
	bind_filters: function () {
		// set in select
		document.querySelectorAll(".filter").forEach(function (el) {
			var key = el.getAttribute("data-key");
			var val = frappe.utils.get_url_arg(key).replace(/\+/g, " ");

			if (val) el.value = val;
		});

		// search url
		var search = function () {
			var args = {};
			document.querySelectorAll(".filter").forEach(function (el) {
				var val = el.value;
				var key = el.getAttribute("data-key");
				if (val) args[key] = val;
			});

			window.location.href = location.pathname + "?" + $.param(args);
		};

		document.querySelectorAll(".filter").forEach(function (el) {
			search();
		});
	},
	bind_navbar_search: function () {
		frappe.get_navbar_search().forEach(function (el) {
			el.addEventListener("keypress", function (e) {
				var val = this.value;
				if (e.which === 13 && val) {
					this.value = "";
					this.blur();
					frappe.do_search(val);
					return false;
				}
			});
		});
	},
	do_search: function (val) {
		var path =
			(frappe.awesome_bar_path && frappe.awesome_bar_path[location.pathname]) ||
			window.search_path ||
			location.pathname;

		window.location.href = path + "?txt=" + encodeURIComponent(val);
	},
	set_search_path: function (path) {
		frappe.awesome_bar_path[location.pathname] = path;
	},
	make_navbar_active: function () {
		var pathname = window.location.pathname;
		document
			.querySelectorAll(".navbar-nav li.active")
			.forEach((el) => el.classList.remove("active"));
		document.querySelectorAll(".navbar-nav li").forEach(function (el) {
			var href = el.querySelector("a").getAttribute("href");
			if (href === pathname) {
				el.classList.add("active");
				return false;
			}
		});
	},
	get_navbar_search: function () {
		return document.querySelectorAll(".navbar .search, .sidebar .search");
	},
	is_user_logged_in: function () {
		return frappe.get_cookie("user_id") !== "Guest" && frappe.session.user !== "Guest";
	},
	add_switch_to_desk: function () {
		document
			.querySelectorAll(".switch-to-desk")
			.forEach((el) => el.classList.remove("hidden"));
	},
	add_link_to_headings: function () {
		document
			.querySelectorAll(
				".doc-content .from-markdown h2, .doc-content .from-markdown h3, .doc-content .from-markdown h4, .doc-content .from-markdown h5, .doc-content .from-markdown h6"
			)
			.forEach((heading) => {
				let id = heading.id;
				let a = document.createElement("a");
				a.classList.add("no-underline");
				a.href = "#" + id;
				a.setAttribute("aria-hidden", "true");
				a.innerHTML = `
 				<svg xmlns="http://www.w3.org/2000/svg" style="width: 0.8em; height: 0.8em;" viewBox="0 0 24 24" fill="none" stroke="currentColor"
 					stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather feather-link">
 					<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
 					<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
 				</svg>
 			`;
				heading.appendChild(a);
			});
	},
	show_language_picker() {
		if (frappe.session.user === "Guest" && window.show_language_picker) {
			frappe
				.call("frappe.translate.get_all_languages", {
					with_language_name: true,
				})
				.then((res) => {
					let language_list = res.message;
					let language = frappe.get_cookie("preferred_language");
					let language_codes = [];
					let language_switcher = document.querySelector(
						"#language-switcher .form-control"
					);
					language_list.forEach((language_doc) => {
						language_codes.push(language_doc.language_code);
						let option = document.createElement("option");
						option.value = language_doc.language_code;
						option.text = language_doc.language_name;
						language_switcher.add(option);
					});
					document.getElementById("language-switcher")?.classList.remove("hide");
					language =
						language ||
						(language_codes.includes(navigator.language) ? navigator.language : "en");
					language_switcher.val(language);
					document.documentElement.lang = language;
					language_switcher.change(() => {
						const lang = language_switcher.val();
						document.cookie = `preferred_language=${lang}`;
						window.location.reload();
					});
				});
		}
	},
	setup_videos: () => {
		// converts video images into youtube embeds (via Page Builder)
		document.querySelectorAll(".section-video-wrapper").forEach((el) => {
			el.addEventListener("click", (e) => {
				let video = e.currentTarget;
				let id = video.dataset.youtubeId;
				console.log(id);
				video.querySelector(".video-thumbnail").style.display = "none";
				video.innerHTML += `
	  			<iframe allowfullscreen="" class="section-video" f;rameborder="0" src="//youtube.com/embed/${id}?autoplay=1"></iframe>
  			`;
			});
		});
	},
});

frappe.setup_search = function (target, search_scope) {
	if (typeof target === "string") {
		target = document.querySelector(target);
	}
	let searchInput = document.createElement("div");
	searchInput.classList.add("dropdown", "id", "dropdownMenuSearch");
	searchInput.innerHTML = `
		<input type="search" class="form-control" placeholder="Search the docs (Press / to focus)" />
		<div class="overflow-hidden shadow dropdown-menu w-100" aria-labelledby="dropdownMenuSearch"></div>
		<div class="search-icon">
			<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather feather-search">
				<circle cx="11" cy="11" r="8"></circle>
				<line x1="21" y1="21" x2="16.65" y2="16.65"></line>
			</svg>
		</div>
	`;

	target.innerHTML = "";
	target.appendChild(searchInput);

	let dropdown = searchInput.querySelector(".dropdown");
	let dropdownMenu = searchInput.querySelector(".dropdown-menu");
	let input = searchInput.querySelector("input");
	let dropdownItems;
	let offsetIndex = 0;

	document.addEventListener("keypress", (e) => {
		if (e.target.matches("textarea, input, select")) {
			return;
		}
		if (e.key === "/") {
			e.preventDefault();
			input.focus();
		}
	});

	input.addEventListener(
		"input",
		frappe.utils.debounce(() => {
			if (!input.value) {
				clear_dropdown();
				return;
			}

			frappe
				.call({
					method: "frappe.search.web_search",
					args: {
						scope: search_scope || null,
						query: input.value,
						limit: 5,
					},
				})
				.then((r) => {
					let results = r.message || [];
					let dropdown_html;
					if (results.length == 0) {
						dropdown_html = `<div class="dropdown-item">No results found</div>`;
					} else {
						dropdown_html = results
							.map((r) => {
								return `<a class="dropdown-item" href="/${r.path}">
						<h6>${r.title_highlights || r.title}</h6>
						<div style="white-space: normal;">${r.content_highlights}</div>
					</a>`;
							})
							.join("");
					}
					dropdownMenu.innerHTML = dropdown_html;
					dropdownMenu.classList.add("show");
					dropdownItems = document.querySelectorAll(".dropdown-menu .dropdown-item");
				});
		}, 500)
	);

	input.addEventListener("focus", () => {
		if (!input.value) {
			clear_dropdown();
		} else {
			input.dispatchEvent(new Event("input"));
		}
	});

	input.addEventListener("keydown", function (e) {
		// up: 38, down: 40
		if (e.which == 40) {
			navigate(0);
		}
	});

	dropdownMenu.addEventListener("keydown", function (e) {
		// up: 38, down: 40
		if (e.which == 38) {
			navigate(-1);
		} else if (e.which == 40) {
			navigate(1);
		} else if (e.which == 27) {
			setTimeout(() => {
				clear_dropdown();
			}, 300);
		}
	});

	// Clear dropdown when clicked
	window.addEventListener("click", function () {
		clear_dropdown();
	});

	searchInput.addEventListener("click", function (event) {
		event.stopPropagation();
	});

	// Navigate the list
	var navigate = function (diff) {
		offsetIndex += diff;

		if (offsetIndex >= dropdownItems.length) offsetIndex = 0;
		if (offsetIndex < 0) offsetIndex = dropdownItems.length - 1;
		input.removeEventListener("blur", undefined);
		dropdownItems.eq(offsetIndex).focus();
	};

	function clear_dropdown() {
		offsetIndex = 0;
		dropdownMenu.innerHtml = "";
		dropdownMenu.classList.remove("show");
		dropdownItems = undefined;
	}

	// Remove focus state on hover
	dropdownMenu.addEventListener("mouseover", function () {
		dropdownItems.blur();
	});
};

// Utility functions
window.valid_email = function (id) {
	// copied regex from frappe/utils.js validate_type
	// eslint-disable-next-line
	return /^((([a-z]|\d|[!#\$%&'\*\+\-\/=\?\^_`{\|}~]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])+(\.([a-z]|\d|[!#\$%&'\*\+\-\/=\?\^_`{\|}~]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])+)*)|((\x22)((((\x20|\x09)*(\x0d\x0a))?(\x20|\x09)+)?(([\x01-\x08\x0b\x0c\x0e-\x1f\x7f]|\x21|[\x23-\x5b]|[\x5d-\x7e]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(\\([\x01-\x09\x0b\x0c\x0d-\x7f]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF]))))*(((\x20|\x09)*(\x0d\x0a))?(\x20|\x09)+)?(\x22)))@((([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])*([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])))\.)+(([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])*([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])))$/.test(
		id.toLowerCase()
	);
};

window.validate_email = window.valid_email;

window.cstr = function (s) {
	return s == null ? "" : s + "";
};

window.is_null = function is_null(v) {
	if (v === null || v === undefined || cstr(v).trim() === "") return true;
};

window.is_html = function is_html(txt) {
	if (
		txt.indexOf("<br>") == -1 &&
		txt.indexOf("<p") == -1 &&
		txt.indexOf("<img") == -1 &&
		txt.indexOf("<div") == -1
	) {
		return false;
	}
	return true;
};

window.ask_to_login = function ask_to_login() {
	if (!frappe.is_user_logged_in()) {
		if (localStorage) {
			localStorage.setItem(
				"last_visited",
				window.location.href.replace(window.location.origin, "")
			);
		}
		window.location.href = "login";
	}
};

// check if logged in?
document.addEventListener("DOMContentLoaded", function (event) {
	window.full_name = frappe.get_cookie("full_name");
	let logged_in = frappe.is_user_logged_in();
	document.getElementById("website-login")?.classList.toggle("hide", logged_in);
	document.getElementById("website-post-login")?.classList.toggle("hide", !logged_in);
	document
		.querySelectorAll(".logged-in")
		.forEach((el) => el.classList.toggle("hide", !logged_in));

	frappe.bind_navbar_search();

	// switch to app link
	if (frappe.get_cookie("system_user") === "yes" && logged_in) {
		frappe.add_switch_to_desk();
	}

	frappe.render_user();

	document.dispatchEvent(new Event("page-change"));
});

document.addEventListener("page-change", function () {
	document.dispatchEvent(new Event("apply_permissions"));
	document.querySelectorAll(".dropdown-toggle").forEach((el) => {
		el.addEventListener("click", function (e) {
			let dropdownMenu = e.target.nextElementSibling;
			if (dropdownMenu) {
				dropdownMenu.classList.toggle("show");
			}
		});
	});
	//multilevel dropdown fix
	document
		.querySelectorAll(".dropdown-menu .dropdown-submenu .dropdown-toggle")
		.forEach((el) => {
			el.addEventListener("click", function (e) {
				e.stopPropagation();
				e.target.closest(".dropdown-submenu").classList.add("open");
			});
		});

	Object.assign(frappe, frappe.get_cookies());
	frappe.session = { user: frappe.user_id };

	// frappe.datetime.refresh_when();
	frappe.trigger_ready();
	frappe.bind_filters();
	frappe.highlight_code_blocks();
	frappe.add_link_to_headings();
	frappe.make_navbar_active();
	// scroll to hash
	if (window.location.hash) {
		document.getElementById(window.location.hash.substring(1))?.scrollIntoView(true);
	}
});

frappe.ready(function () {
	frappe.show_language_picker();
	frappe.setup_videos();
	frappe.realtime.init(window.socketio_port, true); // lazy connection
});
