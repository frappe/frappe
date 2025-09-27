frappe.ui.form.on("User", {
	setup: function (frm) {
		frm.set_query("default_workspace", () => {
			return {
				filters: {
					for_user: ["in", [null, frappe.session.user]],
					title: ["!=", "Welcome Workspace"],
				},
			};
		});
	},
	before_load: function (frm) {
		let update_tz_options = function () {
			frm.fields_dict.time_zone.set_data(frappe.all_timezones);
		};

		if (!frappe.all_timezones) {
			frappe.call({
				method: "frappe.core.doctype.user.user.get_timezones",
				callback: function (r) {
					frappe.all_timezones = r.message.timezones;
					update_tz_options();
				},
			});
		} else {
			update_tz_options();
		}
	},

	time_zone: function (frm) {
		if (frm.doc.time_zone && frm.doc.time_zone.startsWith("Etc")) {
			frm.set_df_property(
				"time_zone",
				"description",
				__("Note: Etc timezones have their signs reversed.")
			);
		}
	},

	module_profile: function (frm) {
		if (frm.doc.module_profile) {
			frappe.call({
				method: "frappe.core.doctype.user.user.get_module_profile",
				args: {
					module_profile: frm.doc.module_profile,
				},
				callback: function (data) {
					frm.set_value("block_modules", []);
					$.each(data.message || [], function (i, v) {
						let d = frm.add_child("block_modules");
						d.module = v.module;
					});
					frm.module_editor.disable = 1;
					frm.module_editor && frm.module_editor.show();
				},
			});
		}
	},

	onload: function (frm) {
		frm.can_edit_roles = has_access_to_edit_user();

		if (frm.is_new() && frm.roles_editor) {
			frm.roles_editor.reset();
		}

		if (
			frm.can_edit_roles &&
			!frm.is_new() &&
			["System User", "Website User"].includes(frm.doc.user_type)
		) {
			if (!frm.roles_editor) {
				const role_area = $('<div class="role-editor">').appendTo(
					frm.fields_dict.roles_html.wrapper
				);

				frm.roles_editor = new frappe.RoleEditor(
					role_area,
					frm,
					frm.doc.role_profiles && frm.doc.role_profiles.length ? 1 : 0
				);

				if (frm.doc.user_type == "System User") {
					var module_area = $("<div>").appendTo(frm.fields_dict.modules_html.wrapper);
					frm.module_editor = new frappe.ModuleEditor(
						frm,
						module_area,
						frm.doc.module_profile ? 1 : 0
					);
				}
			} else {
				frm.roles_editor.show();
			}
		}
	},
	refresh: function (frm) {
		let doc = frm.doc;

		frappe.xcall("frappe.apps.get_apps").then((r) => {
			let apps = r?.map((r) => r.name) || [];
			frm.set_df_property("default_app", "options", [" ", ...apps]);
		});

		if (frm.is_new()) {
			frm.set_value("time_zone", frappe.sys_defaults.time_zone);
		}

		if (
			["System User", "Website User"].includes(frm.doc.user_type) &&
			!frm.is_new() &&
			!frm.roles_editor &&
			frm.can_edit_roles
		) {
			frm.reload_doc();
			return;
		}

		frm.toggle_display(["sb1", "sb3", "modules_access"], false);
		frm.trigger("setup_impersonation");

		if (!frm.is_new()) {
			if (has_access_to_edit_user()) {
				// Add passkey management buttons if enabled and user can manage own passkeys
				frm.trigger("setup_passkey_buttons");

				frm.add_custom_button(
					__("Set User Permissions"),
					function () {
						frappe.route_options = {
							user: doc.name,
						};
						frappe.set_route("List", "User Permission");
					},
					__("Permissions")
				);

				frm.add_custom_button(
					__("View Permitted Documents"),
					() =>
						frappe.set_route("query-report", "Permitted Documents For User", {
							user: frm.doc.name,
						}),
					__("Permissions")
				);

				frm.add_custom_button(
					__("View Doctype Permissions"),
					() =>
						frappe.set_route("query-report", "User Doctype Permissions", {
							user: frm.doc.name,
						}),
					__("Permissions")
				);

				frm.toggle_display(["sb1", "sb3", "modules_access"], true);
			}

			frm.add_custom_button(
				__("Reset Password"),
				function () {
					frappe.call({
						method: "frappe.core.doctype.user.user.reset_password",
						args: {
							user: frm.doc.name,
						},
					});
				},
				__("Password")
			);

			if (frappe.user.has_role("System Manager")) {
				frappe.db.get_single_value("LDAP Settings", "enabled").then((value) => {
					if (value === 1 && frm.doc.name != "Administrator") {
						frm.add_custom_button(
							__("Reset LDAP Password"),
							function () {
								const d = new frappe.ui.Dialog({
									title: __("Reset LDAP Password"),
									fields: [
										{
											label: __("New Password"),
											fieldtype: "Password",
											fieldname: "new_password",
											reqd: 1,
										},
										{
											label: __("Confirm New Password"),
											fieldtype: "Password",
											fieldname: "confirm_password",
											reqd: 1,
										},
										{
											label: __("Logout All Sessions"),
											fieldtype: "Check",
											fieldname: "logout_sessions",
										},
									],
									primary_action: (values) => {
										d.hide();
										if (values.new_password !== values.confirm_password) {
											frappe.throw(__("Passwords do not match!"));
										}
										frappe.call(
											"frappe.integrations.doctype.ldap_settings.ldap_settings.reset_password",
											{
												user: frm.doc.email,
												password: values.new_password,
												logout: values.logout_sessions,
											}
										);
									},
								});
								d.show();
							},
							__("Password")
						);
					}
				});
			}

			if (
				cint(frappe.boot.sysdefaults.enable_two_factor_auth) &&
				(frappe.session.user == doc.name || frappe.user.has_role("System Manager"))
			) {
				frm.add_custom_button(
					__("Reset OTP Secret"),
					function () {
						frappe.call({
							method: "frappe.twofactor.reset_otp_secret",
							args: {
								user: frm.doc.name,
							},
						});
					},
					__("Password")
				);
			}

			frm.trigger("enabled");

			if (frm.roles_editor && frm.can_edit_roles) {
				frm.roles_editor.disable =
					frm.doc.role_profiles && frm.doc.role_profiles.length ? 1 : 0;
				frm.roles_editor.show();
			}

			frm.module_editor.disable = frm.doc.module_profile ? 1 : 0;
			frm.module_editor && frm.module_editor.show();

			if (frappe.session.user == doc.name) {
				// update display settings
				if (doc.user_image) {
					frappe.boot.user_info[frappe.session.user].image = frappe.utils.get_file_link(
						doc.user_image
					);
				}
			}
		}
		if (frm.doc.user_emails && frappe.model.can_create("Email Account")) {
			var found = 0;
			for (var i = 0; i < frm.doc.user_emails.length; i++) {
				if (frm.doc.email == frm.doc.user_emails[i].email_id) {
					found = 1;
				}
			}
			if (!found) {
				frm.add_custom_button(__("Create User Email"), function () {
					if (!frm.doc.email) {
						frappe.msgprint(__("Email is mandatory to create User Email"));
						return;
					}
					frm.events.create_user_email(frm);
				});
			}
		}

		if (frappe.route_flags.unsaved === 1) {
			delete frappe.route_flags.unsaved;
			for (let i = 0; i < frm.doc.user_emails.length; i++) {
				frm.doc.user_emails[i].idx = frm.doc.user_emails[i].idx + 1;
			}
			frm.dirty();
		}
		frm.trigger("time_zone");
	},
	validate: function (frm) {
		if (frm.roles_editor) {
			frm.roles_editor.set_roles_in_table();
		}
	},
	enabled: function (frm) {
		var doc = frm.doc;
		if (!frm.is_new() && has_access_to_edit_user()) {
			frm.toggle_display(["sb1", "sb3", "modules_access"], doc.enabled);
			frm.set_df_property("enabled", "read_only", 0);
		}

		if (frm.doc.name !== "Administrator") {
			frm.toggle_enable("email", frm.is_new());
		}
	},
	create_user_email: function (frm) {
		frappe.call({
			method: "frappe.core.doctype.user.user.has_email_account",
			args: {
				email: frm.doc.email,
			},
			callback: function (r) {
				if (!Array.isArray(r.message) || !r.message.length) {
					frappe.route_options = {
						email_id: frm.doc.email,
						awaiting_password: 1,
						enable_incoming: 1,
					};
					frappe.model.with_doctype("Email Account", function (doc) {
						doc = frappe.model.get_new_doc("Email Account");
						frappe.route_flags.linked_user = frm.doc.name;
						frappe.route_flags.delete_user_from_locals = true;
						frappe.set_route("Form", "Email Account", doc.name);
					});
				} else {
					frappe.route_flags.create_user_account = frm.doc.name;
					frappe.set_route("Form", "Email Account", r.message[0]["name"]);
				}
			},
		});
	},
	generate_keys: function (frm) {
		frappe.call({
			method: "frappe.core.doctype.user.user.generate_keys",
			args: {
				user: frm.doc.name,
			},
			callback: function (r) {
				if (r.message) {
					show_api_key_dialog(r.message.api_key, r.message.api_secret);
					frm.reload_doc();
				}
			},
		});
	},
	after_save: function (frm) {
		/**
		 * Checks whether the effective value has changed.
		 *
		 * @param {Array.<string>} - Tuple with new override, previous override,
		 *   and optionally fallback.
		 * @returns {boolean} - Whether the resulting value has effectively changed
		 */
		const has_effectively_changed = ([new_override, prev_override, fallback = undefined]) => {
			const prev_effective = prev_override || fallback;
			const new_effective = new_override || fallback;
			return new_override !== undefined && prev_effective !== new_effective;
		};

		const doc = frm.doc;
		const boot = frappe.boot;
		const attr_tuples = [
			[doc.language, boot.user.language, boot.sysdefaults.language],
			[doc.time_zone, boot.time_zone.user, boot.time_zone.system],
			[doc.desk_theme, boot.user.desk_theme], // No system default.
		];

		if (doc.name === frappe.session.user && attr_tuples.some(has_effectively_changed)) {
			frappe.msgprint(__("Refreshing..."));
			window.location.reload();
		}
	},
	setup_passkey_buttons: function (frm) {
		// Only show passkey buttons for current user (not Guest/Administrator)
		if (
			frappe.session.user !== frm.doc.name ||
			["Guest", "Administrator"].includes(frm.doc.name)
		) {
			return;
		}

		frappe.db
			.get_single_value("System Settings", "login_with_passkey")
			.then((isEnabled) => {
				if (!isEnabled) return;

				frm.add_custom_button(
					__("Register New"),
					() => start_passkey_registration(frm),
					__("Passkeys")
				);

				frm.add_custom_button(
					__("Manage / Revoke"),
					() => show_active_passkeys(frm),
					__("Passkeys")
				);
			})
			.catch((error) => {
				console.warn("Failed to check passkey settings:", error);
			});
	},

	setup_impersonation: function (frm) {
		if (
			frappe.session.user === "Administrator" &&
			frm.doc.name != "Administrator" &&
			!frm.is_new()
		) {
			frm.add_custom_button(__("Impersonate"), () => {
				if (frm.doc.restrict_ip) {
					frappe.msgprint({
						message:
							"There's IP restriction for this user, you can not impersonate as this user.",
						title: "IP restriction is enabled",
					});
					return;
				}
				frappe.prompt(
					[
						{
							fieldname: "reason",
							fieldtype: "Small Text",
							label: "Reason for impersonating",
							description: __("Note: This will be shared with user."),
							reqd: 1,
						},
					],
					(values) => {
						frappe
							.xcall("frappe.core.doctype.user.user.impersonate", {
								user: frm.doc.name,
								reason: values.reason,
							})
							.then(() => window.location.reload());
					},
					__("Impersonate as {0}", [frm.doc.name]),
					__("Confirm")
				);
			});
		}
	},
});

