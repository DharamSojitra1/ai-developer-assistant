# Authentication Guide

The API uses JSON Web Tokens for authentication. Every protected endpoint expects a bearer token in the Authorization header, and requests without one are rejected with HTTP 401.

## Registering and Logging In

New accounts are created with a POST request to the register endpoint using an email address and a password. Passwords must be at least 12 characters long and are hashed with Argon2 before they are stored, so the plain-text password never reaches the database.

After registering, a client logs in with the same credentials. A successful login returns two tokens: a short-lived access token and a long-lived refresh token. Clients should store the refresh token securely, for example in an HTTP-only cookie, and keep the access token in memory.

## Access Tokens

Access tokens expire after 15 minutes. The expiry is controlled by the ACCESS_TOKEN_EXPIRE_MINUTES setting. Each access token carries the user ID in the `sub` claim and a `type` claim set to `access`, which prevents a refresh token from being used to call protected endpoints.

When an access token expires, the API responds with HTTP 401 and the detail message "Invalid or expired access token". Clients should then use the refresh flow instead of asking the user to log in again.

## Refresh Tokens

Refresh tokens are valid for 7 days, controlled by REFRESH_TOKEN_EXPIRE_DAYS. Each refresh token has a unique `jti` identifier that is stored in the database when the token is issued.

Refresh tokens are rotated: calling the refresh endpoint returns a new access token and a new refresh token, and the old refresh token is revoked immediately. If two requests try to use the same refresh token at the same time, only one succeeds and the other receives HTTP 401. This rotation limits the damage if a refresh token is stolen, because a reused token is detected.

## Logging Out

Logging out revokes the refresh token that the client sends. Access tokens cannot be revoked individually, which is why they are short-lived; an access token keeps working until it expires even after logout.

## Roles

Every user has a role. New users get the `user` role. Administrators have the `admin` role, which is required to add shared knowledge-base documents. There is no endpoint to become an administrator; an existing user is promoted with the `promote_admin` script run on the server.
