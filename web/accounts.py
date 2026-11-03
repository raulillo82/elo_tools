'''
Accounts, invitations and devices. There are no user names: a device cookie
says who it is, and the password confirms it. Accounts only have a first name
and a club. Secrets are only kept hashed.
'''
import hashlib
import secrets
import sqlite3
import time

from werkzeug.security import check_password_hash, generate_password_hash

INVITE_HOURS = 72
MAX_DEVICES = 2
MIN_PASSWORD = 10

#The Álava federation's clubs. A club can only have one person
CLUBS = ["Amurrio", "Buztinzuri", "Calasanz", "Danubio", "Eguidazu", "Kursaal", "Laudio",
         "Marianistas", "Martintxo", "San Viator"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, club TEXT UNIQUE NOT NULL,
    password_hash TEXT, is_admin INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
    token_hash TEXT UNIQUE NOT NULL, added INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS invites (
    token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
    expires INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS used_entries (nonce TEXT PRIMARY KEY, expires INTEGER NOT NULL);
"""
#Added after the first version. production_id is only used in staging, where it
#says who each account is in production
NEW_COLUMNS = {"staging_until": "INTEGER", "production_id": "INTEGER"}


class AccountError(Exception):
    '''
    Something the user can be told: a key of web/i18n.py, and its values
    '''
    def __init__(self, key, **values):
        super().__init__(key)
        self.key = key
        self.values = values


def hash_token(token):
    #Tokens are long and random, so a plain hash is enough for them
    return hashlib.sha256(token.encode()).hexdigest()


class Accounts:
    def __init__(self, path):
        self.path = path
        with self.connect() as database:
            database.executescript(SCHEMA)
            columns = {row["name"] for row in database.execute("PRAGMA table_info(users)")}
            for name, kind in NEW_COLUMNS.items():
                if name not in columns:
                    database.execute(f"ALTER TABLE users ADD COLUMN {name} {kind}")

    def connect(self):
        database = sqlite3.connect(self.path)
        database.row_factory = sqlite3.Row
        database.execute("PRAGMA foreign_keys = ON")
        return database

    def create_invite(self, name=None, club=None, is_admin=False, user_id=None):
        '''
        Returns the token of a one-use invitation, the only time it can be
        read. With a user_id it's for a new device of that account.
        '''
        token = secrets.token_urlsafe(32)
        with self.connect() as database:
            if user_id is None:
                if club not in CLUBS:
                    raise AccountError("no_such_club")
                if database.execute("SELECT 1 FROM users WHERE club = ?", (club,)).fetchone():
                    raise AccountError("club_taken")
                user_id = database.execute(
                    "INSERT INTO users (name, club, is_admin) VALUES (?, ?, ?)",
                    (name.strip(), club, int(is_admin))).lastrowid
            database.execute("DELETE FROM invites WHERE user_id = ?", (user_id,))
            database.execute("INSERT INTO invites VALUES (?, ?, ?)",
                             (hash_token(token), user_id, time.time() + INVITE_HOURS * 3600))
        return token

    def find_invite(self, token):
        '''
        Returns the user of a valid invitation, or None
        '''
        with self.connect() as database:
            return database.execute(
                "SELECT users.* FROM invites JOIN users ON users.id = invites.user_id"
                " WHERE token_hash = ? AND expires > ? AND active = 1",
                (hash_token(token), time.time())).fetchone()

    def accept_invite(self, token, password):
        '''
        Uses an invitation: sets the password the first time, and asks for it
        afterwards. Returns the user and a new device token.
        '''
        user = self.find_invite(token)
        if user is None:
            raise AccountError("invite_invalid")
        if user["password_hash"] is None:
            if len(password) < MIN_PASSWORD:
                raise AccountError("password_short", n=MIN_PASSWORD)
        elif not check_password_hash(user["password_hash"], password):
            raise AccountError("wrong_password")
        device_token = secrets.token_urlsafe(32)
        with self.connect() as database:
            count = database.execute("SELECT COUNT(*) FROM devices WHERE user_id = ?",
                                     (user["id"],)).fetchone()[0]
            if count >= MAX_DEVICES:
                raise AccountError("too_many_devices", n=MAX_DEVICES)
            if user["password_hash"] is None:
                database.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                                 (generate_password_hash(password), user["id"]))
            database.execute("INSERT INTO devices (user_id, token_hash, added) VALUES (?, ?, ?)",
                             (user["id"], hash_token(device_token), time.time()))
            database.execute("DELETE FROM invites WHERE token_hash = ?", (hash_token(token),))
        return self.get_user(user["id"]), device_token

    def user_of_device(self, device_token):
        '''
        Returns the active user of a device, or None
        '''
        if not device_token:
            return None
        with self.connect() as database:
            return database.execute(
                "SELECT users.* FROM devices JOIN users ON users.id = devices.user_id"
                " WHERE token_hash = ? AND active = 1", (hash_token(device_token),)).fetchone()

    def login(self, device_token, password):
        '''
        Returns the user if the device and the password are right, or None.
        Unknown devices also check a hash, to take the same time
        '''
        user = self.user_of_device(device_token)
        stored = user["password_hash"] if user else DUMMY_HASH
        return user if check_password_hash(stored, password) and user else None

    def set_staging(self, user_id, until):
        '''
        Gives access to staging until a time, or takes it away with None
        '''
        with self.connect() as database:
            database.execute("UPDATE users SET staging_until = ? WHERE id = ?", (until, user_id))

    def enter_staging(self, entry):
        '''
        In staging: uses a permission from production, once. Creates or updates
        the account, and returns it with a new device token.
        '''
        device_token = secrets.token_urlsafe(32)
        with self.connect() as database:
            database.execute("DELETE FROM used_entries WHERE expires < ?", (time.time(),))
            try:
                database.execute("INSERT INTO used_entries VALUES (?, ?)",
                                 (entry["nonce"], time.time() + 3600))
            except sqlite3.IntegrityError:
                raise AccountError("staging_bad") from None
            #A club can change hands in production
            for old in database.execute("SELECT id FROM users WHERE club = ? AND production_id IS NOT ?",
                                        (entry["club"], entry["id"])).fetchall():
                remove_user(database, old["id"])
            values = (entry["name"], entry["club"], entry["is_admin"], entry["until"])
            row = database.execute("SELECT id FROM users WHERE production_id = ?",
                                   (entry["id"],)).fetchone()
            if row:
                user_id = row["id"]
                database.execute("UPDATE users SET name = ?, club = ?, is_admin = ?, staging_until = ?"
                                 " WHERE id = ?", (*values, user_id))
            else:
                user_id = database.execute(
                    "INSERT INTO users (name, club, is_admin, staging_until, production_id)"
                    " VALUES (?, ?, ?, ?, ?)", (*values, entry["id"])).lastrowid
            database.execute("INSERT INTO devices (user_id, token_hash, added) VALUES (?, ?, ?)",
                             (user_id, hash_token(device_token), time.time()))
        return self.get_user(user_id), device_token

    def get_user(self, user_id):
        with self.connect() as database:
            return database.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    def list_users(self):
        with self.connect() as database:
            return database.execute(
                "SELECT users.*, (SELECT COUNT(*) FROM devices WHERE user_id = users.id) AS devices"
                " FROM users ORDER BY club").fetchall()

    def free_clubs(self):
        taken = {user["club"] for user in self.list_users()}
        return [club for club in CLUBS if club not in taken]

    def remove_devices(self, user_id):
        with self.connect() as database:
            database.execute("DELETE FROM devices WHERE user_id = ?", (user_id,))

    def delete_user(self, user_id):
        '''
        Deletes an account and frees its club. Admins can't be deleted
        '''
        with self.connect() as database:
            if database.execute("SELECT is_admin FROM users WHERE id = ?",
                                (user_id,)).fetchone()["is_admin"]:
                raise AccountError("admin_kept")
            remove_user(database, user_id)


def remove_user(database, user_id):
    for table in ("devices", "invites"):
        database.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
    database.execute("DELETE FROM users WHERE id = ?", (user_id,))


DUMMY_HASH = generate_password_hash(secrets.token_urlsafe(16))
