# OpenID Connect and Frappe social login

## OpenID Connect

Frappe also uses Open ID connect essential standard for authenticating users. To get `id_token` with `access_token` the scope parameter `openid` must be passed during authorization request.

If the scope is `openid` the JSON response with `access_token` will also include a JSON Web Token (`id_token`) signed with `HS256` and `Client Secret`. The decoded `id_token` includes the `at_hash`.

## Frappe social login setup

In this example there are 2 servers,

### Primary Server
This is the main server hosting all the users. e.g. `https://frappe.io`. To setup this as the main server, go to *Setup* > *Integrations* > *Social Login Keys* and enter `https://frappe.io` in the field  `Frappe Server URL`. This URL repeats in all other Frappe servers who connect to this server to authenticate. Effectively, this is the main Identity Provider (IDP). 

Under this server add as many `OAuth Client`(s) as required. Because we are setting up one app server, add only one `OAuth Client`

### Frappe App Server
This is the client connecting to the IDP. Go to *Setup* > *Integrations* > *Social Login Keys* on this server and add appropriate values to `Frappe Client ID` and `Frappe Client Secret` (refer to client added in primary server). As mentioned before keep the `Frappe Server URL` as `https://frappe.io`

Now you will see Frappe icon on the login page. Click on this icon to login with account created in primary server (IDP) `https://frappe.io`

**Note**: If `Skip Authorization` is checked while registering a client, page to allow or deny the granting access to resource is not shown. This can be used if the apps are internal to one organization and seamless user experience is needed.
