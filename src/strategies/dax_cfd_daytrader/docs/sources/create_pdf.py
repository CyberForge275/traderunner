#!/usr/bin/env python3
"""
Create professional PDF from Discord chat using Pandoc.

Strategy:
1. Convert HTML to clean Markdown
2. Embed local images
3. Use Pandoc to create PDF with embedded images
"""
import re
import json
from pathlib import Path
from urllib.parse import urlparse
import subprocess
from datetime import datetime

def create_markdown_from_json(json_file: Path, charts_dir: Path) -> str:
    """Create professional Markdown from extracted JSON data."""
    
    # Load JSON
    with open(json_file) as f:
        data = json.load(f)
    
    messages = data['messages']
    
    # Start Markdown
    md = []
    md.append("---")
    md.append("title: DAX CFD Trading - Discord Chat Dokumentation")
    md.append("subtitle: Onlytraders - georg-diskussion")
    md.append(f"date: 27.11.2025 - 26.12.2025 ({data['total_messages']} Messages)")
    md.append("geometry: margin=2cm")
    md.append("toc: true")
    md.append("toc-depth: 2")
    md.append("---")
    md.append("")
    md.append("\\newpage")
    md.append("")
    
    # Group messages by date
    from collections import defaultdict
    messages_by_date = defaultdict(list)
    
    for msg in messages:
        if not msg['content'].strip():
            continue
        
        # Extract date from timestamp
        # Example: "Thu Nov 27 2025 18:03:39 GMT+0100"
        timestamp = msg['timestamp']
        try:
            # Simple date extraction
            parts = timestamp.split()
            if len(parts) >= 4:
                date_str = f"{parts[1]} {parts[2]} {parts[3]}"
                messages_by_date[date_str].append(msg)
        except:
            messages_by_date['Unknown'].append(msg)
    
    # Sort dates
    sorted_dates = sorted(messages_by_date.keys(), 
                         key=lambda x: datetime.strptime(x, '%b %d %Y') if x != 'Unknown' else datetime.min)
    
    # Write messages grouped by date
    for date in sorted_dates:
        md.append(f"# {date}")
        md.append("")
        
        for msg in messages_by_date[date]:
            # Author and timestamp
            md.append(f"**{msg['author']}** - *{msg['timestamp']}*")
            md.append("")
            
            # Content
            content = msg['content'].strip()
            # Escape special markdown characters in code blocks
            if '```' in content:
                md.append(content)
            else:
                # Replace newlines with markdown line breaks
                content = content.replace('\n', '  \n')
                md.append(content)
            md.append("")
            
            # Images
            if msg['images']:
                for img_url in msg['images']:
                    # Find local image
                    parsed = urlparse(img_url)
                    filename = Path(parsed.path).name.split('?')[0]
                    
                    for local_file in charts_dir.glob(f"*{filename}"):
                        # Relative path from docs/
                        rel_path = local_file.relative_to(charts_dir.parent)
                        md.append(f"![{local_file.name}]({rel_path})")
                        md.append("")
                        break
            
            md.append("---")
            md.append("")
    
    return '\n'.join(md)


def create_pdf_with_pandoc(markdown_file: Path, output_pdf: Path) -> bool:
    """Create PDF using Pandoc with embedded images."""
    
    try:
        print(f"Converting {markdown_file.name} to PDF with Pandoc...")
        
        result = subprocess.run(
            [
                'pandoc',
                str(markdown_file),
                '-o', str(output_pdf),
                '--pdf-engine=pdflatex',
                '--toc',
                '--toc-depth=2',
                '-V', 'geometry:margin=2cm',
                '-V', 'fontsize=10pt',
                '-V', 'linkcolor=blue',
                '--highlight-style=tango'
            ],
            capture_output=True,
            timeout=180,
            cwd=markdown_file.parent  # Important for relative image paths
        )
        
        if result.returncode == 0:
            print(f"✅ PDF created successfully!")
            return True
        else:
            print(f"❌ Pandoc error:")
            print(result.stderr.decode())
            
            # Try without images if pdflatex fails
            print("\n⚠️ Trying without embedded images...")
            result2 = subprocess.run(
                [
                    'pandoc',
                    str(markdown_file),
                    '-o', str(output_pdf),
                    '--toc',
                    '--toc-depth=2',
                    '-V', 'geometry:margin=2cm',
                    '-V', 'fontsize=10pt'
                ],
                capture_output=True,
                timeout=180
            )
            
            if result2.returncode == 0:
                print(f"✅ PDF created (without embedded images)")
                return True
            else:
                print(f"❌ Also failed: {result2.stderr.decode()}")
                return False
    
    except subprocess.TimeoutExpired:
        print("❌ Timeout during PDF creation")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    # Paths
    base_dir = Path('src/strategies/dax_cfd_daytrader/docs/sources')
    json_file = base_dir / 'discord_chat_extracted.json'
    charts_dir = base_dir / 'charts'
    
    # Output files
    markdown_file = base_dir / 'discord_chat_documentation.md'
    output_pdf = Path('src/strategies/dax_cfd_daytrader/docs/Discord_Chat_DAX_Trading_Dokumentation.pdf')
    
    print("📖 Discord Chat → PDF Konvertierung (Pandoc)")
    print("=" * 60)
    
    # Create Markdown from JSON
    print(f"\n1. Creating Markdown from JSON...")
    markdown_content = create_markdown_from_json(json_file, charts_dir)
    
    print(f"   ✓ Markdown created ({len(markdown_content) / 1024:.1f} KB)")
    
    # Save Markdown
    print(f"\n2. Saving Markdown...")
    markdown_file.write_text(markdown_content, encoding='utf-8')
    print(f"   ✓ Saved: {markdown_file}")
    
    # Convert to PDF
    print(f"\n3. Converting to PDF with Pandoc...")
    if create_pdf_with_pandoc(markdown_file, output_pdf):
        # Get file size
        size_mb = output_pdf.stat().st_size / (1024 * 1024)
        print(f"\n✅ PDF erfolgreich erstellt!")
        print(f"   Location: {output_pdf}")
        print(f"   Size: {size_mb:.2f} MB")
        
        print(f"\n📄 Markdown-Version auch verfügbar:")
        print(f"   {markdown_file}")
        
        return True
    else:
        print(f"\n❌ PDF creation failed")
        print(f"   Markdown saved: {markdown_file}")
        print(f"   Sie können das Markdown manuell zu PDF konvertieren")
        return False


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
