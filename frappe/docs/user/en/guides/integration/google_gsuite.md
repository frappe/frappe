# Google GSuite

You can create and attach Google GSuite Docs to your Documents using your predefined GSuite Templates.
These Templates could use variables from Doctype that will be automatically filled.

## 1. Enable integration with Google Gsuite

### 1.1 Publish Google apps script

*If you will use the default script you can go to 1.2*

1. Go to [https://script.google.com](https://script.google.com)
1. Create a new Project. Click on **File > New > Project**
1. Copy the code of **Desk > Explore > Integrations > GSuite Settings > Google Apps Script** to clipboard and paste to an empty Code.gs in script.google.com
1. Save the Project. Click on **File > Save > Enter new project name**
1. Deploy the app. Click on **Publish > Deploy as web app**
1. Copy "Current web app URL" into **Desk > Explore > Integrations > GSuite Settings > Script URL**
1. Click on OK but don't close the script

### 1.2

### 1.2 Get Google access

1. Go to your Google project console and select your project or create a new. [https://console.developers.google.com](https://console.developers.google.com)
1. In Library click on **Google Drive API** and **Enable**
1. Click on **Credentials > Create Credentials > OAuth Client ID**
1. Fill the form with:
	- Web Application
	- Authorized redirect URI as  **http://{{ yoursite }}/?cmd=frappe.integrations.doctype.gsuite_settings.gsuite_settings.gsuite_callback**
1. Copy the Client ID and Client Secret into **Desk > Explore > Integrations > GSuite Settings > Client ID and Client Secret**
1. Save GSuite Settings

### 1.3 Test Script

1. Click on **Allow GSuite Access** and you will be redirected to select the user and give access. If you have any error please verify you are using the correct Authorized redirect URI.
1. Click on **Run Script test**. You should be asked to give permission.

## 2. GSuite Templates

### 2.1 Google Document as Template

1. Create a new Document or use one you already have. Set variables as you need. Variables are defined with ***{{VARIABLE}}*** with ***VARIABLE*** is the field of your Doctype

	For Example,
		If this document will be used to employee and the Doctype has the field ***name*** then you can use it in Google Docs ad {{name}}

1. Get the ID of that Document from url of your document

    For example: in this address the ID is in bold
	https://docs.google.com/document/d/**1Y2_btbwSqPIILLcJstHnSm1u5dgYE0QJspcZBImZQso**/edit

1. Get the ID of the folder where you want to place the generated documents. (You can step this point if you want to place the generated documents in Google Drive root. )

	For example: in this folder url the ID is in bold
	https://drive.google.com/drive/u/0/folders/**0BxmFzZZUHbgyQzVJNzY5eG5jbmc**

### 2.2 Associate the Template to a Doctype

1. Go to **Desk > Explore > Integrations > GSuite Templates > New**
1. Fill the form with:
	- Template Name (Example: Employee Contract)
	- Related DocType (Example: Employee)
	- Template ID is the Document ID you get from your Google Docs (Example: 1Y2_btbwSqPIILLcJstHnSm1u5dgYE0QJspcZBImZQso)
	- Document name is the name of the new files. You can use field from DocType (Example: Employee Contract of {name})
	- Destination ID is the folder ID of your files created from this Template. (Example: 0BxmFzZZUHbgyQzVJNzY5eG5jbmc)

## 3. Create Documents

1. Go to a Document you already have a Template (Example: Employee > John Doe)
2. Click on **Attach File**
3. O **GSuite Document** section select the Template and click **Attach**
4. You should see the generated document is already created and attached
