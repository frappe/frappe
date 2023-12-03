import doctype_with_phone from "../fixtures/doctype_with_phone";

context("Control Phone", () => {
	before(() => {
		cy.login();
		cy.visit("/app/website");
	});

	afterEach(() => {
		cy.clear_dialogs();
	});

	function get_dialog_with_phone() {
		return cy.dialog({
			title: "Phone",
			fields: [
				{
					fieldname: "phone",
					fieldtype: "Phone",
				},
			],
		});
	}

	it("should set flag and data", () => {
		get_dialog_with_phone().as("dialog");

		cy.get(".selected-phone").click();
		cy.wait(100);
		cy.get(".phone-picker .phone-wrapper[id='afghanistan']").click();
		cy.wait(100);
		cy.get(".selected-phone .country").should("have.text", "+93");
		cy.get(".selected-phone > img").should("have.attr", "src").and("include", "/af.svg");

		cy.get(".selected-phone").click();
		cy.wait(100);
		cy.get(".phone-picker .phone-wrapper[id='india']").click();
		cy.wait(100);
		cy.get(".selected-phone .country").should("have.text", "+91");
		cy.get(".selected-phone > img").should("have.attr", "src").and("include", "/in.svg");

		let phone_number = "9312672712";
		cy.get(".selected-phone > img").click().first();
		cy.get_field("phone").first().click();
		cy.get(".frappe-control[data-fieldname=phone]")
			.findByRole("textbox")
			.first()
			.type(phone_number);

		cy.get_field("phone").first().should("have.value", phone_number);
		cy.get_field("phone").first().blur();
		cy.wait(100);
		cy.get("@dialog").then((dialog) => {
			let value = dialog.get_value("phone");
			expect(value).to.equal("+91-" + phone_number);
		});

		let search_text = "india";
		cy.get(".selected-phone").click().first();
		cy.get(".phone-picker").findByRole("searchbox").click().type(search_text);
		cy.get(".phone-section .phone-wrapper:not(.hidden)").then((i) => {
			cy.get(`.phone-section .phone-wrapper[id*="${search_text.toLowerCase()}"]`).then(
				(countries) => {
					expect(i.length).to.equal(countries.length);
				}
			);
		});
	});

	it("existing document should render phone field with data", () => {
		cy.visit("/app/doctype");
		cy.insert_doc("DocType", doctype_with_phone, true);
		cy.clear_cache();

		// Creating custom doctype
		cy.insert_doc("DocType", doctype_with_phone, true);
		cy.visit("/app/doctype-with-phone");
		cy.click_listview_primary_button("Add Doctype With Phone");

		// create a record
		cy.fill_field("title", "Test Phone 1");
		cy.fill_field("phone", "+91-9823341234");
		cy.get_field("phone").should("have.value", "9823341234");
		cy.click_doc_primary_button("Save");
		cy.get_doc("Doctype With Phone", "Test Phone 1").then((doc) => {
			let value = doc.data.phone;
			expect(value).to.equal("+91-9823341234");
		});

		// open the doc from list view
		cy.go_to_list("Doctype With Phone");
		cy.clear_cache();
		cy.click_listview_row_item(0);
		cy.title().should("eq", "Test Phone 1");
		cy.get(".selected-phone .country").should("have.text", "+91");
		cy.get(".selected-phone > img").should("have.attr", "src").and("include", "/in.svg");
		cy.get_field("phone").should("have.value", "9823341234");
	});
});
