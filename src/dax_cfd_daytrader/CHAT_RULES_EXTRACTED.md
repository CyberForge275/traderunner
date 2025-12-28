# Extracted Rules from Discord Chat

This document lists all trading rules extracted from the Discord chat export, formalized with complete citations.

## Format Legend

- **[CHAT]**: Source message reference (msg_id | author | timestamp)
- **[QUOTE]**: Direct quote from message (max 25 words)
- **[RULE]**: Formal rule statement
- **[PARAM]**: Parameter name, value, and unit
- **[SETUP]**: Applicable setup (1-5 or Global)
- **[CLASSIFICATION]**: new_rule | clarification | example_only | contradiction
- **[CONFIDENCE]**: HIGH | MEDIUM | LOW

---

## Rule Categories

| Rule Type | Count | Description |
|-----------|-------|-------------|
| `BREAKEVEN` | 5 | Breakeven |
| `ENTRY_SIGNAL` | 3 | Entry Signal |
| `ORDER_ENTRY` | 1 | Order Entry |
| `REFILL` | 1 | Refill |
| `STOP_LOSS` | 20 | Stop Loss |
| `TAKE_PROFIT` | 3 | Take Profit |
| `VDAX_FILTER` | 31 | Vdax Filter |
| `ZONE_CALC` | 92 | Zone Calc |

---

## Breakeven

**Total Instances**: 5

**Unique Rules**: 3

### BREAKEVEN_001

**[RULE]** Move to BE after: 20 points

**[CHAT]** `msg_c4202a5d...` | groodoo | 2025-10-23T16:05:18+02:00

**[QUOTE]** "damit wäre man auf be ausgestoppt worden (nach 20 punkten sl -> be, 40 wurden nicht erreicht)..."

**[PARAM]** Move to BE after: 20 points

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** LOW

**Instances**: 1 occurrences in chat

---

### BREAKEVEN_002

**[RULE]** Move to BE after: 10 points

**[CHAT]** `msg_3fe9a4b6...` | rono2910 | 2025-10-23T22:01:47+02:00

**[QUOTE]** "@meteora360#0doch, da der trade nach 10 punkten über der zweiten zone eingestoppt wird. du bereitest..."

**[PARAM]** Move to BE after: 10 points

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** LOW

**Instances**: 1 occurrences in chat

---

### BREAKEVEN_003

**[RULE]** Move to BE after: 100 points

**[CHAT]** `msg_4bc03bd2...` | georg0638 | 2025-11-27T08:23:36+01:00

**[QUOTE]** " notiert zwar bei 18. wir lassen die ersten zonen bei 100 punkte mit der möglichkeit bei einer umkeh..."

**[PARAM]** Move to BE after: 100 points

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** HIGH

**Instances**: 3 occurrences in chat

---

## Entry Signal

**Total Instances**: 3

**Unique Rules**: 1

### ENTRY_SIGNAL_001

**[RULE]** Entry signal: M15 reversal candle required

**[CHAT]** `msg_f7411785...` | georg0638 | 2025-10-23T12:16:29+02:00

**[QUOTE]** " unten nach oben durchkreuzt,
eine abgeschlossene 15-minuten-umkehrkerze bildet
und innerhalb oder o..."

**[PARAM]** Entry signal: M15 reversal candle required

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** HIGH

**Instances**: 3 occurrences in chat

---

## Order Entry

**Total Instances**: 1

**Unique Rules**: 1

### ORDER_ENTRY_001

**[RULE]** Limit order: 0 points über zone

**[CHAT]** `msg_3d69b3da...` | meteora360 | 2025-10-24T06:58:21+02:00

**[QUOTE]** "öst dort den alarm aus. würde ich nun direkt eine limit-order 10 punkte über die zone legen, würde d..."

**[PARAM]** Limit order: 0 points über zone

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** LOW

**Instances**: 1 occurrences in chat

---

## Refill

**Total Instances**: 1

**Unique Rules**: 1

### REFILL_001

**[RULE]** Second position: Double size

**[CHAT]** `msg_f7411785...` | georg0638 | 2025-10-23T12:16:29+02:00

**[QUOTE]** "d innerhalb oder oberhalb der zone schließt.

