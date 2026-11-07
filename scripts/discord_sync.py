"""
µLearn Concierge — Discord Announcement Sync
Connects to Discord, reads the last 100 messages from configured channels,
extracts content (including forwarded message snapshots and embeds), and
writes them to knowledge/discord_news.md.

Usage:
    python scripts/discord_sync.py

Requirements:
    - DISCORD_BOT_TOKEN in .env
    - DISCORD_CHANNEL_IDS in .env (comma-separated)
    - Bot must have Message Content intent enabled in Discord Developer Portal
    - Bot must be in the server and have read access to the channels

This is a one-shot sync script, NOT a long-running bot.
It connects, reads messages, writes the file, and exits.
"""

import os
import sys
import re
import asyncio
from datetime import datetime

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: python-dotenv not installed. Run: pip install python-dotenv")
    sys.exit(1)

try:
    import discord
except ImportError:
    print("ERROR: discord.py not installed. Run: pip install discord.py")
    sys.exit(1)

load_dotenv()

KNOWLEDGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge")
OUTPUT_FILE = os.path.join(KNOWLEDGE_DIR, "discord_news.md")


def extract_message(msg):
    """Extract text content from a Discord message, including embeds and forwarded snapshots.
    
    Returns a dict with id, date, title, body — or None if the message has no useful content.
    """
    parts = []

    # 1. Direct message content
    if msg.content and msg.content.strip():
        parts.append(msg.content.strip())

    # 2. Embeds (rich embeds sent by bots, webhooks, or link previews)
    for embed in msg.embeds:
        embed_parts = []
        if embed.title:
            embed_parts.append(f"**{embed.title}**")
        if embed.description:
            embed_parts.append(embed.description)
        for field in embed.fields:
            embed_parts.append(f"**{field.name}:** {field.value}")
        if embed.footer and embed.footer.text:
            embed_parts.append(f"_{embed.footer.text}_")
        if embed.url:
            embed_parts.append(f"Link: {embed.url}")
        if embed_parts:
            parts.extend(embed_parts)

    # 3. Forwarded message snapshots (discord.py 2.5+)
    #    When a message is forwarded via "channel following" or manual forward,
    #    the content lives in message_snapshots, not in message.content.
    if hasattr(msg, 'message_snapshots') and msg.message_snapshots:
        for snapshot in msg.message_snapshots:
            snap_parts = []
            # Snapshot content
            if hasattr(snapshot, 'content') and snapshot.content and snapshot.content.strip():
                snap_parts.append(snapshot.content.strip())
            # Snapshot embeds
            if hasattr(snapshot, 'embeds') and snapshot.embeds:
                for embed in snapshot.embeds:
                    if embed.title:
                        snap_parts.append(f"**{embed.title}**")
                    if embed.description:
                        snap_parts.append(embed.description)
                    for field in embed.fields:
                        snap_parts.append(f"**{field.name}:** {field.value}")
                    if embed.url:
                        snap_parts.append(f"Link: {embed.url}")
            if snap_parts:
                parts.extend(snap_parts)

    # Skip messages with no text content
    if not parts:
        return None

    body = "\n\n".join(parts)

    # Extract title: first non-empty line, truncated
    first_line = parts[0].split("\n")[0].strip()
    # Remove markdown bold markers for the title
    title = re.sub(r'\*+', '', first_line)[:80].strip()
    if not title:
        title = "Announcement"

    return {
        "id": msg.id,
        "date": msg.created_at.strftime("%Y-%m-%d"),
        "timestamp": msg.created_at,
        "title": title,
        "body": body,
    }


def read_existing_entries():
    """Read existing discord_news.md and extract message IDs and manual entries."""
    existing_ids = set()
    manual_entries = []

    if not os.path.exists(OUTPUT_FILE):
        return existing_ids, manual_entries

    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            content = f.read()
    except (IOError, OSError):
        return existing_ids, manual_entries

    # Extract message IDs from comments like <!-- msg_id: 123456 -->
    for match in re.finditer(r'<!-- msg_id: (\d+) -->', content):
        existing_ids.add(int(match.group(1)))

    # Extract manual entries (those without a msg_id comment)
    sections = re.split(r'\n(?=## )', content)
    for section in sections:
        if section.startswith("## ") and "<!-- msg_id:" not in section:
            manual_entries.append(section.strip())

    return existing_ids, manual_entries


