# Integrations

## OAuth 2

Frappe Framework uses [`oauthlib`](https://github.com/oauthlib/oauthlib) to manage OAuth2 requirements. A Frappe instance can function as all of these:

1. **Resource Server**: contains resources, for example the data in your DocTypes.
2. **Authorization Server**: server that issues tokens to access some resource.
3. **Client**: app that requires access to some resource on a resource server.

DocTypes pertaining to the above roles:

1. **Common**
   - **OAuth Settings**: allows configuring certain OAuth features pertaining to the three roles.
2. **Authorization Server**
   - **OAuth Client**: keeps records of _clients_ registered with the frappe instance.
   - **OAuth Bearer Token**: tokens given out to registered _clients_ are maintained here.
   - **OAuth Authorization Code**: keeps track of OAuth codes a client responds with in exchange for a token.
   - **OAuth Provider Settings**: allows skipping authorization. `[DEPRECATED]` use **OAuth Settings** instead.
3. **Client**
   - **Connected App**: keeps records of _authorization servers_ against whom this frappe instance is registered as a _client_ so some resource can be accessed. Eg. a users Google Drive account.
   - **Social Key Login**: similar to **Connected App**, but for the purpose of logging into the frappe instance. Eg. a users Google account to enable "Login with Google".
   - **Token Cache**: tokens received by the Frappe instance when accessing a **Connected App**.

### Features

Additional features over `oauthlib` that have implemented in the Framework:

- **Dynamic Client Registration**: allows a client to register itself without manual configuration by the resource owner. [RFC7591](https://datatracker.ietf.org/doc/html/rfc7591)
- **Authorization Server Metadata Discovery**: allows a client to view the instance's auth server (itself) metadata such as auth end points. [RFC8414](https://datatracker.ietf.org/doc/html/rfc8414)
- **Resource Server Metadata Discovery**: allows a client to view the instance's resource server metadata such as documentation, auth servers, etc. [RFC9728](https://datatracker.ietf.org/doc/html/rfc9728)

### Additional Docs

Documentation of various OAuth2 features:

1. [How to setup OAuth 2?](https://docs.frappe.io/framework/user/en/guides/integration/how_to_set_up_oauth)
2. [OAuth 2](https://docs.frappe.io/framework/user/en/guides/integration/rest_api/oauth-2)
3. [Token Based Authentication](https://docs.frappe.io/framework/user/en/guides/integration/rest_api/token_based_authentication)
4. [Using Frappe as OAuth Service](https://docs.frappe.io/framework/user/en/using_frappe_as_oauth_service)
5. [Social Login Key](https://docs.frappe.io/framework/user/en/guides/integration/social_login_key)
6. [Connected App](https://docs.frappe.io/framework/user/en/guides/app-development/connected-app)

> [!WARNING]
>
> Some of these might be outdated, it is always recommended to check the code
> when in doubt.

### OAuth Settings

A Single doctype that allows configuring OAuth2 related features. It is
recommended to open the DocType page itself as each field and section has a
sufficiently descriptive help text.

The settings allow toggling the following features:

- Authorization check when active token is present using the _Skip Authorization_ field. _**Note**: Keep this unchecked in production._
- **Authorization Server Metadata Discovery**: by toggling the _Show Auth Server Metadata_ field.
- **Dynamic Client Registration**: by toggling the _Enable Dynamic Client Registration_ field.
- **Resource Server Metadata Discovery**: by toggling the _Show Protected Resource Metadata_.

The remaining fields (in the **Resource** section) are used only when responding to requests on `/.well-known/oauth-protected-resource`

> **Regarding Public Clients**
>
> Public clients, for example an SPA, have restricted access by default. This
> restriction is applied by use of CORS.
>
> To side-step this restriction for certain trusted clients, you may add their
> hostnames to the **Allowed Public Client Origins** field.
