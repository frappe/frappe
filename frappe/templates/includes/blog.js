// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// js inside blog page

var blog = {
	start: 0,
	get_list: function() {
		$.ajax({
			method: "GET",
			url: "/api/method/frappe.website.doctype.blog_post.blog_post.get_blog_list",
			data: {
				start: blog.start,
				by: get_url_arg("by"),
				category: window.category || get_url_arg("category")
			},
			dataType: "json",
			success: function(data) {
				$(".progress").toggle(false);
				if(data.exc) console.log(data.exc);
				blog.render(data.message);
			}
		});
	},
	render: function(data) {
		if(!data) data = [];
		var $wrap = $("#blog-list");
		$.each(data, function(i, b) {
			// comments
			if(!b.comments) {
				b.comment_text = 'No comments yet.'
			} else if (b.comments===1) {
				b.comment_text = '1 comment.'
			} else {
				b.comment_text = b.comments + ' comments.'
			}

			b.page_name = $.map(b.page_name.split("/"), function(p)
				{ return encodeURIComponent(p); }).join("/");

			b.avatar = b.avatar || "";

			// convert relative url to absolute
			if(b.avatar.match(/^(?!http|ftp|\/|#).*$/)) {
				b.avatar = "/" + b.avatar;
			}

			b.month = b.month.toUpperCase().substr(0,3);

			$(repl('<div class="row">\
					<div class="col-md-2 text-center" style="color: #ccc">\
						<h1 class="blog-day" style="margin: 0px;">%(day)s</h1>\
						<div class="small">%(month)s %(year)s</div>\
					</div>\
					<div class="col-md-1">\
						<div class="avatar avatar-medium" style="margin-top: 6px;">\
							<img src="%(avatar)s" />\
						</div>\
					</div>\
					<div class="col-md-9">\
						<a href="/%(page_name)s"><h4>%(title)s</h4></a>\
						<p>%(content)s</p>\
						<p style="color: #aaa; font-size: 90%">\
							<a href="/blog?by=%(blogger)s&by_name=%(full_name)s">\
								%(full_name)s</a> / %(comment_text)s</p>\
					</div>\
				</div><hr>', b)).appendTo($wrap);
		});
		blog.start += (data.length || 0);
		if(!data.length || data.length < 20) {
			if(blog.start) {
				$("#next-page").toggle(false)
					.parent().append("<div class='text-muted'>Nothing more to show.</div>");
			} else {
				$("#next-page").toggle(false)
					.parent().append("<div class='alert alert-warning'>No blogs written yet.</div>");
			}
		} else {
			$("#next-page").toggle(true);
		}
	}
};

$(document).ready(function() {
	// make list of blogs
	setTimeout(blog.get_list, 100);

	$("#next-page").click(function() {
		blog.get_list();
	})

	if(get_url_arg("by_name")) {
		$("#blot-subtitle").html("Posts by " + get_url_arg("by_name")).toggle(true);
	}

	if(get_url_arg("category")) {
		$("#blot-subtitle").html("Posts filed under " + get_url_arg("category")).toggle(true);
	}

});