def write_markdown(entries, manual_entries=None):
    """Write all entries to discord_news.md, newest first."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    lines = [
        "# µLearn Discord Announcements",
        "> Source: µLearn Discord #announcements (central GTech µLearn feed)",
        "> Synced via: scripts/discord_sync.py",
        f"> Last synced: {now}",
        "",
        "<!-- Older announcements can be pasted below manually. Use the format:",
        "## YYYY-MM-DD — Title",
        "Body text, links, etc.",
        "-->",
        "",
    ]

    # Sort by date descending (newest first)
    entries.sort(key=lambda e: e["timestamp"], reverse=True)

    for entry in entries:
        lines.append(f"## {entry['date']} — {entry['title']}")
        lines.append(f"<!-- msg_id: {entry['id']} -->")
        lines.append("")
        lines.append(entry["body"])
        lines.append("")

    # Append manual entries at the end
    if manual_entries:
        lines.append("---")
        lines.append("")
        lines.append("<!-- Manual entries below -->")
        lines.append("")
        for entry in manual_entries:
            lines.append(entry)
            lines.append("")

    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


async def sync(quiet_on_missing=False):
    """Main sync function: connect to Discord, read messages, write markdown."""
    token = os.getenv("DISCORD_BOT_TOKEN")
    channel_ids_str = os.getenv("DISCORD_CHANNEL_IDS", "") or os.getenv("DISCORD_CHANNEL_ID", "")

    # Validate config
    if not token:
        if quiet_on_missing:
            return False
        print("ERROR: DISCORD_BOT_TOKEN not set in .env")
        print("  1. Create a bot at https://discord.com/developers/applications")
        print("  2. Copy the token to your .env file")
        sys.exit(1)

    if not channel_ids_str.strip():
        if quiet_on_missing:
            return False
        print("ERROR: DISCORD_CHANNEL_IDS not set in .env")
        print("  Set it to a comma-separated list of channel IDs to read from.")
        sys.exit(1)

    channel_ids = [cid.strip() for cid in channel_ids_str.split(",") if cid.strip()]

    print("=" * 60)
    print("µLearn Concierge — Discord Sync")
    print("=" * 60)
    print(f"  Channels to sync: {len(channel_ids)}")

    # Read existing entries for de-duplication
    existing_ids, manual_entries = read_existing_entries()
    print(f"  Existing message IDs: {len(existing_ids)}")
    print(f"  Manual entries preserved: {len(manual_entries)}")

    # Set up Discord client
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    all_entries = []
    errors = []

    @client.event
    async def on_ready():
        nonlocal all_entries, errors
        print(f"\n  Connected as: {client.user}")
        print(f"  Guilds: {len(client.guilds)}")

        for cid in channel_ids:
            try:
                channel_id = int(cid)
            except ValueError:
                errors.append(f"Invalid channel ID: {cid}")
                continue

            channel = client.get_channel(channel_id)
            if not channel:
                # Try fetching if not in cache
                try:
                    channel = await client.fetch_channel(channel_id)
                except discord.NotFound:
                    errors.append(f"Channel {cid} not found. Check the ID and bot permissions.")
                    continue
                except discord.Forbidden:
                    errors.append(f"No access to channel {cid}. Ensure the bot has 'Read Message History' permission.")
                    continue
                except Exception as e:
                    errors.append(f"Error fetching channel {cid}: {e}")
                    continue

            print(f"\n  Reading #{channel.name} ({channel.id})...")

            try:
                count = 0
                async for msg in channel.history(limit=100):
                    entry = extract_message(msg)
                    if entry and entry["id"] not in existing_ids:
                        all_entries.append(entry)
                        count += 1
                    elif entry and entry["id"] in existing_ids:
                        # Keep existing entry (already synced)
                        all_entries.append(entry)
                
                print(f"    Found {count} new messages")
            except discord.Forbidden:
                errors.append(
                    f"Cannot read messages in #{channel.name}. "
                    "Ensure the bot has 'Read Message History' permission and "
                    "'Message Content' intent is enabled at "
                    "https://discord.com/developers/applications"
                )
            except Exception as e:
                errors.append(f"Error reading #{channel.name}: {e}")

        # Write output
        if all_entries:
            write_markdown(all_entries, manual_entries)
            print(f"\n✓ Wrote {len(all_entries)} entries to {OUTPUT_FILE}")
        else:
            print("\n  No messages found. Existing file preserved.")

        # Report errors
        if errors:
            print("\n⚠  Errors encountered:")
            for err in errors:
                print(f"    - {err}")

        await client.close()

    # Start the client (blocks until on_ready completes and calls client.close)
    try:
        await client.start(token)
    except discord.LoginFailure as e:
        if quiet_on_missing:
            return False
        print("ERROR: Invalid bot token. Check DISCORD_BOT_TOKEN in .env")
        print("  Get your token from https://discord.com/developers/applications")
        sys.exit(1)
    except discord.PrivilegedIntentsRequired as e:
        if quiet_on_missing:
            return False
        print("ERROR: Message Content intent is required but not enabled.")
        print("  1. Go to https://discord.com/developers/applications")
        print("  2. Select your bot → Bot → Privileged Gateway Intents")
        print("  3. Enable 'Message Content Intent'")
        sys.exit(1)
    except Exception as e:
        if quiet_on_missing:
            return False
        print(f"ERROR: Failed to connect to Discord: {e}")
        sys.exit(1)
    return True


def main():
    asyncio.run(sync())


if __name__ == "__main__":
    main()