frappe.ui.form.on("User Email", {
	email_account(frm, cdt, cdn) {
		let child_row = locals[cdt][cdn];
		frappe.model.get_value(
			"Email Account",
			child_row.email_account,
			"auth_method",
			(value) => {
				child_row.used_oauth = value.auth_method === "OAuth";
				frm.refresh_field("user_emails", cdn, "used_oauth");
			}
		);
	},
});

frappe.ui.form.on("User Role Profile", {
	role_profiles_add: function (frm) {
		if (frm.doc.role_profiles.length > 0) {
			frm.roles_editor.disable = 1;
			frm.call("populate_role_profile_roles").then(() => {
				frm.roles_editor.show();
			});
			$(".deselect-all, .select-all").prop("disabled", true);
		}
	},
	role_profiles_remove: function (frm) {
		if (frm.doc.role_profiles.length == 0) {
			frm.roles_editor.disable = 0;
			frm.roles_editor.show();
			$(".deselect-all, .select-all").prop("disabled", false);
		}
	},
});

function has_access_to_edit_user() {
	return has_common(frappe.user_roles, get_roles_for_editing_user());
}

function get_roles_for_editing_user() {
	return (
		frappe
			.get_meta("User")
			.permissions.filter((perm) => perm.permlevel >= 1 && perm.write)
			.map((perm) => perm.role) || ["System Manager"]
	);
}

