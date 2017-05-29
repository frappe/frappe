import { Selector } from 'testcafe';

fixture `Setup Wizard`
    .page `http://localhost:8000/login`;

test('Setup Wizard Test', async t => {
    const wizard_heading  = Selector(() => {
    	return $('p.lead:visible')[0];
    })
    const lang = Selector("select[data-fieldname='language']")
    const next_btn = Selector("a.next-btn")
    const country = Selector("select[data-fieldname='country']")
    const timezone = Selector("select[data-fieldname='timezone']")
    const currency = Selector("select[data-fieldname='currency']")
    const full_name = Selector("input[data-fieldname='full_name']")
    const email = Selector("input[data-fieldname='email']")
    const password = Selector("input[data-fieldname='password']")
    const upload_input = Selector("input.input-upload-file")
    const upload_btn = Selector("button").withText("Upload")
    const modal_close_btn = Selector("div.modal.in button.btn-modal-close")
    const missing_image_div = Selector("div.missing-image")
    const complete_setup = Selector("a.complete-btn").nth(2)
    const setup_complete_div = Selector("p").withText("Setup Complete")



	await t
	.typeText('#login_email', 'Administrator')
	.typeText('#login_password', 'admin')
	.click('.btn-login')
	.navigateTo('/desk#setup-wizard')

	// Step 0
	.expect(wizard_heading.innerText).eql("Welcome")
	.click(lang)
	.click("option[value='English (United States)']")
	.expect(lang.value).eql("English (United States)")
	.click(next_btn)

	// Step 1
	.expect(wizard_heading.innerText).eql("Region")
	.click(country)
	.click("option[value='India']")
	.expect(country.value).eql("India")
	.expect(timezone.value).eql("Asia/Kolkata")
	.expect(currency.value).eql("INR")
	.click(next_btn.nth(1))

	// Step 2
	.expect(wizard_heading.innerText).eql("The First User: You")
	.typeText(full_name, "Jane Doe")
	.expect(full_name.value).eql("Jane Doe")
	.typeText(email, "jane_doe@example.com")
	.expect(email.value).eql("jane_doe@example.com")
	.typeText(password, "password")
	.expect(password.value).eql("password")
	.click("button[data-fieldname='attach_user']")
	.setFilesToUpload(upload_input, './uploads/user_picture.svg')
	.click(upload_btn)
	.click(modal_close_btn)
	.expect(missing_image_div.visible).notOk()
	.click(complete_setup)
	.expect(setup_complete_div.visible).ok()
});
