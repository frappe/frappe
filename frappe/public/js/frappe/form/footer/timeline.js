// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.timeline');

frappe.ui.form.Timeline = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
	},
	make: function() {
		var me = this;
		this.wrapper = $(frappe.render_template("timeline",
			{})).appendTo(this.parent);

		this.list = this.wrapper.find(".timeline-items");
		this.input = this.wrapper.find(".form-control");

		this.comment_button = this.wrapper.find(".btn-comment")
			.on("click", function() {
				me.add_comment(this);
			});

		this.input.keydown("meta+return ctrl+return", function(e) {
			me.comment_button.trigger("click");
		}).keyup(function(e) {
			if(me.input.val()) {
				if(me.comment_button.hasClass('btn-default')) {
					me.comment_button.removeClass('btn-default').addClass('btn-primary');
				}
			} else {
				if(me.comment_button.hasClass('btn-primary')) {
					me.comment_button.removeClass('btn-primary').addClass('btn-default');
				}
			}
		});

		this.email_button = this.wrapper.find(".btn-new-email")
			.on("click", function() {
				new frappe.views.CommunicationComposer({
					doc: me.frm.doc,
					txt: frappe.markdown(me.input.val()),
					frm: me.frm,
					recipients: me.get_recipient()
				})
			});

		this.list.on("click", ".toggle-blockquote", function() {
			$(this).parent().siblings("blockquote").toggleClass("hidden");
		});

		this.setup_comment_like();

		this.setup_mentions();

		this.list.on("click", ".btn-more", function() {
			var communications = me.get_communications();
			frappe.call({
				btn: this,
				method: "frappe.desk.form.load.get_communications",
				args: {
					doctype: me.frm.doc.doctype,
					name: me.frm.doc.name,
					start: communications.length
				},
				callback: function(r) {
					if (!r.exc) {
						if (r.message) {
							var new_communications = r.message;
							var communications = me.get_communications().concat(new_communications);
							frappe.model.set_docinfo(me.frm.doc.doctype, me.frm.doc.name, "communications", communications);

						} else {
							me.more = false;
						}

						me.refresh();
					}
				}
			});
		});

	},

	refresh: function(scroll_to_end) {
		var me = this;

		this.last_type = "Comment";

		if(this.frm.doc.__islocal) {
			this.wrapper.toggle(false);
			return;
		}
		this.wrapper.toggle(true);
		this.list.empty();

		var communications = this.get_communications(true);

		$.each(communications.sort(function(a, b) { return a.creation > b.creation ? -1 : 1 }),
			function(i, c) {
				if(c.content) {
					c.frm = me.frm;
					me.render_timeline_item(c);
				}
		});

		// more btn
		if (this.more===undefined && communications.length===20) {
			this.more = true;
		}

		if (this.more) {
			var $more = $('<div class="timeline-item">\
				<button class="btn btn-default btn-xs btn-more">More</button>\
			</div>').appendTo(me.list);
		}

		// created
		me.render_timeline_item({
			content: __("created"),
			comment_type: "Created",
			communication_type: "Comment",
			sender: this.frm.doc.owner,
			communication_date: this.frm.doc.creation,
			frm: this.frm
		});

		this.wrapper.find(".is-email").prop("checked", this.last_type==="Email").change();

		this.frm.sidebar.refresh_comments();

		this.frm.trigger('timeline_refresh');
	},

	render_timeline_item: function(c) {
		var me = this;
		this.prepare_timeline_item(c);

		var $timeline_item = $(frappe.render_template("timeline_item", {data:c, frm:this.frm}))
			.appendTo(me.list)
			.on("click", ".close", function() {
				var name = $timeline_item.data('name');
				me.delete_comment(name);

				return false;
			})
			.on('click', '.edit', function() {
				var is_editing = 'is-editing';
				var content = $timeline_item.find('.timeline-item-content');
				var name = $timeline_item.data('name');

				var update_comment = function() {
					var val = content.find('textarea').val();
					// set content to new val so that on save and refresh the new content is shown
					c.content = val;

					frappe.timeline.update_communication(c);
					me.update_comment(name, val);

					// all changes to the timeline_item for editing are reset after calling refresh
					me.refresh();
				}

				if(content.hasClass(is_editing)) {
					update_comment();
				} else {
					var $edit_btn = $(this);
					var editing_textarea = me.input.clone()
						.removeClass('comment-input');

					editing_textarea.keydown("meta+return ctrl+return", function(e) {
						update_comment();
					});

					frappe.db.get_value('Communication', {name: name}, 'content', function(r) {
						$edit_btn.find('i').removeClass('octicon-pencil').addClass('octicon-check');
						editing_textarea.val(r.content);
						content.html(editing_textarea);
						content.addClass(is_editing);
					});
				}

				return false;
			});


		if(c.communication_type=="Communication" && c.communication_medium==="Email") {
			this.last_type = c.communication_medium;
			this.add_reply_btn_event($timeline_item, c);
		}

	},

	add_reply_btn_event: function($timeline_item, c) {
		var me = this;
		$timeline_item.find(".reply-link").on("click", function() {
			var name = $(this).attr("data-name");
			var last_email = null;

			// find the email tor reply to
			me.get_communications().forEach(function(c) {
				if(c.name==name) {
					last_email = c;
					return false;
				}
			});

			// make the composer
			new frappe.views.CommunicationComposer({
				doc: me.frm.doc,
				txt: "",
				frm: me.frm,
				last_email: last_email
			});
		});
	},

	prepare_timeline_item: function(c) {
		if(!c.sender) c.sender = this.frm.doc.owner;

		if(c.sender && c.sender.indexOf("<")!==-1) {
			c.sender = c.sender.split("<")[1].split(">")[0];
		}

		if(c.sender) {
			c.user_info = frappe.user_info(c.sender);
		} else {
			c.user_info = frappe.user_info(c.owner);
		}

		c["delete"] = "";
		c["edit"] = "";
		if(c.communication_type=="Comment" && (c.comment_type || "Comment") === "Comment") {
			if(frappe.model.can_delete("Communication")) {
				c["delete"] = '<a class="close" href="#"><i class="octicon octicon-trashcan"></i></a>';
			}

			if(frappe.user.name == c.sender || (frappe.user.name == 'Administrator')) {
				c["edit"] = '<a class="edit" href="#"><i class="octicon octicon-pencil"></i></a>';
			}
		}

		c.comment_on = comment_when(c.creation);
		if(!c.fullname) {
			c.fullname = c.sender_full_name || frappe.user.full_name(c.sender);
		}

		if(c.attachments && typeof c.attachments==="string")
			c.attachments = JSON.parse(c.attachments);

		if(c.communication_type=="Comment" && !c.comment_type) {
			c.comment_type = "Comment";
		}

		this.set_icon_and_color(c);

		// label view
		if(c.comment_type==="Workflow" || c.comment_type==="Label") {
			c.comment_html = repl('<span class="label label-%(style)s">%(text)s</span>', {
				style: frappe.utils.guess_style(c.content),
				text: __(c.content)
			});
		} else {
			if(c.communication_type=="Communication" && c.communication_medium=="Email") {
				c.content = c.content.split("<!-- original-reply -->")[0];
				c.content = frappe.utils.strip_original_content(c.content);

				c.original_content = c.content;
				c.content = frappe.utils.toggle_blockquote(c.content);
			}

			if(!frappe.utils.is_html(c.content)) {
				c.content_html = frappe.markdown(__(c.content));
			} else {
				c.content_html = c.content;
				c.content_html = frappe.utils.strip_whitespace(c.content_html);
				c.content_html = c.content_html.replace(/&lt;/g,"<").replace(/&gt;/g,">")
			}

			// bold @mentions
			if(c.comment_type==="Comment") {
				c.content_html = c.content_html.replace(/(^|\W)(@\w+)/g, "$1<b>$2</b>");
			}

			if (this.is_communication_or_comment(c)) {
				c.user_content = true;
				if (!$.isArray(c._liked_by)) {
					c._liked_by = JSON.parse(c._liked_by || "[]");
				}

				c.liked_by_user = c._liked_by.indexOf(user)!==-1;
			}
		}

		// basic level of XSS protection
		c.content_html = frappe.dom.remove_script_and_style(c.content_html);

		// subject
		c.show_subject = false;
		if(c.subject
			&& c.communication_type==="Communication"
			&& !frappe._in(this.frm.doc.subject, c.subject)
			&& !frappe._in(this.frm.doc.name, c.subject)
			&& !frappe._in(this.frm.doc[this.frm.meta.title_field || "name"], c.subject)) {
			c.show_subject = true;
		}
	},

	is_communication_or_comment: function(c) {
		return c.communication_type==="Communication" || (c.communication_type==="Comment" && (c.comment_type==="Comment"||c.comment_type==="Relinked"));
	},

	set_icon_and_color: function(c) {
		c.icon = {
			"Email": "octicon octicon-mail",
			"Chat": "octicon octicon-comment-discussion",
			"Phone": "octicon octicon-device-mobile",
			"SMS": "octicon octicon-comment",
			"Created": "octicon octicon-plus",
			"Submitted": "octicon octicon-lock",
			"Cancelled": "octicon octicon-x",
			"Assigned": "octicon octicon-person",
			"Assignment Completed": "octicon octicon-check",
			"Comment": "octicon octicon-comment-discussion",
			"Workflow": "octicon octicon-git-branch",
			"Label": "octicon octicon-tag",
			"Attachment": "octicon octicon-cloud-upload",
			"Attachment Removed": "octicon octicon-trashcan",
			"Shared": "octicon octicon-eye",
			"Unshared": "octicon octicon-circle-slash",
			"Like": "octicon octicon-heart",
			"Edit": "octicon octicon-pencil",
			"Relinked": "octicon octicon-check"
		}[c.comment_type || c.communication_medium]

		c.color = {
			"Email": "#3498db",
			"Chat": "#3498db",
			"Phone": "#3498db",
			"SMS": "#3498db",
			"Created": "#1abc9c",
			"Submitted": "#1abc9c",
			"Cancelled": "#c0392b",
			"Assigned": "#f39c12",
			"Assignment Completed": "#16a085",
			"Comment": "#f39c12",
			"Workflow": "#2c3e50",
			"Label": "#2c3e50",
			"Attachment": "#7f8c8d",
			"Attachment Removed": "#eee",
			"Relinked": "#16a085"
		}[c.comment_type || c.communication_medium];

		c.icon_fg = {
			"Attachment Removed": "#333",
		}[c.comment_type || c.communication_medium]

		if(!c.icon_fg)
			c.icon_fg = "#fff";

	},
	get_communications: function(with_versions) {
		var docinfo = this.frm.get_docinfo(),
			me = this,
			out = [].concat(docinfo.communications);

		if(with_versions) {
			this.build_version_comments(docinfo, out);
		}
		return out;
	},
	build_version_comments: function(docinfo, out) {
		var me = this;

		docinfo.versions.forEach(function(version) {
			if(!version.data) return;
			var data = JSON.parse(version.data);

			// comment
			if(data.comment) {
				out.push(me.get_version_comment(version, data.comment, data.comment_type));
				return;
			}

			// value changed in parent
			if(data.changed && data.changed.length) {
				var parts = [];
				data.changed.every(function(p) {
					if(p[0]==='docstatus') {
						if(p[2]==1) {
							out.push(me.get_version_comment(version, __('submitted this document')));
						} else if (p[2]==2) {
							out.push(me.get_version_comment(version, __('cancelled this document')));
						}
					} else {
						var df = frappe.meta.get_docfield(me.frm.doctype, p[0], me.frm.docname);
						if(!df.hidden) {
							var field_display_status = frappe.perm.get_field_display_status(df, null,
								me.frm.perm);
							if(field_display_status === 'Read' || field_display_status === 'Write') {
								parts.push(__('{0} from {1} to {2}', [
									__(df.label),
									(frappe.ellipsis(p[1], 40) || '""').bold(),
									(frappe.ellipsis(p[2], 40) || '""').bold()
								]));
							}
						}
					}
					return parts.length < 3;
				});
				if(parts.length) {
					out.push(me.get_version_comment(version, __("changed value of {0}", [parts.join(', ')])));
				}
			}

			// value changed in table field
			if(data.row_changed && data.row_changed.length) {
				var parts = [], count = 0;
				data.row_changed.every(function(row) {
					row[3].every(function(p) {
						var df = frappe.meta.get_docfield(me.frm.fields_dict[row[0]].grid.doctype,
							p[0], me.frm.docname);

						if(!df.hidden) {
							field_display_status = frappe.perm.get_field_display_status(df,
								null, me.frm.perm);

							if(field_display_status === 'Read' || field_display_status === 'Write') {
								parts.push(__('{0} from {1} to {2} in row #{3}', [
									frappe.meta.get_label(me.frm.fields_dict[row[0]].grid.doctype,
										p[0]),
									(frappe.ellipsis(p[1], 40) || '""').bold(),
									(frappe.ellipsis(p[2], 40) || '""').bold(),
									row[1]
								]));
							}
						}
						return parts.length < 3;
					});
					return parts.length < 3;
				});
				if(parts.length) {
					out.push(me.get_version_comment(version, __("changed values for {0}",
						[parts.join(', ')])));
				}
			}

			// rows added / removed
			// __('added'), __('removed') # for translation, don't remove
			['added', 'removed'].forEach(function(key) {
				if(data[key] && data[key].length) {
					parts = (data[key] || []).map(function(p) {
						var df = frappe.meta.get_docfield(me.frm.doctype, p[0], me.frm.docname);
						if(!df.hidden) {
							var field_display_status = frappe.perm.get_field_display_status(df, null,
								me.frm.perm);

							if(field_display_status === 'Read' || field_display_status === 'Write') {
								return frappe.meta.get_label(me.frm.doctype, p[0])
							}
						}
					});
					parts = parts.filter(function(p) { return p; });
					if(parts.length) {
						out.push(me.get_version_comment(version, __("{0} rows for {1}",
							[__(key), parts.join(', ')])));
					}
				}
			});
		});
	},
	get_version_comment: function(version, text, comment_type) {
		if(!comment_type) {
			text = '<a href="#Form/Version/'+version.name+'">' + text + '</a>';
		}
		return {
			comment_type: comment_type || 'Edit',
			creation: version.creation,
			owner: version.owner,
			version_name: version.name,
			sender: version.owner,
			comment_by: version.owner,
			content: text
		};
	},

	add_comment: function(btn) {
		var txt = this.input.val();

		if(txt) {
			this.insert_comment("Comment", txt, btn, this.input);
		}
	},
	insert_comment: function(comment_type, comment, btn, input) {
		var me = this;
		if(input) input.prop('disabled', true);
		return frappe.call({
			method: "frappe.desk.form.utils.add_comment",
			args: {
				doc:{
					doctype: "Communication",
					communication_type: "Comment",
					comment_type: comment_type || "Comment",
					reference_doctype: this.frm.doctype,
					reference_name: this.frm.docname,
					content: comment,
					sender: user
				}
			},
			btn: btn,
			callback: function(r) {
				if(!r.exc) {
					me.input.val("");

					frappe.utils.play_sound("click");

					var comment = r.message;
					var comments = me.get_communications();
					var comment_exists = false;
					for (var i=0, l=comments.length; i<l; i++) {
						if (comments[i].name==comment.name) {
							comment_exists = true;
							break;
						}
					}
					if (comment_exists) {
						return;
					}

					me.frm.get_docinfo().communications = comments.concat([r.message]);
					me.refresh(true);
				}
			},
			always: function() {
				if(input) input.prop('disabled', false);
			}
		});

	},

	delete_comment: function(name) {
		var me = this;

		frappe.confirm(__('Delete comment?'), function() {
			return frappe.call({
				method: "frappe.client.delete",
				args: {
					doctype: "Communication",
					name: name
				},
				callback: function(r) {
					if(!r.exc) {
						frappe.utils.play_sound("delete");

						me.frm.get_docinfo().communications =
							$.map(me.frm.get_docinfo().communications,
								function(v) {
									if(v.name==name) return null;
									else return v;
								}
							);
						me.refresh(true);
					}
				}
			});
		});
	},

	/**
	 * Update comment
	 *
	 * @param {string} name
	 * @param {string} content
	 *
	 * @returns {boolean}
	 */
	update_comment: function(name, content)
	{
		// TODO: is there a frappe.client.update function?
		return frappe.call({
			method: 'frappe.client.set_value',
			args: {
				doctype: 'Communication',
				name: name,
				fieldname: 'content',
				value: content,
			}, callback: function(r) {
				frappe.utils.play_sound('click');
			}
		});
	},

	get_recipient: function() {
		if(this.frm.email_field) {
			return this.frm.doc[this.frm.email_field];
		} else {
			return this.frm.doc.email_id || this.frm.doc.email || "";
		}
	},

	get_last_email: function(from_recipient) {
		var last_email = null,
			communications = this.frm.get_docinfo().communications,
			email = this.get_recipient();

		$.each(communications.sort(function(a, b) { return a.creation > b.creation ? -1 : 1 }), function(i, c) {
			if(c.communication_type=='Communication' && c.communication_medium=="Email") {
				if(from_recipient) {
					if(c.sender.indexOf(email)!==-1) {
						last_email = c;
						return false;
					}
				} else {
					last_email = c;
					return false;
				}
			}
		});

		return last_email;
	},

	setup_mentions: function() {
		this.setup_awesomplete_for_mentions();
	},

	setup_awesomplete_for_mentions: function() {
		var me = this;
		var username_user_map = {};
		for (var name in frappe.boot.user_info) {
			if(name !== "Administrator" && name !== "Guest") {
				var _user = frappe.boot.user_info[name];
				username_user_map[_user.username] = _user;
			}
		}
		var source = Object.keys(username_user_map);

		this.awesomplete = new Awesomplete(this.input.get(0), {
			minChars: 0,
			maxItems: 99,
			autoFirst: true,
			list: source,
			filter: function(text, input) {
				if(input.indexOf("@") === -1) return false;
				return Awesomplete.FILTER_STARTSWITH(text, input.match(/[^@]*$/)[0]);
			},
			replace: function(text) {
				var before = this.input.value.match(/^.*@\s*|/)[0];
				this.input.value = before + text + " ";
			}
		});
	},

	setup_comment_like: function() {
		this.wrapper.on("click", ".comment-likes .octicon-heart", frappe.ui.click_toggle_like);

		frappe.ui.setup_like_popover(this.wrapper, ".comment-likes");
	}
});