function show_api_key_dialog(api_key, api_secret) {
	const dialog = new frappe.ui.Dialog({
		title: __("API Keys"),
		fields: [
			{
				label: __("API Key"),
				fieldname: "api_key",
				fieldtype: "Code",
				read_only: 1,
				default: api_key,
			},
			{
				label: __("API Secret"),
				fieldname: "api_secret",
				fieldtype: "Code",
				read_only: 1,
				default: api_secret,
			},
		],
		size: "small",
		primary_action_label: __("Download"),
		primary_action: () => {
			frappe.tools.downloadify(
				[
					["api_key", "api_secret"],
					[api_key, api_secret],
				],
				"System Manager",
				"frappe_api_keys"
			);

			dialog.hide();
		},
		secondary_action_label: __("Copy token to clipboard"),
		secondary_action: () => {
			const token = `${api_key}:${api_secret}`;
			frappe.utils.copy_to_clipboard(token);
			dialog.hide();
		},
	});

	dialog.show();
	dialog.show_message(
		__("Store the API secret securely. It won't be displayed again."),
		"yellow",
		1
	);
}

async function start_passkey_registration(frm) {
	if (!navigator.credentials) {
		frappe.msgprint("Passkeys are not supported in this browser.");
		return;
	}

	try {
		const challengeResponse = await frappe.call({
			method: "frappe.integrations.passkey.register_challenge",
			args: { email: frm.doc.email, user_display_name: frm.doc.full_name },
		});

		const credential = await create_new_passkey(challengeResponse.message);

		const credentialResponse = {
			id: credential.id,
			rawId: frappe.utils.buffer_to_base64url(credential.rawId),
			response: {
				attestationObject: frappe.utils.buffer_to_base64url(
					credential.response.attestationObject
				),
				clientDataJSON: frappe.utils.buffer_to_base64url(
					credential.response.clientDataJSON
				),
			},
			type: credential.type,
			title: detect_device_label(),
		};

		await verify_passkey_with_server(frm, credentialResponse);
	} catch (error) {
		show_error_message(error);
	}
}

