#!/usr/bin/env python3
"""
Discord Chat HTML Export Parser
Extracts messages from Discord HTML export to structured JSONL format
"""

import json
import hashlib
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from dataclasses import dataclass, asdict


@dataclass
class DiscordMessage:
    """Represents a single Discord message"""
    msg_id: str  # Stable hash-based ID
    timestamp_raw: str  # Raw timestamp string from HTML
    timestamp_utc: str  # Normalized UTC timestamp
    timestamp_berlin: str  # Berlin timezone timestamp
    author: str
    channel: str
    content_text: str
    inline_links: List[str]
    attachment_refs: List[Dict[str, str]]  # list of {type, url, name}
    is_same_sender: bool  # Consecutive message from same author
    
    
def parse_timestamp(timestamp_str: str) -> tuple[str, str]:
    """
    Parse Discord timestamp to UTC and Berlin time
    Example: "Tue Oct 21 2025 19:41:35 GMT+0200 (Mitteleuropäische Sommerzeit)"
    Returns: (utc_iso, berlin_iso)
    """
    # Extract timezone info
    if "GMT+0200" in timestamp_str or "Sommerzeit" in timestamp_str:
        tz_offset = "+02:00"
    elif "GMT+0100" in timestamp_str or "Normalzeit" in timestamp_str:
        tz_offset = "+01:00"
    else:
        tz_offset = "+00:00"
    
    # Parse the date/time portion
    # Format: "Tue Oct 21 2025 19:41:35"
    match = re.search(r'([A-Z][a-z]{2}) ([A-Z][a-z]{2}) (\d{2}) (\d{4}) (\d{2}):(\d{2}):(\d{2})', timestamp_str)
    if match:
        day_name, month_str, day, year, hour, minute, second = match.groups()
        
        # Convert month name to number
        months = {
            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
            'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
        }
        month = months.get(month_str, '01')
        
        # Build Berlin timestamp
        berlin_iso = f"{year}-{month}-{day}T{hour}:{minute}:{second}{tz_offset}"
        
        # Calculate UTC (subtract offset)
        from datetime import datetime, timedelta
        if tz_offset == "+02:00":
            offset_hours = 2
        elif tz_offset == "+01:00":
            offset_hours = 1
        else:
            offset_hours = 0
        
        dt = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
        dt_utc = dt - timedelta(hours=offset_hours)
        utc_iso = dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        return utc_iso, berlin_iso
    
    return timestamp_str, timestamp_str


def generate_msg_id(author: str, timestamp: str, content_snippet: str) -> str:
    """Generate a stable message ID based on author, timestamp, and content"""
    # Take first 50 chars of content for uniqueness
    snippet = content_snippet[:50] if content_snippet else ""
    combined = f"{author}|{timestamp}|{snippet}"
    hash_obj = hashlib.sha256(combined.encode('utf-8'))
    return f"msg_{hash_obj.hexdigest()[:16]}"


def extract_attachments(li_element) -> List[Dict[str, str]]:
    """Extract attachment information from message"""
    attachments = []
    
    # Image attachments
    for img in li_element.select('.image-attachment img'):
        attachments.append({
            'type': 'image',
            'url': img.get('src', ''),
            'name': img.get('alt', 'image')
        })
    
    # File attachments
    for file_link in li_element.select('.file-attachment a'):
        attachments.append({
            'type': 'file',
            'url': file_link.get('href', ''),
            'name': file_link.text.strip()
        })
    
    # Video attachments
    for video in li_element.select('.video-attachment video'):
        attachments.append({
            'type': 'video',
            'url': video.get('src', ''),
            'name': 'video'
        })
    
    # Audio attachments
    for audio in li_element.select('.audio-attachment audio'):
        attachments.append({
            'type': 'audio',
            'url': audio.get('src', ''),
            'name': 'audio'
        })
    
    return attachments


def extract_inline_links(content: str) -> List[str]:
    """Extract URLs from message content"""
    # Find all URLs in text
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, content)
    return urls


def parse_discord_html(html_path: Path, channel_name: str = "dax-trading-georg") -> List[DiscordMessage]:
    """Parse Discord HTML export and extract all messages"""
    
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    
    messages = []
    
    # Find all message li elements
    message_elements = soup.select('ul.chatContent li')
    
    print(f"Found {len(message_elements)} message elements")
    
    for li in message_elements:
        # Check if same sender (consecutive message from same author)
        is_same_sender = 'sameSender' in li.get('class', [])
        
        # Extract author
        author_span = li.select_one('.chatName')
        author = author_span.text.strip() if author_span else "Unknown"
        
        # Extract timestamp
        time_span = li.select_one('.time')
        timestamp_raw = time_span.text.strip() if time_span else ""
        
        # Parse timestamp
        timestamp_utc, timestamp_berlin = parse_timestamp(timestamp_raw)
        
        # Extract content - look for p elements inside .titleInfo div
        titleinfo_div = li.select_one('.titleInfo')
        content_text = ""
        if titleinfo_div:
            # Get all p elements except the one with timeInfo class
            content_paragraphs = [p for p in titleinfo_div.find_all('p') if 'timeInfo' not in p.get('class', [])]
            if content_paragraphs:
                # Join all paragraph text, removing @mentions formatting
                texts = []
                for p in content_paragraphs:
                    # Get text, stripping sky blue spans (user mentions)
                    text = p.get_text(strip=True)
                    if text:
                        texts.append(text)
                content_text = "\n".join(texts)
        
        # Extract inline links
        inline_links = extract_inline_links(content_text)

        
        # Extract attachments
        attachments = extract_attachments(li)
        
        # Generate stable ID
        msg_id = generate_msg_id(author, timestamp_berlin, content_text)
        
        msg = DiscordMessage(
            msg_id=msg_id,
            timestamp_raw=timestamp_raw,
            timestamp_utc=timestamp_utc,
            timestamp_berlin=timestamp_berlin,
            author=author,
            channel=channel_name,
            content_text=content_text,
            inline_links=inline_links,
            attachment_refs=attachments,
            is_same_sender=is_same_sender
        )
        
        messages.append(msg)
    
    return messages