die zweite position wird mit der doppelten kontrakthöh..."

**[PARAM]** Second position: Double size

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** LOW

**Instances**: 1 occurrences in chat

---

## Stop Loss

**Total Instances**: 20

**Unique Rules**: 1

### STOP_LOSS_001

**[RULE]** Stop Loss: 5 points

**[CHAT]** `msg_155983c5...` | georg0638 | 2025-10-22T13:45:57+02:00

**[QUOTE]** "s 50 punkte über bzw. unter der ersten zone.

der stop-loss wird 35 punkte über bzw. unter der zweit..."

**[PARAM]** Stop Loss: 5 points

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** HIGH

**Instances**: 20 occurrences in chat

---

## Take Profit

**Total Instances**: 3

**Unique Rules**: 1

### TAKE_PROFIT_001

**[RULE]** Profit target: 0 points

**[CHAT]** `msg_2f872995...` | georg0638 | 2025-10-23T13:03:25+02:00

**[QUOTE]** "gewinnziel 40 punkte erreicht . das übliche gewinnziel liegt bei 30-40..."

**[PARAM]** Profit target: 0 points

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** HIGH

**Instances**: 3 occurrences in chat

---

## Vdax Filter

**Total Instances**: 31

**Unique Rules**: 8

### VDAX_FILTER_001

**[RULE]** VDAX value: 7

**[CHAT]** `msg_155983c5...` | georg0638 | 2025-10-22T13:45:57+02:00

**[QUOTE]** "1

➡️ eröffnung: −24 punkte (kleines down-gap)
➡️ vdax-new: 17

🔻 short-setup
beschreibung    berech..."

**[PARAM]** VDAX value: 7

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** HIGH

**Instances**: 5 occurrences in chat

---

### VDAX_FILTER_002

**[RULE]** VDAX value: 8

**[CHAT]** `msg_18fa4fa2...` | georg0638 | 2025-10-23T08:29:06+02:00

**[QUOTE]** "lso mit einem leichten up-gap von 24 punkten.
der vdax-new notiert bei 18.
die handelszonen bleiben ..."

**[PARAM]** VDAX value: 8

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** HIGH

**Instances**: 4 occurrences in chat

---

### VDAX_FILTER_003

**[RULE]** VDAX value: 9

**[CHAT]** `msg_c25333ca...` | georg0638 | 2025-11-05T08:21:48+01:00

**[QUOTE]** "g german 40    23.843

➡️ down-gap: −41 punkte
➡️ vdax-new: 19 (gestiegen)
➡️ marktumfeld: volatil, ..."

**[PARAM]** VDAX value: 9

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** HIGH

**Instances**: 5 occurrences in chat

---

### VDAX_FILTER_004

**[RULE]** VDAX value: 0

**[CHAT]** `msg_b80573d7...` | georg0638 | 2025-11-07T08:33:27+01:00

**[QUOTE]** "
was einem up-gap von 33 punkten entspricht.

der vdax-new stieg auf 20 und signalisiert eine zunehm..."

**[PARAM]** VDAX value: 0

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** HIGH

**Instances**: 9 occurrences in chat

---

### VDAX_FILTER_005

**[RULE]** VDAX value: 2

**[CHAT]** `msg_dac5c39e...` | georg0638 | 2025-11-07T18:43:05+01:00

**[QUOTE]** "ät erneut steigend

• handelsspanne: 387 punkte
• vdax: +5,83 % auf 22

trades heute:
→ am morgen zw..."

**[PARAM]** VDAX value: 2

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** MEDIUM

**Instances**: 2 occurrences in chat

---

### VDAX_FILTER_006

**[RULE]** VDAX value: 20

**[CHAT]** `msg_225b92a1...` | georg0638 | 2025-11-11T09:12:30+01:00

**[QUOTE]** " zweite zone beträgt weitere 50 punkte. liegt der vdax-new hingegen unter 20, so umfasst die erste z..."

**[PARAM]** VDAX value: 20

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** LOW

**Instances**: 1 occurrences in chat

---

### VDAX_FILTER_007

**[RULE]** VDAX value: 5

