# Lost Hiker – Developer Workflow (v0.1 “Discordant Forest”)

This doc describes **how to work on Lost Hiker**, not what the game is about.  
It covers:

- Where the **canonical design docs** live.
- How to use **ChatGPT** (with multiple focused chats).
- How to use **Cursor** inside the repo.
- How to keep decisions and implementation from drifting apart.

The goal is simple: **ship v0.1 “Discordant Forest” without losing your mind.**

---

## 1. Canonical Sources

There are exactly **two** design documents that matter:

- `docs/design/Lost Hiker - Master Design Doc.md`  
  → Full game master vision: all zones, long-term systems, dragon, island town, etc. :contentReference[oaicite:1]{index=1}  

- `docs/design/Lost Hiker - Design Doc 0.1 _Discordant Forest_.md`  
  → The **only** design doc that defines v0.1 scope (Forest-only, Forest Act I, Echo, Astrin, survival loop, curses UI). :contentReference[oaicite:2]{index=2}  

**Hierachy when things conflict:**

1. **Code reality** (what actually runs).
2. **0.1 Design Doc** (what v0.1 should converge toward).
3. **Master Design Doc** (future ambitions).

When you change scope or behavior, update the **0.1 design doc**.  
When you invent future-zone nonsense, update the **Master** doc.

---

## 2. High-Level Workflow

### TL;DR Loop

1. Decide **what area** you’re working on (Forest content, Echo/Astrin, UI, systems).
2. Open the right **ChatGPT topic chat** (see next section).
3. Ask for:
   - A small set of **concrete tasks**.
   - Any needed design clarification from the 0.1 doc.
4. Use **Cursor** inside the repo to:
   - Run audits / searches.
   - Implement those tasks.
   - Get progress snapshots.
5. When decisions change:
   - Update the **0.1 design doc**.
   - Update the **Roadmap chat** with a short progress summary.

Rinse, repeat, don’t invent new tools unless you actually need them.

---

## 3. ChatGPT Structure (5 Chats)

Use **five** stable chats for Lost Hiker work:

### 3.1 Roadmap & Progress

**Chat name:** `Lost Hiker – Roadmap & Progress (Discordant Forest)`

Purpose:

- Central “project brain.”
- Track v0.1 scope, DONE/PARTIAL/NOT STARTED items, and next 3–7 tasks.
- Integrate:
  - Cursor repo summaries.
  - Design decisions from topic chats.
  - Changes to the 0.1 design doc.

Typical uses:

- “Here’s the latest Cursor audit, update the roadmap.”
- “I finished X and Y tasks—what’s the next 3 things that move v0.1 closest to shippable?”
- “I’m thinking of adding feature Z—tell me if that’s v0.1 or post-0.1.”

---

### 3.2 Forest Content

**Chat name:** `Lost Hiker – Forest Act I: Landmarks, Encounters, Quests`

Purpose:

- Design and refine **Forest content only**:
  - Landmarks.
  - Creatures & encounters.
  - Micro-quests and small side quests.
  - How depth/time/season affect Forest play.

Typical uses:

- “Give me 2 new Forest landmarks that fit v0.1.”
- “I need 3 more creatures to hit the ~10 encounter target—design them.”
- “Turn this micro-event into a 3-step side quest.”

Output style:

- Markdown sections:
  - `## Landmarks`, `## Creatures & Encounters`, `## Micro-Quests`, `## Implied Tasks`.

---

### 3.3 Echo & Astrin

**Chat name:** `Lost Hiker – Echo & Astrin Tarrinae: NPCs, Rapport, Cozy/Vore`

Purpose:

- Define and refine **Echo** and **Astrin Tarrinae**:
  - Roles, arcs, and key scenes.
  - Rapport thresholds and unlocks.
  - Interactions with systems (camping, teas, HT radio, vore shelter).

Typical uses:

