'''
Entry to staging from production, without a second password. Production signs
a short permission, and staging reads it and opens the session.

It only goes that way: production never accepts anything from staging. The key
has no other use, so code being tried in staging can at most fake its own
entries, in an environment without real accounts.
'''
import secrets
import time

from itsdangerous import BadData, URLSafeTimedSerializer

SALT = "elo-staging-entry"
ENTRY_SECONDS = 60


def entry_token(key, user):
    '''
    Returns the signed permission of a user of production
    '''
    return URLSafeTimedSerializer(key, salt=SALT).dumps({
        "id": user["id"], "name": user["name"], "club": user["club"],
        "is_admin": user["is_admin"], "until": user["staging_until"],
        "nonce": secrets.token_urlsafe(16)})


def read_entry(key, token):
    '''
    Returns what a permission says, or None if it's forged, old, or its access is over
    '''
    try:
        entry = URLSafeTimedSerializer(key, salt=SALT).loads(token, max_age=ENTRY_SECONDS)
    except BadData:
        return None
    return entry if entry["until"] > time.time() else None
