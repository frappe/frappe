// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// js inside blog page

frappe.blog = {
	start: 0,
	get_list: function() {
		$.ajax({
			method: "GET",
			url: "/api/method/frappe.templates.pages.blog.get_blog_list",
			data: {
				start: frappe.blog.start,
				by: get_url_arg("by"),
				category: window.category || get_url_arg("category")
			},
			dataType: "json",
			success: function(data) {
				if(data.exc) {
					console.log(data.exc);
				}
				if(data.message) {
					$(data.message).appendTo($("#blog-list"));
					frappe.blog.set_paging();
				}
			}
		});
	},
	set_paging: function(result_length) {
		frappe.blog.start = $(".blog-post-preview").length;
		if(!frappe.blog.start || (frappe.blog.start % 20) != 0) {
			if(frappe.blog.start) {
				$("#next-page").toggle(false);
				$(".blog-message").html(__("Nothing more to show."));
			} else {
				$("#next-page").toggle(false);
				$(".blog-message").html(__("No posts written yet."));
			}
		} else {
			$("#next-page").toggle(true);
		}
	}

};

frappe.ready(function() {
	frappe.blog.set_paging();

	$("#next-page").click(function() {
		frappe.blog.get_list();
	})

	if(get_url_arg("by_name")) {
		$("#blot-subtitle").html("Posts by " + get_url_arg("by_name")).toggle(true);
	}

	if(get_url_arg("category")) {
		$("#blot-subtitle").html("Posts filed under " + get_url_arg("category")).toggle(true);
	}
});