$.extend(frappe.timeline, {
	new_communication: function(communication) {
		var docinfo = frappe.model.get_docinfo(communication.reference_doctype, communication.reference_name);
		if (docinfo && docinfo.communications) {
			var communications = docinfo.communications;
			var communication_exists = false;
			for (var i=0, l=communications.length; i<l; i++) {
				if (communications[i].name==communication.name) {
					communication_exists = true;
					break;
				}
			}

			if (!communication_exists) {
				docinfo.communications = communications.concat([communication]);
			}
		}

		if (cur_frm.doctype === communication.reference_doctype && cur_frm.docname === communication.reference_name) {
			cur_frm.timeline && cur_frm.timeline.refresh();
		}
	},

	delete_communication: function(communication) {
		var docinfo = frappe.model.get_docinfo(communication.reference_doctype, communication.reference_name);
		var index = frappe.timeline.index_of_communication(communication, docinfo);
		if (index !== -1) {
			// remove it from communications list
			docinfo.communications.splice(index, 1);
		}

		if (cur_frm.doctype === communication.reference_doctype && cur_frm.docname === communication.reference_name) {
			cur_frm.timeline && cur_frm.timeline.refresh();
		}
	},

	update_communication: function(communication) {
		var docinfo = frappe.model.get_docinfo(communication.reference_doctype, communication.reference_name);
		var index = frappe.timeline.index_of_communication(communication, docinfo);

		if (index !== -1) {
			// update
			$.extend(docinfo.communications[index], communication);
		}

		if (cur_frm.doctype === communication.reference_doctype && cur_frm.docname === communication.reference_name) {
			cur_frm.timeline && cur_frm.timeline.refresh();
		}
	},

	index_of_communication: function(communication, docinfo) {
		var index = -1;

		if (docinfo && docinfo.communications) {
			var communications = docinfo.communications;

			for (var i=0, l=communications.length; i<l; i++) {
				if (communications[i].name==communication.name) {
					index = i;
					break;
				}
			}
		}

		return index;
	}
})