**[CHAT]** `msg_5e66d2eb...` | muph82 | 2025-11-12T10:11:12+01:00

**[QUOTE]** "da vdax unter 20 mit 75. ausgehend von 24199...."

**[PARAM]** VDAX value: 5

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** HIGH

**Instances**: 4 occurrences in chat

---

### VDAX_FILTER_008

**[RULE]** VDAX value: 3

**[CHAT]** `msg_2049e439...` | georg0638 | 2025-11-19T08:41:42+01:00

**[QUOTE]** "as einem down-gap von 36 punkten entspricht.

der vdax-new notiert bei 23, also auf einem erhöhten n..."

**[PARAM]** VDAX value: 3

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** LOW

**Instances**: 1 occurrences in chat

---

## Zone Calc

**Total Instances**: 92

**Unique Rules**: 16

### ZONE_CALC_001

**[RULE]** Zone offset: 75 points über

**[CHAT]** `msg_155983c5...` | georg0638 | 2025-10-22T13:45:57+02:00

**[QUOTE]** "szonen bleiben wie gestern:

die erste zone liegt 75 punkte über dem schlusskurs (22 h) bzw. 75 punk..."

**[PARAM]** Zone offset: 75 points über

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** HIGH

**Instances**: 9 occurrences in chat

---

### ZONE_CALC_002

**[RULE]** Zone offset: 75 points unter

**[CHAT]** `msg_155983c5...` | georg0638 | 2025-10-22T13:45:57+02:00

**[QUOTE]** " liegt 75 punkte über dem schlusskurs (22 h) bzw. 75 punkte unter dem eröffnungskurs.

die zweite zo..."

**[PARAM]** Zone offset: 75 points unter

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** HIGH

**Instances**: 7 occurrences in chat

---

### ZONE_CALC_003

**[RULE]** Zone offset: 50 points über

**[CHAT]** `msg_155983c5...` | georg0638 | 2025-10-22T13:45:57+02:00

**[QUOTE]** "em eröffnungskurs.

die zweite zone liegt jeweils 50 punkte über bzw. unter der ersten zone.

der st..."

**[PARAM]** Zone offset: 50 points über

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** HIGH

**Instances**: 13 occurrences in chat

---

### ZONE_CALC_004

**[RULE]** Zone offset: 35 points über

**[CHAT]** `msg_155983c5...` | georg0638 | 2025-10-22T13:45:57+02:00

**[QUOTE]** "r bzw. unter der ersten zone.

der stop-loss wird 35 punkte über bzw. unter der zweiten zone gesetzt..."

**[PARAM]** Zone offset: 35 points über

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** HIGH

**Instances**: 13 occurrences in chat

---

### ZONE_CALC_005

**[RULE]** Zone offset: 10 points über

**[CHAT]** `msg_dd59f34c...` | rono2910 | 2025-10-23T16:00:44+02:00

**[QUOTE]** "@meteora360#0korrekt, du lässt dich 10 punkte über/unter der zweiten zone einstoppen...."

**[PARAM]** Zone offset: 10 points über

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** HIGH

**Instances**: 3 occurrences in chat

---

### ZONE_CALC_006

**[RULE]** Zone offset: 11 points über

**[CHAT]** `msg_517f7747...` | meteora360 | 2025-10-23T16:14:28+02:00

**[QUOTE]** "@rono2910#0wenn die kerze 11 punkte über der 2. zone schließt, erfolgt kein trade?..."

**[PARAM]** Zone offset: 11 points über

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** LOW

**Instances**: 1 occurrences in chat

---

### ZONE_CALC_007

**[RULE]** Zone offset: 35 points unter

**[CHAT]** `msg_5760fe10...` | georg0638 | 2025-10-24T08:30:26+02:00

**[QUOTE]** "one liegt 50 punkte darunter.

der stop-loss wird 35 punkte unter der zweiten zone gesetzt.

die sho..."

**[PARAM]** Zone offset: 35 points unter

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** HIGH

**Instances**: 5 occurrences in chat

---

### ZONE_CALC_008

**[RULE]** Zone offset: 100 points unter

**[CHAT]** `msg_5d848d07...` | georg0638 | 2025-10-27T08:21:53+01:00