def generate_stats(messages: List[DiscordMessage]) -> Dict[str, Any]:
    """Generate basic statistics from messages"""
    
    # Count messages per author
    author_counts = {}
    for msg in messages:
        author_counts[msg.author] = author_counts.get(msg.author, 0) + 1
    
    # Count attachments
    total_attachments = sum(len(msg.attachment_refs) for msg in messages)
    
    # Get date range
    timestamps = [msg.timestamp_berlin for msg in messages if msg.timestamp_berlin]
    date_range = f"{timestamps[0]} to {timestamps[-1]}" if timestamps else "Unknown"
    
    # Count messages with attachments
    msgs_with_attachments = sum(1 for msg in messages if msg.attachment_refs)
    
    # Count messages with links
    msgs_with_links = sum(1 for msg in messages if msg.inline_links)
    
    # Key term frequencies
    all_text = " ".join(msg.content_text.lower() for msg in messages)
    key_terms = {
        'setup': all_text.count('setup'),
        'zone': all_text.count('zone'),
        'long': all_text.count('long'),
        'short': all_text.count('short'),
        'vdax': all_text.count('vdax'),
        'punkte': all_text.count('punkte'),
        'regelwerk': all_text.count('regelwerk'),
        'stop': all_text.count('stop'),
        'limit': all_text.count('limit'),
    }
    
    return {
        'total_messages': len(messages),
        'total_authors': len(author_counts),
        'date_range': date_range,
        'top_authors': dict(sorted(author_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
        'total_attachments': total_attachments,
        'messages_with_attachments': msgs_with_attachments,
        'messages_with_links': msgs_with_links,
        'key_term_frequencies': key_terms
    }


def main():
    """Main extraction pipeline"""
    
    # Paths
    base_dir = Path(__file__).parent.parent
    html_file = base_dir / "sources" / "discord_chat_export.html"
    
    # Generate run ID from current time
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create output directory
    output_dir = base_dir / "artifacts" / "chat_extract" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Parsing HTML file: {html_file}")
    print(f"Output directory: {output_dir}")
    
    # Parse messages
    messages = parse_discord_html(html_file)
    
    print(f"Extracted {len(messages)} messages")
    
    # Write messages to JSONL
    jsonl_file = output_dir / "discord_messages.jsonl"
    with open(jsonl_file, 'w', encoding='utf-8') as f:
        for msg in messages:
            f.write(json.dumps(asdict(msg), ensure_ascii=False) + '\n')
    
    print(f"Wrote messages to: {jsonl_file}")
    
    # Write attachments manifest
    manifest_file = output_dir / "attachments_manifest.csv"
    with open(manifest_file, 'w', encoding='utf-8') as f:
        f.write("msg_id,author,timestamp,type,url,name\n")
        for msg in messages:
            for att in msg.attachment_refs:
                f.write(f'"{msg.msg_id}","{msg.author}","{msg.timestamp_berlin}","{att["type"]}","{att["url"]}","{att["name"]}"\n')
    
    print(f"Wrote attachments manifest to: {manifest_file}")
    
    # Generate and write stats
    stats = generate_stats(messages)
    stats_file = output_dir / "stats.json"
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    
    print(f"Wrote statistics to: {stats_file}")
    
    # Print summary
    print("\n" + "="*60)
    print("EXTRACTION SUMMARY")
    print("="*60)
    print(f"Total Messages: {stats['total_messages']}")
    print(f"Date Range: {stats['date_range']}")
    print(f"Total Authors: {stats['total_authors']}")
    print(f"Messages with Attachments: {stats['messages_with_attachments']}")
    print(f"Messages with Links: {stats['messages_with_links']}")
    print(f"\nTop Authors:")
    for author, count in list(stats['top_authors'].items())[:5]:
        print(f"  {author}: {count}")
    print(f"\nKey Term Frequencies:")
    for term, count in stats['key_term_frequencies'].items():
        if count > 0:
            print(f"  {term}: {count}")
    print("="*60)
    
    return output_dir


if __name__ == "__main__":
    output_dir = main()
    print(f"\nAll extraction artifacts saved to: {output_dir}")