async function create_new_passkey(publicKeyOptions) {
	const credential = await navigator.credentials.create({
		publicKey: prepare_publickey_options(publicKeyOptions),
	});

	if (!credential) {
		throw new Error("User cancelled passkey creation");
	}

	return credential;
}

function prepare_publickey_options(options) {
	const prepared = { ...options };
	prepared.challenge = frappe.utils.base64url_to_uint8array(options.challenge);
	prepared.user.id = frappe.utils.base64url_to_uint8array(options.user.id);

	if (prepared.excludeCredentials) {
		prepared.excludeCredentials = prepared.excludeCredentials.map((credential) => ({
			...credential,
			id: frappe.utils.base64url_to_uint8array(credential.id),
		}));
	}
	return prepared;
}

function detect_device_label() {
	const userAgent = navigator.userAgent;
	const browserMatch = userAgent.match(/(opera|chrome|safari|firefox|msie|edg)\/?\s*([\d\.]+)/i);
	const browser = browserMatch?.[1] || "Unknown Browser";
	const platform = navigator.userAgentData?.platform || navigator.platform || "Unknown Device";
	return `${browser} - ${platform}`;
}

async function verify_passkey_with_server(frm, credentialResponse) {
	try {
		const response = await frappe.call({
			method: "frappe.integrations.passkey.register_verify",
			args: { email: frm.doc.email, credential: credentialResponse },
		});

		if (response.message.success) {
			return await prompt_passkey_label(frm, response.message.credential_id);
		}

		const errorMessage = response.message.error || "Passkey registration failed.";
		frappe.msgprint(errorMessage);
	} catch (error) {
		show_error_message(error);
	}
}

