---
description: Understanding and managing Antigravity agent memory and project history
---

# Agent Memory Architecture

This document explains how Antigravity maintains context and history across sessions, and how to optimize memory for your projects.

---

## 1. Automatic Memory Sources

### Conversation Summaries
Antigravity automatically maintains summaries of recent conversations (last ~20).  
**What's stored:**
- Conversation ID and title
- Creation and modification timestamps
- User objectives summary
- Key actions taken

**Limitations:**
- ~20 most recent conversations retained
- Summaries are condensed, not full transcripts
- Older conversations fade from memory

### Brain Folder Artifacts
Located at: `~/.gemini/antigravity/brain/<conversation-id>/`

**Structure per conversation:**
```
<conversation-id>/
├── task.md           # Task checklist for that session
├── implementation_plan.md  # Technical plans created
├── walkthrough.md    # Work summaries and proof
└── *.webp/*.png     # Screenshots and recordings
```

---

## 2. Persistent Memory (User-Controlled)

### Workflow Files
Place `.md` files in `.agent/workflows/` directory within any project.

**Format:**
```markdown
---
description: Short description of what this workflow covers
---

# Workflow Title

Your content here...
```

**Benefits:**
- ✅ Persists across ALL sessions
- ✅ Project-specific context
- ✅ Can be version controlled (git)
- ✅ Agent reads these when relevant

**Recommended workflows:**
- `project-context.md` - System architecture, key decisions
- `debugging-playbook.md` - Common issues and solutions
- `deployment-steps.md` - Production deployment procedures

### Project Documentation
Your `README.md`, `docs/`, and other markdown files are also referenced by Antigravity when exploring the codebase.

---

## 3. Memory Best Practices

### For Long-Running Projects

1. **Create project-context.md:**
   Document your system architecture, key decisions, and current focus areas.

2. **Update after major changes:**
   When architecture changes, update workflows to reflect new state.

3. **Use consistent terminology:**
   Antigravity learns your project vocabulary from docs.

### For Recurring Tasks

1. **Create specific workflows:**
   ```
   .agent/workflows/deploy-to-production.md
   .agent/workflows/add-new-strategy.md
   .agent/workflows/debug-ib-connection.md
   ```

2. **Include turbo annotations:**
   Add `// turbo` above steps safe to auto-run.

### For Context Recovery

After a fresh session, you can:
- Say: "Read project-context workflow"
- Say: "What was I working on yesterday?" (uses conversation summaries)
- Say: "Check the brain folder for recent plans"

---

## 4. Brain Folder Management

### Viewing History
```bash
# List all conversation folders
ls -la ~/.gemini/antigravity/brain/

# See artifacts from a specific conversation
ls -la ~/.gemini/antigravity/brain/<conversation-id>/

# View a plan from a past session
cat ~/.gemini/antigravity/brain/<id>/implementation_plan.md
```

### Cleanup (Optional)
Old brain folders can be deleted if no longer needed:
```bash
# Remove conversations older than 30 days (be careful!)
find ~/.gemini/antigravity/brain -type d -mtime +30 -exec rm -rf {} +
```

---

## 5. Conversation ID Mapping

Your recent conversation IDs and their purposes:

| ID | Topic |
|----|-------|
| `955367b9-...` | Fix Trading Dashboard Logs |
| `eb15cf8d-...` | Documentation Review and Update |
| `e489625c-...` | InsideBar Simulation Setup |
| `50070c6b-...` | Build Pipeline Sanity Checks |
| `8f5ab637-...` | Integrate Trading Projects |

_(This table was generated from your current brain folder)_

---

## 6. Triggering Memory Recall

### Explicit Commands
- `/project-context` - Load the project context workflow
- "Review my project architecture"
- "What changes did we make to the dashboard?"

### Automatic Triggering
Antigravity will automatically:
- Read workflow files when you mention topics in their `description`
- Reference conversation summaries for recent context
- Check brain artifacts when you ask about past work

---

## 7. Creating an "Agent with Memories"

For a truly persistent agent experience:

1. **Maintain project-context.md** - Your source of truth
2. **Create topic-specific workflows** - For deep procedural knowledge
3. **Update docs regularly** - Agent reads your README and docs
4. **Reference past conversations** - "Continue from where we left off with X"

The combination of:
- ✅ Automatic conversation summaries
- ✅ Brain folder artifacts
- ✅ Workflow files (persistent)
- ✅ Project documentation

Creates an agent that "remembers" your project across all sessions.