- “Design a high-rapport camp-at-Glade scene with Astrin.”
- “Refine Echo’s HT tutorial sequence into 2–3 scenes.”
- “Propose 1 co-vore scene (Echo + player + Astrin) that respects v0.1 tone and constraints.”

Output style:

- Markdown sections:
  - `## Echo`, `## Astrin Tarrinae`, `## Rapport Structure`, `## Implied Tasks`.

---

### 3.4 Curses UI & UX

**Chat name:** `Lost Hiker – Curses UI & UX`

Purpose:

- Design and refine the **terminal UI**, not the game systems:
  - Screen layouts (main menu, Glade, explore, encounter, camp).
  - Status bar content.
  - Borders, drips, and palettes.
  - Input / keybindings.

Typical uses:

- “Propose a curses layout for the Glade screen using status, main text, and options.”
- “Design how bellied mode should look in curses without becoming unreadable.”
- “We need a clearer encounter screen—restructure the output layout.”

Output style:

- Markdown sections:
  - `## Screen Types`, `## Layout & Regions`, `## Interaction & Input`, `## Implied Tasks`.

---

### 3.5 Systems & Survival

**Chat name:** `Lost Hiker – Systems & Survival: Time, Travel, Weather`

Purpose:

- Work on **mechanical systems**:
  - Hunger/stamina tuning.
  - Time-of-day and day/night behavior.
  - Travel and fast travel (Forest Act I).
  - Minimal weather behavior (if included in v0.1).

Typical uses:

- “Current stamina feels too punishing—suggest a tuning pass.”
- “We need fast travel that’s actually usable in Act I—refine Wayfinding/Kirin requirements.”
- “Draft a basic weather model that’s small enough to implement in 0.1.”

Output style:

- Markdown sections:
  - `## Hunger & Stamina`, `## Time, Day/Night, Seasons`, `## Travel & Fast Travel`, `## Weather`, `## Implied Tasks`.

---

## 4. Using Vacuum Prompts (Old Chats → Design Doc)

### 4.1 Per-Conversation Design Extract

When you open **an old Lost Hiker chat** that still has useful decisions:

1. Paste this at the end of that chat:

```text
You are helping me consolidate design decisions for my Python curses-based text adventure **Lost Hiker**.

Your job is to scan THIS ENTIRE CONVERSATION so far and extract all the IMPORTANT, ACTIONABLE design decisions that affect the game.

Assume this context:
- Title: Lost Hiker
- Engine: Python, curses-based UI, JSON-driven data
- v0.1 codename: “Discordant Forest”
- v0.1 scope: Forest-only, focused on Forest Act I, Echo, and Astrin Tarrinae (tea/herb NPC)

Do NOT rehash the whole conversation. I only want the durable decisions and constraints that future work depends on.

---

### TASK

1. Identify design decisions (explicit choices, fixed mechanics, character roles, UI/UX choices, constraints).
2. Ignore discarded half-ideas and generic advice.
3. Classify each decision into categories like: `core_loop`, `forest_content`, `npc_echo`, `npc_astrin`, `vore_system`, `systems`, `ui_curses`, `tone_lore`, `other`.
4. Mark each decision as `locked`, `soft`, or `open`.
5. List constraints, open questions, and implied tasks.

---

### OUTPUT FORMAT

Respond ONLY with a Markdown document in this structure (no extra commentary):

```markdown
# Conversation Summary

- **Scope:** Short one-line description of what this conversation was mainly about.

## Design Decisions

### D1 — category: `...`, status: `locked|soft|open`
- **Description:** Short but precise statement of the decision.
- **Rationale:** Why we made this decision, if mentioned.

### D2 — category: `...`, status: `...`
- **Description:** ...
- **Rationale:** ...

## Constraints

- Hard constraint or “we will not do X”.
- Another important constraint.

## Open Questions

- Explicit unresolved question #1.
- Explicit unresolved question #2.

## Implied Tasks

- **T1:** Short description of a concrete task implied by one or more decisions.
- **T2:** Another task description.