# OpenID Connect and Frappé social login

## OpenID Connect

Frappé also uses Open ID connect essential standard for authenticating users. To get `id_token` with `access_token`, pass `openid` as the value for the scope parameter during authorization request.

If the scope is `openid` the JSON response with `access_token` will also include a JSON Web Token (`id_token`) signed with `HS256` and `Client Secret`. The decoded `id_token` includes the `at_hash`.

Example Bearer Token with scope `openid`

```
{
  "token_type": "Bearer",
  "id_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6Imp3dCJ9.eyJpc3MiOiJodHRwczovL21udGVjaG5pcXVlLmNvbSIsImF0X2hhc2giOiJOQlFXbExJUy1lQ1BXd1d4Y0EwaVpnIiwiYXVkIjoiYjg3NzJhZWQ1YyIsImV4cCI6MTQ3Nzk1NTYzMywic3ViIjoiNWFjNDE2NThkZjFiZTE1MjI4M2QxYTk0YjhmYzcwNDIifQ.1GRvhk5wNoR4GWoeQfleEDgtLS5nvj9nsO4xd8QE-Uk",
  "access_token": "ZJD04ldyyvjuAngjgBrgHwxcOig4vW",
  "scope": "openid",
  "expires_in": 3600,
  "refresh_token": "2pBTDTGhjzs2EWRkcNV1N67yw0nizS"
}
```

## Frappé social login setup

In this example there are 2 servers,

### Primary Server
This is the main server hosting all the users. e.g. `https://frappe.io`. To setup this as the main server, go to *Setup* > *Integrations* > *Social Login Keys* and enter `https://frappe.io` in the field  `Frappé Server URL`. This URL repeats in all other Frappé servers who connect to this server to authenticate. Effectively, this is the main Identity Provider (IDP). 

Under this server add as many `OAuth Client`(s) as required. Because we are setting up one app server, add only one `OAuth Client`

### Frappé App Server
This is the client connecting to the IDP. Go to *Setup* > *Integrations* > *Social Login Keys* on this server and add appropriate values to `Frappé Client ID` and `Frappé Client Secret` (refer to client added in primary server). As mentioned before keep the `Frappé Server URL` as `https://frappe.io`

Now you will see Frappé icon on the login page. Click on this icon to login with account created in primary server (IDP) `https://frappe.io`

**Note**: If `Skip Authorization` is checked while registering a client, page to allow or deny the granting access to resource is not shown. This can be used if the apps are internal to one organization and seamless user experience is needed.

## Steps

### Part 1 : on Frappé Identity Provider (IDP)

Login to IDP
<img class="screenshot" src="/docs/assets/img/00-login-to-idp.png">

Add OAuth Client on IDP
<img class="screenshot" src="/docs/assets/img/01-add-oauth-client-on-idp.png">

Set Server URL on IDP
<img class="screenshot" src="/docs/assets/img/02-set-server-url-on-idp.png">

### Part 2 : on Frappé App Server

Set `Frappé Client ID`  and `Frappé Client Secret` on App server (refer the client set on IDP)
<img class="screenshot" src="/docs/assets/img/03-set-clientid-client-secret-server-on-app-server.png">

**Note**: Frappé Server URL is the main server where identities from your organization are stored.

Login Screen on App Server (login with frappe)
<img class="screenshot" src="/docs/assets/img/04-login-screen-on-app-server.png">

### Part 3 : Redirected on IDP 

login with user on IDP
<img class="screenshot" src="/docs/assets/img/05-login-with-user-on-idp.png">

Confirm Access on IDP
<img class="screenshot" src="/docs/assets/img/06-confirm-grant-access-on-idp.png">

### Part 4 : Back on App Server

Logged in on app server with ID from IDP
<img class="screenshot" src="/docs/assets/img/07-logged-in-as-website-user-with-id-from-idp.png">
