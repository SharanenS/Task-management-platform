# Provider token verification

Shared protocol validation only; this package owns no business data or role rules.
The gateway and people service independently validate signed, unexpired access
JWTs for the exact issuer, API audience and authorized web client. ID tokens and
client-supplied role/actor headers establish no application authority.
