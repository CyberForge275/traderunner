#!/usr/bin/env python3
"""
Discord Chat Topic Clustering and Rule Extraction
Analyzes extracted Discord messages to identify thematic blocks and extract trading rules
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Set
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class TopicBlock:
    """Represents a thematic block of messages"""
    topic_id: str
    topic_name: str
    msg_start_id: str
    msg_end_id: str
    message_count: int
    date_range: str
    keywords: List[str]
    messages: List[Dict]  # List of message dicts
    

def load_messages(jsonl_path: Path) -> List[Dict]:
    """Load messages from JSONL file"""
    messages = []
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            messages.append(json.loads(line))
    return messages


def contains_keywords(text: str, keywords: List[str], require_all: bool = False) -> bool:
    """Check if text contains keywords (case-insensitive)"""
    text_lower = text.lower()
    if require_all:
        return all(kw.lower() in text_lower for kw in keywords)
    else:
        return any(kw.lower() in text_lower for kw in keywords)


def identify_topic_blocks(messages: List[Dict]) -> List[TopicBlock]:
    """
    Segment messages into thematic blocks based on content analysis
    """
    
    # Define topic patterns with keywords
    topic_patterns = {
        'SETUP_ZONES': {
            'keywords': ['zone', 'zone 1', 'zone 2', 'erste zone', 'zweite zone', 'aktionszone'],
            'name': 'Setup Entry Zones & Zone Calculation'
        },
        'SETUP_LONG': {
            'keywords': ['long', 'longeinstieg', 'long-position', 'long-zone'],
'name': 'Long Setups & Entries'
        },
        'SETUP_SHORT': {
            'keywords': ['short', 'shorteinstieg', 'short-position', 'short-zone'],
            'name': 'Short Setups & Entries'
        },
        'VDAX_FILTER': {
            'keywords': ['vdax', 'vdax-new', 'volatilität'],
            'name': 'VDAX Volatility Filter'
        },
        'PRICE_MOVEMENT': {
            'keywords': ['±1%', '+/-1%', 'prozent', 'bewegung'],
            'name': 'Price Movement Filter (±1%)'
        },
        'NEWS_EVENTS': {
            'keywords': ['news', 'nachrichten', 'termine', 'wirtschafts', 'fed', 'zinsen'],
            'name': 'News & Economic Events Filter'
        },
        'TIME_SESSIONS': {
            'keywords': ['8:00', '9:00', '13:00', '14:45', '15:30', '22:00', 'uhr', 'eröffnung', 'schluss'],
            'name': 'Trading Hours & Sessions'
        },
        'PAUSE_FLATTEN': {
            'keywords': ['pause', '13:00-14:45', 'flatten', 'position schließen'],
            'name': 'Pause Times & Flatten Rules'
        },
        'STOP_LOSS': {
            'keywords': ['stop', 'stop-loss', 'sl', 'stopp', '35 punkte'],
            'name': 'Stop Loss Rules & Management'
        },
        'TAKE_PROFIT': {
            'keywords': ['gewinn', 'profit', 'tp', '30 punkte', '40 punkte', 'gewinnziel'],
            'name': 'Take Profit & Profit Targets'
        },
        'BREAKEVEN': {
            'keywords': ['breakeven', 'be', 'auf null', '20 punkte'],
            'name': 'Breakeven Rules'
        },
        'TRAILING': {
            'keywords': ['trailing', 'nachziehen', 'trailing stop'],
            'name': 'Trailing Stop Rules'
        },
        'POSITION_SIZING': {
            'keywords': ['kontrakt', 'positionsgröße', 'einsatz', 'position size'],
            'name': 'Position Sizing & Risk Per Trade'
        },
        'MAX_TRADES': {
            'keywords': ['max', 'maximum', 'anzahl trades', 'pro tag'],
            'name': 'Maximum Trades Per Day'
        },
        'MAX_LOSS': {
            'keywords': ['max loss', 'tagesverlust', 'verlustlimit'],
            'name': 'Maximum Daily Loss Limit'
        },
        'REFILL_RULES': {
            'keywords': ['refill', 'nachkauf', 'zweite position', 'doppelte'],
            'name': 'Refill & Position Adding Rules'
        },
        'ORDER_TYPES': {
            'keywords': ['limit', 'market', 'stop order', '10 punkte über', '10 punkte unter'],
            'name': 'Order Types (Market/Limit/Stop)'
        },
        'SPREAD_COSTS': {
            'keywords': ['spread', 'kosten', 'gebühr', 'slippage', '1,4 punkte'],
            'name': 'Spread & Transaction Costs'
        },
        'INSTRUMENTS': {
            'keywords': ['cfd', 'fdax', 'fdxm', 'german 40', 'ig markets'],
            'name': 'Instruments (CFD/FDAX/FDXM)'
        },
        'US_CORRELATION': {
            'keywords': ['dow', 'djia', 'us-markt', 'futures', 'korrelation', '14:30', '15:30'],
            'name': 'US Market Correlation & Afternoon Trading'
        },
        'REVERSAL_PATTERNS': {
            'keywords': ['umkehrkerze', 'reversal', 'engulfing', 'm15', '15-minuten'],
            'name': 'Reversal Patterns & Candlestick Signals'
        },
        'GAP_HANDLING': {
            'keywords': ['gap', 'lücke', 'overnight', 'eröffnungskurs'],
            'name': 'Gap Handling & Overnight Gaps'
        },
        'BACKTEST_DATA': {
            'keywords': ['backtest', 'historical', 'daten', 'eodhd', 'test'],
            'name': 'Backtesting & Historical Data'
        },
        'TIMEZONE': {
            'keywords': ['timezone', 'zeitzone', 'utc', 'berlin', 'europa'],
            'name': 'Timezone & Session Timing'
        },
        'ARTIFACTS': {
            'keywords': ['chart', 'screenshot', 'bild', 'pdf', 'regelwerk'],
            'name': 'Charts & Documentation Artifacts'
        },
        'BUGS_ISSUES': {
            'keywords': ['fehler', 'bug', 'problem', 'fix'],
            'name': 'Known Issues & Debugging'
        },
    }
    
    # Track messages by topic
    topic_messages = defaultdict(list)
    
    # First pass: classify each message into one or more topics
    for msg in messages:
        content = msg['content_text']
        if not content:
            continue
            
        for topic_id, pattern in topic_patterns.items():
            if contains_keywords(content, pattern['keywords']):
                topic_messages[topic_id].append(msg)
    
    # Create topic blocks
    blocks = []
    for topic_id, msgs in topic_messages.items():
        if not msgs:
            continue
            
        pattern = topic_patterns[topic_id]
        
        # Get date range
        timestamps = [m['timestamp_berlin'] for m in msgs]
        date_range = f"{timestamps[0]} to {timestamps[-1]}"
        
        block = TopicBlock(
            topic_id=topic_id,
            topic_name=pattern['name'],
            msg_start_id=msgs[0]['msg_id'],
            msg_end_id=msgs[-1]['msg_id'],
            message_count=len(msgs),
            date_range=date_range,
            keywords=pattern['keywords'],
            messages=msgs
        )
        blocks.append(block)
    
    # Sort by message count (most relevant first)
    blocks.sort(key=lambda b: b.message_count, reverse=True)
    
    return blocks


def extract_rules_from_messages(messages: List[Dict]) -> List[Dict]:
    """
    Extract trading rules from message content
    Returns list of rule dicts with metadata
    """
    
    rules = []
    
    # Rule extraction patterns
    patterns = [
        # Zone calculations
        {
            'pattern': r'(\d+)\s*punkte\s+(über|unter)',
            'rule_type': 'ZONE_CALC',
            'extract_func': lambda m: f"Zone offset: {m.group(1)} points {m.group(2)}"
        },
        # Stop loss
        {
            'pattern': r'stop[-\s]?loss.{0,20}(\d+)\s*punkte',
            'rule_type': 'STOP_LOSS',
            'extract_func': lambda m: f"Stop Loss: {m.group(1)} points"
        },
        # Take profit
        {
            'pattern': r'gewinnziel.{0,20}(\d+)[-\s]?(\d+)?\s*punkte',
            'rule_type': 'TAKE_PROFIT',
            'extract_func': lambda m: f"Profit target: {m.group(1)}{'-' + m.group(2) if m.group(2) else ''} points"
        },
        # Breakeven
        {
            'pattern': r'(?:nach|bei)\s*(\d+)\s*punkte.{0,30}(?:be|breakeven|auf null)',
            'rule_type': 'BREAKEVEN',
            'extract_func': lambda m: f"Move to BE after: {m.group(1)} points"
        },
        # VDAX threshold
        {
            'pattern': r'vdax.{0,20}(\d+)',
            'rule_type': 'VDAX_FILTER',
            'extract_func': lambda m: f"VDAX value: {m.group(1)}"
        },
        # Limit order offset
        {
            'pattern': r'limit.{0,20}(\d+)\s*punkte\s+(über|unter)',
            'rule_type': 'ORDER_ENTRY',
            'extract_func': lambda m: f"Limit order: {m.group(1)} points {m.group(2)} zone"
        },
        # Refill position size
        {
            'pattern': r'(?:zweite|2\.)\s*position.{0,30}doppelte',
            'rule_type': 'REFILL',
            'extract_func': lambda m: "Second position: Double size"
        },
        # Reversal candle requirement
        {
            'pattern': r'(?:m15|15[-\s]?minuten).{0,30}umkehrkerze',
            'rule_type': 'ENTRY_SIGNAL',
            'extract_func': lambda m: "Entry signal: M15 reversal candle required"
        },
    ]
    
    for msg in messages:
        content = msg['content_text'].lower()
        if not content:
            continue
        
        for pattern_def in patterns:
            matches = re.finditer(pattern_def['pattern'], content, re.IGNORECASE)
            for match in matches:
                rule_text = pattern_def['extract_func'](match)
                
                rules.append({
                    'rule_type': pattern_def['rule_type'],
                    'rule_text': rule_text,
                    'source_msg_id': msg['msg_id'],
                    'source_author': msg['author'],
                    'source_timestamp': msg['timestamp_berlin'],
                    'source_snippet': content[max(0, match.start()-50):min(len(content), match.end()+50)],
                    'classification': 'extracted',  # Will be refined later
                })
    
    return rules


def main():
    """Main analysis pipeline"""
    
    # Find latest extraction
    base_dir = Path("/home/mirko/data/workspace/droid/traderunner/src/strategies/dax_cfd_daytrader/docs")
    extract_dir = base_dir / "artifacts" / "chat_extract"
    
    # Get latest run directory
    run_dirs = sorted(extract_dir.glob("*"))
    if not run_dirs:
        print("No extraction runs found!")
        return
    
    latest_run = run_dirs[-1]
    jsonl_file = latest_run / "discord_messages.jsonl"
    
    print(f"Analyzing: {jsonl_file}")
    
    # Load messages
    messages = load_messages(jsonl_file)
    print(f"Loaded {len(messages)} messages")
    
    # Identify topic blocks
    print("\nIdentifying topic blocks...")
    blocks = identify_topic_blocks(messages)
    
    print(f"\nFound {len(blocks)} topic blocks:")
    for block in blocks:
        print(f"  {block.topic_id:25s} | {block.message_count:4d} msgs | {block.topic_name}")
    
    # Save topic blocks
    blocks_file = latest_run / "topic_blocks.json"
    with open(blocks_file, 'w', encoding='utf-8') as f:
        blocks_data = []
        for block in blocks:
            blocks_data.append({
                'topic_id': block.topic_id,
                'topic_name': block.topic_name,
                'msg_start_id': block.msg_start_id,
                'msg_end_id': block.msg_end_id,
                'message_count': block.message_count,
                'date_range': block.date_range,
                'keywords': block.keywords,
                'message_ids': [m['msg_id'] for m in block.messages]
            })
        json.dump(blocks_data, f, indent=2, ensure_ascii=False)
    
    print(f"\nSaved topic blocks to: {blocks_file}")
    
    # Extract rules
    print("\nExtracting rules...")
    rules = extract_rules_from_messages(messages)
    
    print(f"Extracted {len(rules)} rule instances")
    
    # Group by rule type
    rules_by_type = defaultdict(list)
    for rule in rules:
        rules_by_type[rule['rule_type']].append(rule)
    
    print("\nRules by type:")
    for rule_type, rule_list in sorted(rules_by_type.items()):
        print(f"  {rule_type:20s}: {len(rule_list):3d} instances")
    
    # Save rules
    rules_file = latest_run / "extracted_rules.json"
    with open(rules_file, 'w', encoding='utf-8') as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)
    
    print(f"\nSaved extracted rules to: {rules_file}")
    
    return blocks, rules


if __name__ == "__main__":
    blocks, rules = main()
