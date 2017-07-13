QUnit.module("Role Permission Manager");

QUnit.only("Role-Manager Functions", function(assert) {
	assert.expect(4);
    let done = assert.async();
    frappe.run_serially([
        () => frappe.set_route("permission-manager", "Account"),
        () => $(".col-md-2:nth-child(1) .input-sm").val("Account").trigger("change"),
        () => frappe.timeout(0.3),
        () => $(".col-md-2+ .col-md-2 .input-sm").val("Accounts Manager").trigger("change"),
        () => frappe.timeout(0.3),
        () => assert.ok(cur_page.page._route.includes("Account")),
        () => assert.ok($("div#page-permission-manager td:nth-child(2) > a").html() == "Accounts Manager", "Filter Works"),
        () => frappe.timeout(1),
        () => $("div#page-permission-manager td:nth-child(5) > button").click(),
        () => frappe.timeout(1),
        () => assert.ok($("div#page-permission-manager td:nth-child(2) > a").length == 0, "Delete Works"),
        () => frappe.timeout(3),
        () => $("div#page-permission-manager button:nth-child(2)").click(),
        () => frappe.timeout(1),
        () => $(".btn-primary:contains('Yes')").click(),
        () => frappe.timeout(1),
        () => assert.ok($("div#page-permission-manager td:nth-child(2) > a").html() == "Accounts Manager", "Restore Default Works"),
        () => done()
	]);
});