function prompt_passkey_label(frm, credentialId) {
	return new Promise((resolve, reject) => {
		frappe.prompt(
			[{ fieldname: "label", label: "Passkey Label", fieldtype: "Data" }],
			async (values) => {
				try {
					await frappe.call({
						method: "frappe.integrations.passkey.update_passkey_label",
						args: { credential_id: credentialId, label: values.label },
					});

					frappe.msgprint("Passkey registered successfully!");
					frm.reload_doc();
					resolve();
				} catch (error) {
					show_error_message(error);
					reject(error);
				}
			},
			__("Passkey registered. Add Label for Passkey"),
			__("Save")
		);
	});
}

function show_active_passkeys(frm) {
	frappe
		.call({
			method: "frappe.integrations.passkey.get_active_passkeys",
			args: { user: frm.doc.name },
		})
		.then((response) => {
			const passkeys = response.message || [];

			if (!passkeys.length) {
				frappe.msgprint("No active passkeys found.");
				return;
			}

			const dialog = new frappe.ui.Dialog({
				title: `Active Passkeys for ${frm.doc.full_name}`,
				fields: [
					{
						fieldname: "passkey_list",
						fieldtype: "HTML",
						options: generate_passkey_list_html(passkeys),
					},
				],
				primary_action_label: "Close",
				primary_action() {
					dialog.hide();
				},
			});

			dialog.show();

			dialog.$wrapper.on("click", ".btn-revoke-passkey", function () {
				const passkeyName = $(this).data("name");
				const passkeyTitle = $(this).data("title");

				dialog.hide();

				frappe.confirm(
					`Are you sure you want to revoke passkey: ${frappe.utils.escape_html(
						passkeyTitle
					)}?`,
					() => {
						frappe
							.call({
								method: "frappe.integrations.passkey.revoke_passkey",
								args: { name: passkeyName },
							})
							.then((revokeResponse) => {
								if (revokeResponse.message?.success) {
									frappe.msgprint(
										`Passkey "${frappe.utils.escape_html(
											passkeyTitle
										)}" revoked successfully.`
									);
									frm.reload_doc();
								} else {
									show_error_message({
										name: "Revoke Failed",
										message: revokeResponse.message?.error || "Unknown error",
									});
									dialog.show();
								}
							})
							.catch((error) => {
								show_error_message(error);
								dialog.show();
							});
					},
					() => {
						dialog.show();
					}
				);
			});
		})
		.catch((error) => {
			show_error_message(error);
		});
}

function generate_passkey_list_html(passkeys) {
	return passkeys
		.map((passkey) => {
			const title = frappe.utils.escape_html(passkey.title || "Untitled");
			const addedDate = passkey.creation
				? frappe.datetime.str_to_user(passkey.creation)
				: "N/A";
			const lastUsed =
				passkey.sign_count > 0 && passkey.last_used
					? frappe.datetime.comment_when(passkey.last_used)
					: "Never";

			return `
				<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:5px;">
					<div>
						<strong>${title}</strong><br>
						<small>Added on ${addedDate} | Last used ${lastUsed}</small>
					</div>
					<button class="btn btn-xs btn-danger btn-revoke-passkey"
						data-name="${frappe.utils.escape_html(passkey.name)}"
						data-title="${title}">
						Revoke
					</button>
				</div>`;
		})
		.join("");
}

function show_error_message(error) {
	if (!error) {
		frappe.msgprint("An unknown error occurred.");
		return;
	}

	let title = "Error";
	let message = "An error occurred";

	// Handle WebAuthn specific errors
	if (error.name === "NotAllowedError") {
		title = "Passkey Error";
		message = "User cancelled or passkey operation not allowed.";
	} else if (error.name === "InvalidStateError") {
		title = "Passkey Error";
		message = "Passkey already registered for this device.";
	} else if (error.name === "NotSupportedError") {
		title = "Passkey Error";
		message = "Passkeys are not supported on this device.";
	} else if (error.name === "SecurityError") {
		title = "Passkey Error";
		message = "Security error occurred during passkey operation.";
	} else {
		// Handle generic errors
		title = error.name || "Error";
		message = error.message || "An error occurred";
	}

	frappe.msgprint({
		title: title,
		message: message,
		indicator: "red",
	});
}
