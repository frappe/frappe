# How to setup oauth?

<a href="https://tools.ietf.org/html/rfc6749">OAuth 2.0</a> provider based on <a href="https://github.com/idan/oauthlib">oauthlib</a> is built into frappe. Third party apps can now access resources of users based on Frappé Role and User permission system. To setup an app to access

## OAuth defines four roles

#### resource owner
An entity capable of granting access to a protected resource. When the resource owner is a person, it is referred to as an end-user.

#### resource server
The server hosting the protected resources, capable of accepting and responding to protected resource requests using access tokens.

#### client
An application making protected resource requests on behalf of the resource owner and with its authorization.  The term "client" does not imply any particular implementation characteristics (e.g.,
whether the application executes on a server, a desktop, or other devices).

#### authorization server
The server issuing access tokens to the client after successfully authenticating the resource owner and obtaining authorization.

## Setup OAuth Provider

System Managers can setup behavior of confirmation message as `Force` or `Auto` in OAuth Provider Settings.
If Force is selected the system will always ask for user's confirmation. If Auto is selected system asks for the confirmation only if there are no active tokens for the user.

Go to 

> Setup > Integrations > OAuth Provider Settings

<img class="screenshot" src="/docs/assets/img/oauth_provider_settings.png">

### Add Primary Server

This is the main server hosting all the users. e.g. `https://frappe.io`. To setup this as the main server, go to *Setup* > *Integrations* > *Social Login Keys* and enter `https://frappe.io` in the field  `Frappé Server URL`. This URL repeats in all other Frappé servers who connect to this server to authenticate. Effectively, this is the main Identity Provider (IDP). 

Under this server add as many `OAuth Client`(s) as required.

## Add a Client App

As a System Manager go to  

> Setup > Integrations > OAuth Client

<img class="screenshot" src="/docs/assets/img/oauth2_client_app.png">

To add a client fill in the following details

1. **App Name** : Enter App Name e.g. CAVS
2. **Skip Authorization** : If this is checked, during authentication there won't be me any confirmation message
3. **Scopes** : List of scopes shown to user along with confirmation message. scopes are separated by semicolon ';'
4. **Redirect URIs** : List of Redirect URIs separated by semicolon ';'
5. **Default Redirect URIs** : Default Redirect URI from list of Redirect URIs
6. **Grant Type**: select `Authorization Code`
7. **Response Type**: select `Code`
