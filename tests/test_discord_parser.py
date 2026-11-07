"""
µLearn Concierge — Tests for Discord Announcement Parser
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock
from scripts.discord_sync import extract_message, write_markdown, read_existing_entries


def test_extract_plain_content():
    """Extract message with direct content."""
    mock_msg = MagicMock()
    mock_msg.id = 12345
    mock_msg.created_at = datetime(2026, 11, 1, 10, 30)
    mock_msg.content = "New workshop announcement: AI Interest Group meeting this Saturday at 4 PM."
    mock_msg.embeds = []
    mock_msg.message_snapshots = []

    entry = extract_message(mock_msg)
    assert entry is not None
    assert entry["id"] == 12345
    assert entry["date"] == "2026-11-01"
    assert "New workshop announcement" in entry["title"]
    assert "AI Interest Group meeting" in entry["body"]


def test_extract_embed_content():
    """Extract message that contains rich embed fields and title."""
    mock_msg = MagicMock()
    mock_msg.id = 67890
    mock_msg.created_at = datetime(2026, 11, 2, 14, 0)
    mock_msg.content = ""
    
    mock_embed = MagicMock()
    mock_embed.title = "GTech µLearn Hackathon 2026"
    mock_embed.description = "Registrations are now open for the biggest student hackathon."
    mock_embed.url = "https://mulearn.org/hackathon"
    
    mock_field1 = MagicMock()
    mock_field1.name = "Prize Pool"
    mock_field1.value = "50,000 INR + 1000 Karma Points"
    
    mock_embed.fields = [mock_field1]
    mock_embed.footer.text = "µLearn Foundation"
    mock_msg.embeds = [mock_embed]
    mock_msg.message_snapshots = []

    entry = extract_message(mock_msg)
    assert entry is not None
    assert entry["id"] == 67890
    assert "GTech µLearn Hackathon 2026" in entry["title"]
    assert "Registrations are now open" in entry["body"]
    assert "Prize Pool:" in entry["body"]
    assert "Link: https://mulearn.org/hackathon" in entry["body"]


def test_extract_forwarded_snapshot():
    """Extract forwarded message via message_snapshots (channel following)."""
    mock_msg = MagicMock()
    mock_msg.id = 99999
    mock_msg.created_at = datetime(2026, 11, 3, 16, 45)
    mock_msg.content = ""  # Wrapper message has empty content
    mock_msg.embeds = []

    # Forwarded snapshot
    mock_snapshot = MagicMock()
    mock_snapshot.content = "Official announcement from central #announcements: Submissions close tonight!"
    mock_snapshot.embeds = []
    mock_msg.message_snapshots = [mock_snapshot]

    entry = extract_message(mock_msg)
    assert entry is not None
    assert entry["id"] == 99999
    assert "Official announcement" in entry["title"]
    assert "Submissions close tonight!" in entry["body"]


def test_extract_snapshot_with_embed():
    """Extract forwarded message that contains an embed inside the snapshot."""
    mock_msg = MagicMock()
    mock_msg.id = 88888
    mock_msg.created_at = datetime(2026, 11, 4, 18, 0)
    mock_msg.content = ""
    mock_msg.embeds = []

    mock_snapshot = MagicMock()
    mock_snapshot.content = ""
    mock_snap_embed = MagicMock()
    mock_snap_embed.title = "Top Colleges on Karma Leaderboard"
    mock_snap_embed.description = "College of Engineering Chengannur (CEC) enters top 5!"
    mock_snap_embed.fields = []
    mock_snap_embed.url = ""
    mock_snapshot.embeds = [mock_snap_embed]

    mock_msg.message_snapshots = [mock_snapshot]

    entry = extract_message(mock_msg)
    assert entry is not None
    assert "Top Colleges on Karma Leaderboard" in entry["title"]
    assert "College of Engineering Chengannur" in entry["body"]


def test_skip_empty_message():
    """Messages with no text content, no embeds, and no snapshots return None."""
    mock_msg = MagicMock()
    mock_msg.id = 11111
    mock_msg.created_at = datetime(2026, 11, 5, 12, 0)
    mock_msg.content = "   "
    mock_msg.embeds = []
    mock_msg.message_snapshots = []

    entry = extract_message(mock_msg)
    assert entry is None

