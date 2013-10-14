$(function() {
	$('<br><button class="editable-button btn btn-default">Edit</button>').appendTo($("footer.container"))
	$(".editable-button").click(function() {
		if(window.editable) {
			$(".web-page-content").attr("contentEditable", false).removeClass("web-page-editable");
			window.editable = false;
			$(this).html("Edit");
			var html = $(".web-page-content").html() || "";
			html = html.replace(/(font-family|font-size|line-height):[^;]*;/g, '');
			html = html.replace(/<[^>]*(font=['"][^'"]*['"])>/g, function(a,b) { return a.replace(b, ''); });
			html = html.replace(/\s*style\s*=\s*["']\s*["']/g, '');
			$(".web-page-content").html(html);
		
			wn.call({
				type: "POST",
				method: "webnotes.client.set_value",
				args: {
					doctype:"Web Page",
					name: window.name,
					fieldname: "main_section",
					value: html
				},
				callback: function(r) {
					wn.msgprint(r.exc ? "Error" : "Saved");
				}
			});
		} else {
			$(".web-page-content").attr("contentEditable", true).addClass("web-page-editable").focus();
			$(this).html("Save");
			window.editable = true;
		}
	});
})
