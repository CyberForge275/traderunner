#!/usr/bin/env python3
"""
Extract structured text from FDAX-Regelwerk PDF.

Extracts:
- Full text content
- Page-by-page breakdown
- Tables (if any)
- Structure analysis
"""
import pdfplumber
from pathlib import Path
import json
import re

def extract_pdf_content(pdf_path: Path, output_dir: Path):
    """Extract all content from PDF."""
    
    print(f"📖 Extracting PDF: {pdf_path.name}")
    print("=" * 60)
    
    results = {
        'metadata': {},
        'pages': [],
        'full_text': '',
        'tables': [],
        'structure_hints': []
    }
    
    with pdfplumber.open(pdf_path) as pdf:
        # Metadata
        results['metadata'] = {
            'total_pages': len(pdf.pages),
            'title': pdf.metadata.get('Title', 'Unknown'),
            'author': pdf.metadata.get('Author', 'Unknown'),
            'creation_date': pdf.metadata.get('CreationDate', 'Unknown')
        }
        
        print(f"\n📄 Metadata:")
        print(f"  Total Pages: {results['metadata']['total_pages']}")
        print(f"  Title: {results['metadata']['title']}")
        
        # Process each page
        full_text_parts = []
        
        for i, page in enumerate(pdf.pages, 1):
            print(f"\n📃 Processing page {i}/{len(pdf.pages)}...")
            
            # Extract text
            page_text = page.extract_text()
            
            if not page_text:
                print(f"  ⚠️  No text on page {i}")
                continue
            
            # Store page info
            page_info = {
                'page_num': i,
                'text': page_text,
                'char_count': len(page_text),
                'tables': []
            }
            
            # Extract tables
            tables = page.extract_tables()
            if tables:
                print(f"  ✓ Found {len(tables)} table(s)")
                page_info['tables'] = tables
                results['tables'].extend([{
                    'page': i,
                    'table_index': j,
                    'rows': len(table),
                    'data': table
                } for j, table in enumerate(tables)])
            
            # Detect structure hints
            lines = page_text.split('\n')
            for line in lines:
                # Detect headings (ALL CAPS, short lines)
                if line.isupper() and len(line) < 80 and len(line) > 3:
                    results['structure_hints'].append({
                        'page': i,
                        'type': 'heading',
                        'text': line
                    })
                
                # Detect numbered rules (e.g., "1.", "2.", "Regel 1:", etc.)
                if re.match(r'^\s*(Regel\s+)?\d+[\.:)]', line):
                    results['structure_hints'].append({
                        'page': i,
                        'type': 'numbered_rule',
                        'text': line[:100]  # First 100 chars
                    })
            
            results['pages'].append(page_info)
            full_text_parts.append(f"\n\n=== PAGE {i} ===\n\n{page_text}")
            
            print(f"  ✓ Extracted {len(page_text)} characters")
        
        results['full_text'] = '\n'.join(full_text_parts)
    
    # Save results
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # Save full text
    text_file = output_dir / 'regelwerk_full_text.txt'
    text_file.write_text(results['full_text'], encoding='utf-8')
    print(f"\n✅ Saved full text: {text_file}")
    
    # Save JSON
    json_file = output_dir / 'regelwerk_extracted.json'
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"✅ Saved JSON: {json_file}")
    
    # Save structure analysis
    structure_file = output_dir / 'regelwerk_structure.md'
    with open(structure_file, 'w', encoding='utf-8') as f:
        f.write(f"# FDAX-Regelwerk Structure Analysis\n\n")
        f.write(f"**Total Pages:** {results['metadata']['total_pages']}\n\n")
        
        if results['structure_hints']:
            f.write(f"## Detected Structure Hints ({len(results['structure_hints'])})\n\n")
            for hint in results['structure_hints']:
                f.write(f"- **Page {hint['page']}** [{hint['type']}]: {hint['text']}\n")
        
        if results['tables']:
            f.write(f"\n## Tables Found ({len(results['tables'])})\n\n")
            for table_info in results['tables']:
                f.write(f"- **Page {table_info['page']}** Table {table_info['table_index']}: {table_info['rows']} rows\n")
    
    print(f"✅ Saved structure: {structure_file}")
    
    # Summary
    print(f"\n📊 Summary:")
    print(f"  Pages processed: {len(results['pages'])}")
    print(f"  Total characters: {len(results['full_text']):,}")
    print(f"  Tables found: {len(results['tables'])}")
    print(f"  Structure hints: {len(results['structure_hints'])}")
    
    return results


def main():
    pdf_path = Path('src/strategies/dax_cfd_daytrader/docs/sources/FDAX-Regelwerk-August-2025.pdf')
    output_dir = Path('src/strategies/dax_cfd_daytrader/docs/sources/extracted_regelwerk')
    
    if not pdf_path.exists():
        print(f"❌ PDF not found: {pdf_path}")
        return False
    
    extract_pdf_content(pdf_path, output_dir)
    return True


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
