// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

wn.provide("website");
$.extend(website, {
	toggle_permitted: function() {
		if(website.access) {
			// hide certain views
			$('li[data-view="add"]').toggleClass("hide", !website.access.write);
			$('li[data-view="settings"]').toggleClass("hide", !website.access.admin);
			$('li[data-view="edit"]').toggleClass("hide", website.view!=="edit");
		
			// show message
			$(".post-list-help").html(!website.access.write ? "You do not have permission to post" : "");
		}
	},
	setup_pagination: function($btn, opts) {
		$btn.removeClass("hide");
	
		$btn.on("click", function() {
			wn.call($.extend({
				btn: $btn,
				type: "GET",
				callback: function(data) {
					if(opts.prepend) {
						opts.$wrapper.prepend(data.message);
					} else {
						opts.$wrapper.append(data.message);
					}
				
					$btn.toggleClass("hide", !(data.message && data.message.length===opts.args.limit_length));
				}
			}, opts))
		});
	},
	bind_add_post: function() {
		$(".btn-post-add").on("click", website.add_post);

		$pic_input = $(".control-post-add-picture").on("change", website.add_picture);
		$(".btn-post-add-picture").on("click", function() { 
			$pic_input.click();
		});
	},
	add_post: function() {
		if(website.post) {
			wn.msgprint("Post already exists. Cannot add again!");
			return;
		}
		
		website._update_post(this, "webnotes.website.doctype.post.post.add_post");
	},
	bind_save_post: function() {
		$(".btn-post-add").addClass("hide");
		$(".btn-post-save").removeClass("hide").on("click", website.save_post);
		$(".post-picture").toggleClass("hide", !$(".post-picture").attr("src"));
	},
	save_post: function() {
		if(!website.post) {
			wn.msgprint("Post does not exist. Please add post!");
			return;
		}
	
		website._update_post(this, "webnotes.website.doctype.post.post.save_post");
	},
	_update_post: function(btn, cmd) {
		var values = website.get_editor_values();
		if(!values) {
			return;
		}
		
		wn.call({
			btn: btn,
			type: "POST",
			args: $.extend({
				cmd: cmd,
				group: website.group,
				post: website.post || undefined
			}, values),
			callback: function(data) {
				var url = window.location.pathname + "?view=post&name=" + data.message;
				window.location.href = url;
				
				// if(history.pushState) {
				// 	app.get_content(url);
				// } else {
				// 	window.location.href = url;
				// }
			}
		});
	},
	get_editor_values: function() {
		var values = {};
		$.each($('.post-editor [data-fieldname]'), function(i, ele) {
			var $ele = $(ele);
			values[$ele.attr("data-fieldname")] = $ele.val();
		});
	
		values.parent_post = $(".post-editor").attr("data-parent-post");
		values.picture_name = $(".control-post-add-picture").val() || null;

		var dataurl = $(".post-picture img").attr("src");
		values.picture = dataurl ? dataurl.split(",")[1] : ""
	
		// validations
		if(!values.parent_post && !values.title) {
			wn.msgprint("Please enter title!");
			return;
		} else if(!values.content) {
			wn.msgprint("Please enter some text!");
			return;
		} else if($('.post-editor [data-fieldname="event_datetime"]').length && !values.event_datetime) {
			wn.msgprint("Please enter Event's Date and Time!");
			return;
		}
	
		// post process
		// convert links in content
		values.content = website.process_external_links(values.content);
	
		return values;
	},
	process_external_links: function(content) {
		return content.replace(/([^\s]*)(http|https|ftp):\/\/[^\s\[\]\(\)]+/g, function(match, p1) {
			// mimicing look behind! should not have anything in p1
			// replace(/match/g)
			// replace(/(p1)(p2)/g)
			// so, when there is a character before http://, it shouldn't be replaced!
			if(p1) return match;
		
			return "["+match+"]("+match+")";
		});
	},
	add_picture: function() {
		if (this.type === 'file' && this.files && this.files.length > 0) {
			$.each(this.files, function (idx, fileobj) {
				if (/^image\//.test(fileobj.type)) {
					$.canvasResize(fileobj, {
						width: 500,
						height: 0,
						crop: false,
						quality: 80,
						callback: function(data, width, height) {
							$(".post-picture").removeClass("hide").find("img").attr("src", data);
						}
					});
				}
			});
		}
		return false;
	},
	setup_tasks_editor: function() {
		// assign events
		var $post_editor = $(".post-editor");
		var $control_assign = $post_editor.find('.control-assign');
	
		var bind_close = function() {
			var close = $post_editor.find("a.close")
			if(close.length) {
				close.on("click", function() {
					// clear assignment
					$post_editor.find(".assigned-to").addClass("hide");
					$post_editor.find(".assigned-profile").html("");
					$post_editor.find('[data-fieldname="assigned_to"]').val(null);
					$control_assign.val(null);
				});
			}
		}
	
		if($control_assign.length) {
			website.setup_autosuggest({
				$control: $control_assign,
				select: function(value, item) {
					var $assigned_to = $post_editor.find(".assigned-to").removeClass("hide");
					$assigned_to.find(".assigned-profile").html(item.profile_html);
					$post_editor.find('[data-fieldname="assigned_to"]').val(value);
					bind_close();
				},
				method: "webnotes.website.doctype.post.post.suggest_user"
			});
			bind_close();
		}
	},
	setup_event_editor: function() {
		var $post_editor = $(".post-editor");
		var $control_event = $post_editor.find('.control-event').empty();
		var $event_field = $post_editor.find('[data-fieldname="event_datetime"]');

		var set_event = function($control) {
			var datetime = website.datetimepicker.obj_to_str($control_event.datepicker("getDate"));
			if($event_field.val() !== datetime) {
				$event_field.val(datetime);
			}
		};

		website.setup_datepicker({
			$control: $control_event,
			onClose: function() { set_event($control_event) }
		});

		if($event_field.val()) {
			$control_event.val(website.datetimepicker.format_datetime($event_field.val()));
		}
	},
	format_event_timestamps: function() {
		var get_day = function(num) {
			return ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday",
				"Friday", "Saturday"][num];
		}
		
		var get_month = function(num) {
			return ["January", "February", "March", "April", "May", "June",
				"July", "August", "September", "October", "November", "December"][num-1];
		}
		
		var format = function(datetime) {
			if(!datetime) return "";
			
			var date = datetime.split(" ")[0].split("-");
			var time = datetime.split(" ")[1].split(":");
			var tt = "am";
			if(time[0] >= 12) {
				time[0] = parseInt(time[0]) - 12;
				tt = "pm";
			}
			if(!parseInt(time[0])) {
				time[0] = 12;
			}
		
			var hhmm = [time[0], time[1]].join(":")
			
			// DD, d MM, yy hh:mm tt
			
			var dateobj = new Date(date[0], date[1], date[2])
			
			return repl("%(day)s, %(date)s %(month)s, %(year)s %(time)s", {
				day: get_day(dateobj.getDay()),
				date: date[2],
				month: get_month(dateobj.getMonth()),
				year: date[0],
				time: hhmm + " " + tt
			})
		}
		$(".event-timestamp").each(function() {
			$(this).html(format($(this).attr("data-timestamp")));
		})
	},
	toggle_earlier_replies: function() {
		var $earlier_replies = $(".child-post").slice(0, $(".child-post").length - 2);
		var $btn = $(".btn-earlier-replies").on("click", function() {
			if($earlier_replies.hasClass("hide")) {
				$earlier_replies.removeClass("hide");
				$(".btn-earlier-label").html("Hide");
			} else {
				$earlier_replies.addClass("hide");
				$(".btn-earlier-label").html("Show");
			}
		});
	
		if($earlier_replies.length) {
			$btn.toggleClass("hide", false).click();
		}
	},
	toggle_edit: function(only_owner) {
		if(only_owner) {
			var user = wn.get_cookie("user_id");
			$(".edit-post").each(function() {
				$(this).toggleClass("hide", !(website.access.write && $(this).attr("data-owner")===user));
			});
		} else {
			$(".edit-post").toggleClass("hide", !website.access.write);
		}
	},
	toggle_upvote: function() {
		if(!website.access.read) {
			$(".upvote").remove();
		}
	},
	toggle_post_editor: function() {
		$(".post-editor").toggleClass("hide", !website.access.write);
	},
	setup_upvote: function() {
		$(".post-list, .parent-post").on("click", ".upvote a", function() {
			var sid = wn.get_cookie("sid");
			if(!sid || sid==="Guest") {
				wn.msgprint("Please login to Upvote!");
				return;
			}
			var $post = $(this).parents(".post");
			var post = $post.attr("data-name");
			var $btn = $(this).prop("disabled", true);
			
			$.ajax({
				url: "/",
				type: "POST",
				data: {
					cmd: "webnotes.website.doctype.user_vote.user_vote.set_vote",
					ref_doctype: "Post",
					ref_name: post
				},
				statusCode: {
					200: function(data) {
						if(data.exc) {
							console.log(data.exc);
						} else {
							var text_class = data.message === "ok" ? "text-success" : "text-danger";
							if(data.message==="ok") {
								var count = parseInt($post.find(".upvote-count").text());
								$post.find(".upvote-count").text(count + 1).removeClass("hide");
							}
							$btn.addClass(text_class);
							setTimeout(function() { $btn.removeClass(text_class); }, 2000);
						}
					}
				}
			}).always(function() {
				$btn.prop("disabled", false);
			});
		});
	},
	setup_autosuggest: function(opts) {
		if(opts.$control.hasClass("ui-autocomplete-input")) return;
	
		wn.require("/assets/webnotes/js/lib/jquery/jquery.ui.min.js");
		wn.require("/assets/webnotes/js/lib/jquery/bootstrap_theme/jquery-ui.selected.css");

		var $user_suggest = opts.$control.autocomplete({
			source: function(request, response) {
				$.ajax({
					url: "/",
					data: {
						cmd: opts.method,
						term: request.term,
						group: website.group
					},
					success: function(data) {
						if(data.exc) {
							console.log(data.exc);
						} else {
							response(data.message);
						}
					}
				});
	        },
			select: function(event, ui) {
				opts.$control.val("");
				opts.select(ui.item.profile, ui.item);
			}
		});
	
		$user_suggest.data( "ui-autocomplete" )._renderItem = function(ul, item) {
			return $("<li>").html("<a style='padding: 5px;'>" + item.profile_html + "</a>")
				.css("padding", "5px")
				.appendTo(ul);
	    };
	
		return opts.$control
	},
	setup_datepicker: function(opts) {
		if(opts.$control.hasClass("hasDatetimepicker")) return;
	
		// libs required for datetime picker
		wn.require("/assets/webnotes/js/lib/jquery/jquery.ui.min.js");
		wn.require("/assets/webnotes/js/lib/jquery/bootstrap_theme/jquery-ui.selected.css");
		wn.require("/assets/webnotes/js/lib/jquery/jquery.ui.slider.min.js");
		wn.require("/assets/webnotes/js/lib/jquery/jquery.ui.sliderAccess.js");
		wn.require("/assets/webnotes/js/lib/jquery/jquery.ui.timepicker-addon.css");
		wn.require("/assets/webnotes/js/lib/jquery/jquery.ui.timepicker-addon.js");	

		opts.$control.datetimepicker({
			timeFormat: "hh:mm tt",
			dateFormat: 'DD, d MM, yy',
			changeYear: true,
			yearRange: "-70Y:+10Y",
			stepMinute: 5,
			hour: 10,
			onClose: opts.onClose
		});
	
		website.setup_datetime_functions();
	
		return opts.$control;
	},
	setup_datetime_functions: function() {
		// requires datetime picker
		wn.provide("website.datetimepicker");
		website.datetimepicker.str_to_obj = function(datetime_str) {
			return $.datepicker.parseDateTime("yy-mm-dd", "HH:mm:ss", datetime_str);
		};

		website.datetimepicker.obj_to_str = function(datetime) {
			if(!datetime) {
				return "";
			}
			// requires datepicker
			var date_str = $.datepicker.formatDate("yy-mm-dd", datetime)
			var time_str = $.datepicker.formatTime("HH:mm:ss", {
				hour: datetime.getHours(),
				minute: datetime.getMinutes(),
				second: datetime.getSeconds()
			})
			return date_str + " " + time_str;
		};

		website.datetimepicker.format_datetime = function(datetime) {
			if (typeof(datetime)==="string") {
				datetime = website.datetimepicker.str_to_obj(datetime);
			}
			var date_str = $.datepicker.formatDate("DD, d MM, yy", datetime)
			var time_str = $.datepicker.formatTime("hh:mm tt", {
				hour: datetime.getHours(),
				minute: datetime.getMinutes(),
				second: datetime.getSeconds()
			})
			return date_str + " " + time_str;
		}
	},
	setup_settings: function() {
		// autosuggest
		website.setup_autosuggest({
			$control: $(".add-user-control"),
			select: function(value) { 
				website.add_sitemap_permission(value); 
			},
			method: "webnotes.templates.website_group.settings.suggest_user"
		});

	
		// trigger for change permission
		$(".permission-editor-area").on("click", ".sitemap-permission [type='checkbox']", 
			website.update_permission);
		$(".permission-editor-area").find(".btn-add-group").on("click", website.add_group);
		$(".btn-settings").parent().addClass("active");
	
		// disabled public_write if not public_read
		var control_public_read = $(".control-add-group-public_read").click(function() {
			if(!$(this).prop("checked")) {
				$(".control-add-group-public_write").prop("checked", false).prop("disabled", true);
			} else {
				$(".control-add-group-public_write").prop("disabled", false);
			}
		}).trigger("click").trigger("click"); // hack
	},
	add_group: function() {
		var $control = $(".control-add-group"),
			$btn = $(".btn-add-group");

		if($control.val()) {
			$btn.prop("disabled", true);
			$.ajax({
				url:"/",
				type:"POST",
				data: {
					cmd:"webnotes.templates.website_group.settings.add_website_group",
					group: website.group,
					new_group: $control.val(),
					group_type: $(".control-add-group-type").val(),
					public_read: $(".control-add-group-public_read").is(":checked") ? 1 : 0,
					public_write: $(".control-add-group-public_write").is(":checked") ? 1 : 0
				},
				statusCode: {
					403: function() {
						wn.msgprint("Name Not Permitted");
					},
					200: function(data) {
						if(data.exc) {
							console.log(data.exc);
							if(data._server_messages) wn.msgprint(data._server_messages);
						} else {
							wn.msgprint("Group Added, refreshing...");
							setTimeout(function() { window.location.reload(); }, 1000)
						}
					}
				}
			}).always(function() {
				$btn.prop("disabled",false);
				$control.val("");
			})
		}
	},
	update_permission: function() {
		var $chk = $(this);
		var $tr = $chk.parents("tr:first");
		$chk.prop("disabled", true);
	
		$.ajax({
			url: "/",
			type: "POST",
			data: {
				cmd: "webnotes.templates.website_group.settings.update_permission",
				profile: $tr.attr("data-profile"),
				perm: $chk.attr("data-perm"),
				value: $chk.prop("checked") ? "1" : "0",
				sitemap_page: website.group
			},
			statusCode: {
				403: function() {
					wn.msgprint("Not Allowed");
				},
				200: function(data) {
					$chk.prop("disabled", false);
					if(data.exc) {
						$chk.prop("checked", !$chk.prop("checked"));
						console.log(data.exc);
					} else {
						if(!$tr.find(":checked").length) $tr.remove();
					}
				}
			},
		});
	},
	add_sitemap_permission: function(profile) {
		$.ajax({
			url: "/",
			type: "POST",
			data: {
				cmd: "webnotes.templates.website_group.settings.add_sitemap_permission",
				profile: profile,
				sitemap_page: website.group
			},
			success: function(data) {
				$(".add-user-control").val("");
				if(data.exc) {
					console.log(data.exc);
				} else {
					$(data.message).prependTo($(".permission-editor tbody"));
				}
			}
		});
	},
	update_group_description: function() {
		$(".btn-update-description").prop("disabled", true);
		$.ajax({
			url: "/",
			type: "POST",
			data: {
				cmd: "webnotes.templates.website_group.settings.update_description",
				description: $(".control-description").val() || "",
				group: website.group
			},
			success: function(data) {
				window.location.reload();
			}
		}).always(function() { 	$(".btn-update-description").prop("disabled", false); });
	}
});

$(document).on("apply_permissions", function() {
	website.toggle_permitted();
});
