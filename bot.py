import discord
from discord import app_commands
import json
import os
import psycopg2
from steam_imap import get_steam_guard_code

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "YOUR_DISCORD_BOT_TOKEN_HERE")
ACCOUNTS_FILE = "accounts.json"
DATABASE_URL = os.environ.get("DATABASE_URL")

# ── Database helpers ──────────────────────────────────────────────────────────

def get_db():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    label TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    password TEXT NOT NULL
                )
            """)
        conn.commit()

# ── Account storage (JSON locally, DB on Railway) ────────────────────────────

def load_accounts() -> dict:
    if DATABASE_URL:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT label, email, password FROM accounts")
                return {row[0]: {"email": row[1], "password": row[2]} for row in cur.fetchall()}
    if not os.path.exists(ACCOUNTS_FILE):
        return {}
    with open(ACCOUNTS_FILE, "r") as f:
        return json.load(f)

def save_account(label: str, email: str, password: str):
    if DATABASE_URL:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO accounts (label, email, password)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (label) DO UPDATE SET email=EXCLUDED.email, password=EXCLUDED.password
                """, (label, email, password))
            conn.commit()
    else:
        accounts = load_accounts()
        accounts[label] = {"email": email, "password": password}
        with open(ACCOUNTS_FILE, "w") as f:
            json.dump(accounts, f, indent=2)

def delete_account(label: str):
    if DATABASE_URL:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM accounts WHERE label = %s", (label,))
            conn.commit()
    else:
        accounts = load_accounts()
        del accounts[label]
        with open(ACCOUNTS_FILE, "w") as f:
            json.dump(accounts, f, indent=2)

# ── Bot setup ─────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

@client.event
async def on_ready():
    if DATABASE_URL:
        init_db()
    await tree.sync()
    print(f"Bot is online as {client.user}")

# Autocomplete helper
async def label_autocomplete(interaction: discord.Interaction, current: str):
    accounts = load_accounts()
    return [
        app_commands.Choice(name=label, value=label)
        for label in accounts
        if current.lower() in label.lower()
    ][:25]

# /steamcode [label]
@tree.command(name="steamcode", description="Fetch the latest Steam Guard code for an account")
@app_commands.describe(label="The account label you gave when adding it")
@app_commands.autocomplete(label=label_autocomplete)
async def steamcode(interaction: discord.Interaction, label: str):
    await interaction.response.defer(ephemeral=True)
    accounts = load_accounts()
    if label not in accounts:
        await interaction.followup.send(f"No account found with label `{label}`.", ephemeral=True)
        return
    acc = accounts[label]
    try:
        code = get_steam_guard_code(acc["email"], acc["password"])
        if code:
            await interaction.followup.send(f"Steam Guard code for `{label}`: **{code}**", ephemeral=True)
        else:
            await interaction.followup.send(f"No unread Steam Guard email found for `{label}`.", ephemeral=True)
    except RuntimeError as e:
        await interaction.followup.send(f"Error fetching code: {e}", ephemeral=True)

# /addaccount [label] [email] [password]
@tree.command(name="addaccount", description="Add a Gmail account to fetch Steam Guard codes from")
@app_commands.describe(label="A short name to identify this account", gmail="The Gmail address", app_password="The Gmail App Password")
async def addaccount(interaction: discord.Interaction, label: str, gmail: str, app_password: str):
    await interaction.response.defer(ephemeral=True)
    save_account(label, gmail, app_password)
    await interaction.followup.send(f"Account `{label}` saved successfully.", ephemeral=True)

# /removeaccount [label]
@tree.command(name="removeaccount", description="Remove a saved Gmail account")
@app_commands.describe(label="The label of the account to remove")
@app_commands.autocomplete(label=label_autocomplete)
async def removeaccount(interaction: discord.Interaction, label: str):
    await interaction.response.defer(ephemeral=True)
    accounts = load_accounts()
    if label not in accounts:
        await interaction.followup.send(f"No account found with label `{label}`.", ephemeral=True)
        return
    delete_account(label)
    await interaction.followup.send(f"Account `{label}` removed.", ephemeral=True)

# /listaccounts
@tree.command(name="listaccounts", description="List all saved Gmail account labels")
async def listaccounts(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    accounts = load_accounts()
    if not accounts:
        await interaction.followup.send("No accounts saved yet. Use `/addaccount` to add one.", ephemeral=True)
        return
    labels = "\n".join(f"• {label} ({acc['email']})" for label, acc in accounts.items())
    await interaction.followup.send(f"Saved accounts:\n{labels}", ephemeral=True)

client.run(DISCORD_TOKEN)
