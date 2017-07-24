frappe.ready(() => {
	$(".revoke-tokens").on("click", function(event) {
		console.log("App Name", $(this).data("app_name"));
		console.log("client id", $(this).data("client_id"));
	});
});
