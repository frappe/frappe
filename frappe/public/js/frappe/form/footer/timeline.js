// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.timeline');
frappe.separator_element = '<div>---</div>';

frappe.ui.form.Timeline = class Timeline {
	constructor(opts) {
		$.extend(this, opts);
		this.make();
	}

	make() {
		var me = this;
		this.wrapper = $(frappe.render_template("timeline",
			{doctype: me.frm.doctype, allow_events_in_timeline: me.frm.meta.allow_events_in_timeline})).appendTo(me.parent);

		this.list = this.wrapper.find(".timeline-items");

		this.comment_area = frappe.ui.form.make_control({
			parent: this.wrapper.find('.timeline-head'),
			df: {
				fieldtype: 'Comment',
				fieldname: 'comment',
				label: 'Comment'
			},
			mentions: this.get_names_for_mentions(),
			render_input: true,
			only_input: true,
			on_submit: (val) => {
				val && this.insert_comment("Comment", val, this.comment_area.button);
			}
		});

		this.setup_email_button();
		this.setup_interaction_button();

		this.list.on("click", ".toggle-blockquote", function() {
			$(this).parent().siblings("blockquote").toggleClass("hidden");
		});

		this.setup_comment_like();

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

							if (new_communications.length < 20) {
								me.more = false;
							}

						} else {
							me.more = false;
						}

						me.refresh();
					}
				}
			});
		});

	}

	setup_email_button() {
		var me = this;
		var selector = this.frm.doctype === "Communication"? ".btn-reply-email": ".btn-new-email";
		this.email_button = this.wrapper.find(selector)
			.on("click", function() {
				const $btn = $(this);
				let is_a_reply = true;
				if ($btn.is('.btn-new-email')) {
					is_a_reply = false;
				}

				var args = {
					doc: me.frm.doc,
					frm: me.frm,
					recipients: me.get_recipient(),
					is_a_reply
				}

				if(me.frm.doctype === "Communication") {
					$.extend(args, {
						txt: "",
						last_email: me.frm.doc,
						recipients: me.frm.doc.sender,
						subject: __("Re: {0}", [me.frm.doc.subject]),
					});
				} else {
					const comment_value = frappe.markdown(me.comment_area.get_value());
					$.extend(args, {
						txt: strip_html(comment_value) ? comment_value : ''
					});
				}
				new frappe.views.CommunicationComposer(args)
			});
	}

	setup_interaction_button() {
		var me = this;
		var selector = ".btn-new-interaction";
		this.activity_button = this.wrapper.find(selector)
			.on("click", function() {
				var args = {
					doc: me.frm.doc,
					frm: me.frm,
					recipients: me.get_recipient()
				}
				$.extend(args, {
					txt: frappe.markdown(me.comment_area.get_value())
				});
				new frappe.views.InteractionComposer(args);
			});
	}

	setup_editing_area() {
		this.$editing_area = $('<div class="timeline-editing-area">');

		this.editing_area = new frappe.ui.CommentArea({
			parent: this.$editing_area,
			mentions: this.get_names_for_mentions(),
			no_wrapper: true
		});

		this.editing_area.destroy();
	}

	refresh(scroll_to_end) {
		var me = this;
		this.last_type = "Comment";

		if(this.frm.doc.__islocal) {
			this.wrapper.toggle(false);
			return;
		}
		this.wrapper.toggle(true);
		this.list.empty();
		this.comment_area.set_value('');
		let communications = this.get_communications(true);
		var views = this.get_view_logs();

		var timeline = communications.concat(views);
		timeline
			.filter(a => a.content)
			.sort((b, c) => me.compare_dates(b, c))
			.forEach(d => {
				d.frm = me.frm;
				me.render_timeline_item(d);
			});



		// more btn
		if (this.more===undefined && timeline.length===20) {
			this.more = true;
		}

		if (this.more) {
			$('<div class="timeline-item">\
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
			creation: this.frm.doc.creation,
			frm: this.frm
		});

		this.wrapper.find(".is-email").prop("checked", this.last_type==="Email").change();

		this.frm.sidebar.refresh_comments();

		this.frm.trigger('timeline_refresh');
	}

	compare_dates(b, c) {
		let b_date = b.communication_date ? b.communication_date : b.creation;
		let c_date = c.communication_date ? c.communication_date : c.creation;
		let comparison = new Date(b_date) > new Date(c_date) ? -1 : 1;
		return comparison;
	}

	make_editing_area(container) {
		return frappe.ui.form.make_control({
			parent: container,
			df: {
				fieldtype: 'Comment',
				fieldname: 'comment',
				label: 'Comment'
			},
			mentions: this.get_names_for_mentions(),
			render_input: true,
			only_input: true,
			no_wrapper: true
		});
	}

	render_timeline_item(c) {
		var me = this;
		this.prepare_timeline_item(c);
		var $timeline_item = $(frappe.render_template("timeline_item", {data:c, frm:this.frm}))
			.appendTo(me.list)
			.on("click", ".delete-comment", function() {
				var name = $timeline_item.data('name');
				me.delete_comment(name);
				return false;
			})
			.on('click', '.edit-comment', function(e) {
				e.preventDefault();
				var name = $timeline_item.data('name');

				if($timeline_item.hasClass('is-editing')) {
					me.current_editing_area.submit();
				} else {
					const $edit_btn = $(this);
					const $timeline_content = $timeline_item.find('.timeline-item-content');
					const $timeline_edit = $timeline_item.find('.timeline-item-edit');
					const content = $timeline_content.html();

					// update state
					$edit_btn
						.text(__("Save"))
						.find('i')
						.removeClass('octicon-pencil')
						.addClass('octicon-check');
					$timeline_content.hide();
					$timeline_item.addClass('is-editing');

					// initialize editing area
					me.current_editing_area = me.make_editing_area($timeline_edit);
					me.current_editing_area.set_value(content);

					// submit handler
					me.current_editing_area.on_submit = (value) => {
						$timeline_edit.empty();
						$timeline_content.show();

						// set content to new val so that on save and refresh the new content is shown
						c.content = value;
						frappe.timeline.update_communication(c);
						me.update_comment(name, value);
						// all changes to the timeline_item for editing are reset after calling refresh
						me.refresh();
					};
				}

				return false;
			});


		if(c.communication_type=="Communication" && c.communication_medium==="Email") {
			this.last_type = c.communication_medium;
			this.add_reply_btn_event($timeline_item, c);
		}

	}

	add_reply_btn_event($timeline_item, c) {
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
				title: __('Reply'),
				frm: me.frm,
				last_email: last_email,
				is_a_reply: true
			});
		});
	}

	prepare_timeline_item(c) {
		if(!c.sender) c.sender = c.owner;

		if(c.sender && c.sender.indexOf("<")!==-1) {
			c.sender = c.sender.split("<")[1].split(">")[0];
		}

		c.user_info = frappe.user_info(c.sender);

		c["delete"] = "";
		c["edit"] = "";
		if(c.communication_type=="Comment" && (c.comment_type || "Comment") === "Comment") {
			if(frappe.model.can_delete("Communication")) {
				c["delete"] = '<a class="close delete-comment" title="Delete"  href="#"><i class="octicon octicon-x"></i></a>';
			}

			if(frappe.user.name == c.sender || (frappe.user.name == 'Administrator')) {
				c["edit"] = '<a class="edit-comment text-muted" title="Edit" href="#">Edit</a>';
			}
		}
		let communication_date = c.communication_date || c.creation;
		c.comment_on_small = comment_when(communication_date, true);
		c.comment_on = comment_when(communication_date);
		c.futur_date = communication_date > frappe.datetime.now_datetime() ? true : false;
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
				c.content = c.content.split(frappe.separator_element)[0];
				c.content = frappe.utils.strip_original_content(c.content);

				c.original_content = c.content;
				c.content = frappe.utils.toggle_blockquote(c.content);
			} else if (c.communication_type==="Feedback") {
				c.content = frappe.utils.strip_original_content(c.content);

				c.original_content = c.content;
				c.content = frappe.utils.toggle_blockquote(c.content);
			}
			if(!frappe.utils.is_html(c.content)) {
				c.content_html = frappe.markdown(__(c.content));
			} else {
				c.content_html = c.content;
				c.content_html = frappe.utils.strip_whitespace(c.content_html);
				c.content_html = c.content_html.replace(/&lt;/g,"<").replace(/&gt;/g,">");
			}

			// bold @mentions
			if(c.comment_type==="Comment" &&
				// avoid adding <b> tag a 2nd time
				!c.content_html.match(/(^|\W)<b>(@[^\s]+)<\/b>/)
			) {
				/*
					Replace the email ids by only displaying the string which
					occurs before the second `@` to enhance the mentions.
					Eg.
					@abc@a-example.com will be converted to
					@abc with the below line of code.
				*/

				c.content_html = c.content_html.replace(/(<[a][^>]*>)/g, "");
				// bold the @mentions
				c.content_html = c.content_html.replace(/(@[^\s@]*)@[^\s@|<]*/g, "<b>$1</b>");
			}

			if (this.is_communication_or_comment(c)) {
				c.user_content = true;
				if (!$.isArray(c._liked_by)) {
					c._liked_by = JSON.parse(c._liked_by || "[]");
				}

				c.liked_by_user = c._liked_by.indexOf(frappe.session.user)!==-1;
			}
		}

		// basic level of XSS protection
		c.content_html = frappe.dom.remove_script_and_style(c.content_html);

		// subject
		c.show_subject = false;
		if(c.subject && c.communication_type==="Communication") {
			if(this.frm.doc.subject && !this.frm.doc.subject.includes(c.subject)) {
				c.show_subject = true;
			} else if(this.frm.meta.title_field && this.frm.doc[this.frm.meta.title_field]
				&& !!this.frm.doc[this.frm.meta.title_field].includes(c.subject)) {
				c.show_subject = true;
			} else if(!this.frm.doc.name.includes(c.subject)) {
				c.show_subject = true;
			}
		}
	}

	is_communication_or_comment(c) {
		return c.communication_type==="Communication"
		|| c.communication_type==="Feedback"
		|| (c.communication_type==="Comment" && (c.comment_type==="Comment"||c.comment_type==="Relinked"));
	}

	set_icon_and_color(c) {
		if(c.communication_type == "Feedback"){
			c.icon = "octicon octicon-comment-discussion"
			c.rating_icons = frappe.render_template("rating_icons", {rating: c.rating, show_label: true})
			c.color = "#f39c12"
		} else {
			c.icon = {
				"Email": "octicon octicon-mail",
				"Chat": "octicon octicon-comment-discussion",
				"Phone": "octicon octicon-device-mobile",
				"SMS": "octicon octicon-comment",
				"Event": "fa fa-calendar",
				"Meeting": "octicon octicon-briefcase",
				"ToDo": "fa fa-check",
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
				"Relinked": "octicon octicon-check",
				"Reply": "octicon octicon-mail-reply"
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
				"Relinked": "#16a085",
				"Reply": "#8d99a6"
			}[c.comment_type || c.communication_medium];

			c.icon_fg = {
				"Attachment Removed": "#333",
			}[c.comment_type || c.communication_medium]

		}
		if(!c.icon_fg)
			c.icon_fg = "#fff";
	}

	get_communications(with_versions) {
		var docinfo = this.frm.get_docinfo(),
			me = this,
			out = [].concat(docinfo.communications);
		if(with_versions) {
			this.build_version_comments(docinfo, out);
		}

		return out;
	}

	get_view_logs(){
		var docinfo = this.frm.get_docinfo(),
			me = this,
			out = [];
		for (let c of docinfo.views){
			c.content = `<a href="#Form/View Log/${c.name}"> ${__("viewed")}</a>`;
			c.comment_type = "Info";
			out.push(c);
		};
		return out;
	}

	build_version_comments(docinfo, out) {
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

						if(df && !df.hidden) {
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
						var df = me.frm.fields_dict[row[0]] &&
							frappe.meta.get_docfield(me.frm.fields_dict[row[0]].grid.doctype,
								p[0], me.frm.docname);

						if(df && !df.hidden) {
							var field_display_status = frappe.perm.get_field_display_status(df,
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
						if(df && !df.hidden) {
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
	}

	get_version_comment(version, text, comment_type) {
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
	}

	insert_comment(comment_type, comment, btn) {
		var me = this;
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
					sender: frappe.session.user
				}
			},
			btn: btn,
			callback: function(r) {
				if(!r.exc) {
					me.comment_area.set_value('');
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
			}
		});

	}

	delete_comment(name) {
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
	}

	/**
	 * Update comment
	 *
	 * @param {string} name
	 * @param {string} content
	 *
	 * @returns {boolean}
	 */
	update_comment(name, content){
		return frappe.call({
			method: 'frappe.desk.form.utils.update_comment',
			args: { name, content },
			callback: function(r) {
				if(!r.exc) {
					frappe.utils.play_sound('click');
				}
			}
		});
	}

	get_recipient() {
		if (this.frm.email_field) {
			return this.frm.doc[this.frm.email_field];
		} else {
			return this.frm.doc.email_id || this.frm.doc.email || "";
		}
	}

	get_last_email(from_recipient) {
		var last_email = null,
			communications = this.frm.get_docinfo().communications,
			email = this.get_recipient();

		$.each(communications && communications.sort(function(a, b) { return a.creation > b.creation ? -1 : 1 }), function(i, c) {
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
	}

	get_names_for_mentions() {
		var valid_users = Object.keys(frappe.boot.user_info)
			.filter(user => !["Administrator", "Guest"].includes(user));
		valid_users = valid_users
			.filter(user => frappe.boot.user_info[user].allowed_in_mentions==1);
		return valid_users.map(user => frappe.boot.user_info[user].name);
	}

	setup_comment_like() {
		this.wrapper.on("click", ".comment-likes .octicon-heart", frappe.ui.click_toggle_like);

		frappe.ui.setup_like_popover(this.wrapper, ".comment-likes");
	}
};

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