**[QUOTE]** " werden die zonen angepasst:

long-seite:

zone = 100 punkte unter dem eröffnungskurs

zone = 50 pun..."

**[PARAM]** Zone offset: 100 points unter

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** HIGH

**Instances**: 15 occurrences in chat

---

### ZONE_CALC_009

**[RULE]** Zone offset: 50 points unter

**[CHAT]** `msg_5d848d07...` | georg0638 | 2025-10-27T08:21:53+01:00

**[QUOTE]** "one = 100 punkte unter dem eröffnungskurs

zone = 50 punkte unter der ersten zone

stop-loss = 35 pu..."

**[PARAM]** Zone offset: 50 points unter

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** HIGH

**Instances**: 3 occurrences in chat

---

### ZONE_CALC_010

**[RULE]** Zone offset: 5 points über

**[CHAT]** `msg_d83e9c34...` | georg0638 | 2025-10-29T08:45:34+01:00

**[QUOTE]** "gskurs um 8:00 uhr liegt bei 24 260 punkten, also 5 punkte über dem schlusskurs vom vortag (22:00 uh..."

**[PARAM]** Zone offset: 5 points über

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** LOW

**Instances**: 1 occurrences in chat

---

### ZONE_CALC_011

**[RULE]** Zone offset: 100 points über

**[CHAT]** `msg_b80573d7...` | georg0638 | 2025-11-07T08:33:27+01:00

**[QUOTE]** "andel werden wie folgt gesetzt:

1. zone (short): 100 punkte über dem eröffnungskurs

1. zone (long)..."

**[PARAM]** Zone offset: 100 points über

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** HIGH

**Instances**: 15 occurrences in chat

---

### ZONE_CALC_012

**[RULE]** Zone offset: 10 points unter

**[CHAT]** `msg_da514022...` | georg0638 | 2025-11-07T20:13:49+01:00

**[QUOTE]** "n: long: 10 punkte oberhalb der long-zone. short: 10 punkte unterhalb der short-zone. order nur ausf..."

**[PARAM]** Zone offset: 10 points unter

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** HIGH

**Instances**: 3 occurrences in chat

---

### ZONE_CALC_013

**[RULE]** Zone offset: 395 points über

**[CHAT]** `msg_258f86c4...` | georg0638 | 2025-11-10T10:39:05+01:00

**[QUOTE]** "tatsache, dass der dax-schlusskurs vom freitag um 395 punkte überschritten wurde. dieses sehr weite ..."

**[PARAM]** Zone offset: 395 points über

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** LOW

**Instances**: 1 occurrences in chat

---

### ZONE_CALC_014

**[RULE]** Zone offset: 42 points unter

**[CHAT]** `msg_7903129d...` | dervieltrader | 2025-11-13T10:48:05+01:00

**[QUOTE]** "inem einstieg richtig gelegen habe. einstieg long 42 punkte unterhalb der ersten zohne......."

**[PARAM]** Zone offset: 42 points unter

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** LOW

**Instances**: 1 occurrences in chat

---

### ZONE_CALC_015

**[RULE]** Zone offset: 20 points unter

**[CHAT]** `msg_293bf232...` | georg0638 | 2025-11-17T14:01:52+01:00

**[QUOTE]** "eübte trader. nach dem einstieg von svend einfach 20 punkte unter dem einstieg long eine gegenpositi..."

**[PARAM]** Zone offset: 20 points unter

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** LOW

**Instances**: 1 occurrences in chat

---

### ZONE_CALC_016

**[RULE]** Zone offset: 150 points über

**[CHAT]** `msg_352909cf...` | meeloo8 | 2025-11-21T11:20:10+01:00

**[QUOTE]** "kte über dem open und die zweite zone short liegt 150 punkte über dem open. wir haben heute kein dop..."

**[PARAM]** Zone offset: 150 points über

**[SETUP]** Global (appears in general trading context)

**[CLASSIFICATION]** clarification (provides specific parameter value)

**[CONFIDENCE]** LOW

**Instances**: 1 occurrences in chat

---


---

*Generated from Discord chat export analysis*  
*Total Rules: 156*  
*Unique Rules: 32*
