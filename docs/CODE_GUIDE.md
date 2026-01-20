# Lost Hiker - Code Guide for Content Editors

This guide explains the codebase structure and how to edit game content.

## Quick Start for Content Editors

**Most content editing happens in JSON files**, not Python code.

### Where to Edit Content:

| What to Edit | File Location |
|--------------|---------------|
| Dialogue & conversations | `src/lost_hiker/data/dialogue_*.json` |
| Random events (foraging, flavor text) | `src/lost_hiker/data/events_forest.json` |
| Food items & recipes | `src/lost_hiker/data/items_food.json`, `cooking_recipes.json` |
| NPCs (who they are, where they appear) | `src/lost_hiker/data/npcs_forest.json` |
| Landmarks (discoverable locations) | `src/lost_hiker/data/landmarks_forest.json` |
| Quests (runestone data) | `src/lost_hiker/data/runestones_forest.json` |
| Seasons (weather, visuals) | `src/lost_hiker/data/seasons.json` |
| Races (player character options) | `src/lost_hiker/data/races.json` |

**📖 See `src/lost_hiker/data/README.md` for detailed JSON editing guide.**

---

## Codebase Structure

```
lost-hiker/
├── docs/                          # Design documents
│   ├── design/                    # Game design docs
│   │   └── Lost Hiker Master Design Doc.md
│   └── CODE_GUIDE.md             # This file
│
├── src/lost_hiker/               # Main game code
│   ├── data/                     # ⭐ Content files (JSON) ⭐
│   │   ├── README.md             # JSON editing guide
│   │   ├── dialogue_*.json       # NPC dialogue trees
│   │   ├── events_forest.json    # Random exploration events
│   │   ├── items_food.json       # Food item definitions
│   │   ├── cooking_recipes.json  # Recipes
│   │   ├── npcs_forest.json      # NPC definitions
│   │   ├── landmarks_forest.json # Landmark locations
│   │   ├── runestones_forest.json # Quest runestones
│   │   ├── seasons.json          # Season definitions
│   │   └── races.json            # Player races
│   │
│   ├── main.py                   # Entry point, UI setup, character creation
│   ├── engine.py                 # Main game loop (wake → explore → camp)
│   ├── state.py                  # Game state, save/load, persistence
│   ├── character.py              # Character stats, race system
│   ├── commands.py               # Command parser (text input handling)
│   │
│   ├── dialogue.py               # Dialogue system engine
│   ├── npcs.py                   # NPC encounter logic
│   ├── echo.py                   # Echo (serpent) interactions
│   │
│   ├── events.py                 # Random event system
│   ├── encounters.py             # Creature encounters
│   ├── scenes.py                 # Scene/location descriptions
│   ├── landmarks.py              # Landmark discovery
│   │
│   ├── cooking.py                # Cooking/crafting system
│   ├── tea_flavor.py             # Tea brewing mechanics
│   ├── hunger.py                 # Hunger/starvation system
│   │
│   ├── runestones.py             # Runestone repair quest (Act I)
│   ├── forest_act1.py            # Act I quest management
│   ├── kirin.py                  # Kirin (mystical guide) system
│   ├── micro_quests.py           # Small side quests
│   │
│   ├── vore.py                   # Vore/belly mechanics (optional)
│   ├── belly_interaction.py      # Belly interaction scenes
│   ├── combat.py                 # Combat system
│   │
│   ├── seasons.py                # Season cycle logic
│   ├── time_of_day.py            # Day/night cycle
│   ├── sky.py                    # Sky descriptions
│   ├── wayfinding.py             # Fast travel (wayfinding tea)
│   ├── rapport.py                # NPC relationship tracking
│   ├── race_flavor.py            # Race-specific flavor text
│   └── ui_curses.py              # Terminal UI (curses interface)
│
├── save/                         # Save files (auto-generated)
│   └── save.json                 # Player save data
│
└── Makefile                      # Build commands (make run, make format)
```

---

## Code Architecture

### Layer 1: Entry Point (main.py)

**Responsibility:** Start game, handle UI, character creation, load resources

**Key Functions:**
- `main()` - Entry point, sets up UI and loads data files
- `create_character()` - Character creation flow
- `build_ui()` - Choose between curses UI or console UI

**When to Edit:** Adding new UI screens, changing main menu, modifying character creation

### Layer 2: Game Loop (engine.py)

**Responsibility:** Core gameplay loop (wake → explore → camp → sleep)

**Key Class:** `Engine`

**Game Phases:**
1. **Intro** - Player wakes in Charred Hollow, meets Echo
2. **Wake** - Morning, check hunger, restore stamina
3. **Explore** - Forest exploration, events, encounters
4. **Camp** - Rest, cook, brew teas, save

**Key Methods:**
- `run()` - Main game loop
- `_run_day()` - Single day cycle
- `_explore_phase()` - Exploration loop (move deeper, events, camp/return)
- `_camp_phase()` - Camp menu (cook, brew, sleep)

**When to Edit:** Adding new commands, changing exploration flow, modifying camp options

### Layer 3: Game State (state.py)

**Responsibility:** All persistent game data (saved between sessions)

**Key Class:** `GameState`

**What's Stored:**
- Day number, season, time of day
- Character stats, stamina, condition
- Inventory, crafted items
- Quest progress (runestones, Act I state)
- NPC relationships (rapport)
- Discovered landmarks, location
- Settings (vore enabled, etc.)

**Migration System:**
When game structure changes, old saves are automatically upgraded via `GameStateRepository._migrate()`

**When to Edit:** Adding new quest flags, new state tracking, new mechanics that need persistence

### Layer 4: Character System (character.py)

**Responsibility:** Character stats, modifiers, race traits

**Key Classes:**
- `Character` - Player character with stats
- `TimedModifier` - Temporary buffs/debuffs (tea effects)

**Stat System:**
```
Final Stat = Base + Race Mods + Permanent Mods + Timed Mods
```

**When to Edit:** Adding new stats, changing modifier calculations, race balance

### Layer 5: Content Systems

#### Dialogue (dialogue.py)
- Node-based conversation trees
- Conditions (rapport, flags, items, seasons)
- Effects (rapport changes, flag sets)
- Branching based on player choices

#### Events (events.py)
- Random occurrences during exploration
- Weighted by depth, season, category
- Categories: forage, flavor, hazard, encounter
- Anti-repetition (recent_events tracking)

#### NPCs (npcs.py, echo.py)
- NPC definitions (name, appearance, location)
- Spawn at specific landmarks
- Dialogue integration
- Rapport tracking (relationship points)

#### Cooking (cooking.py)
- Recipe system (ingredients → output)
- Camp requirement check
- Inventory management
- Food categories (snack vs meal)

#### Quests (runestones.py, forest_act1.py, kirin.py)
- **Runestones**: 3-stage repair (physical → resonance → pulse)
- **Act I**: "Breath of the Forest" main quest
- **Kirin**: Mystical guide discovery and trust

---

## Key Concepts

### Depth System

Exploration uses a **depth counter** (0 = forest edge, 15+ = deep danger zone):
- **Depth 0-2**: Edge - Safe, common foraging, few hazards
- **Depth 3-6**: Mid - Balanced mix of events
- **Depth 7-14**: Deep - More dangerous, fewer resources
- **Depth 15+**: Depths - Extreme danger, rare events

Events have `min_depth`, `max_depth`, and `depth_weight` to control where they appear.

### Rapport System

NPCs track relationship points:
- **< 0**: Hostile
- **0-4**: Neutral
- **5-9**: Friendly
- **10+**: Close

Dialogue options and NPC behavior change based on rapport tier.

### Time & Seasons

**Seasons:** Spring → Summer → Fall → Winter (14 days each, 56-day cycle)
- Affects event weights (berries in summer, etc.)
- Changes visuals (sky colors, descriptions)
- Modifies gameplay (frozen streams in winter)

**Time of Day:** Dawn → Day → Dusk → Night
- Advances with exploration
- Affects sky descriptions
- Future: Will affect creature spawns, NPC availability

### Radio System (Echo Communication)

The HT radio is how the player communicates with Echo:
- **Radio v1** (start): Fragmentary, emotional broadcasts
- **Radio v2** (after Echo attunes it): Clear sentences, dialogue

Commands: `ping` (contact Echo), `talk echo` (dialogue)

### Hunger System

- Track `days_without_meal` (0-7)
- **Snacks** (berries, nuts): Don't count as meals, but sustain
- **Meals** (stew, cooked fish): Reset hunger to 0
- **Game Over** at 7 days without meal

### Modular Race System

Races are built from:
- **body_type**: humanoid, taur, naga, quadruped
- **size**: small, medium, large
- **archetype**: forest_creature, cave_creature, etc.
- **flavor_tags**: scaly, fluffy, warm_blooded (affects NPC reactions)
- **stat modifiers**: Race-specific bonuses

See `data/races.json` for race definitions.

---

## How Systems Interact

### Example: Foraging Event

1. **Player explores** (`engine.py` → `_explore_phase()`)
2. **Event selected** (`events.py` → `EventPool.pick()`)
   - Filters by depth (`min_depth`, `max_depth`)
   - Weights by category, depth, season
   - Excludes recent events
3. **Event triggers** (e.g., "berry_bush_patch")
   - Shows `text` to player
   - Applies `effects`: `inventory_add: ["forest_berries"]`
4. **Inventory updated** (`state.inventory.append("forest_berries")`)
5. **State saved** (`repo.save(state)`)

### Example: NPC Dialogue

1. **Player meets NPC** at landmark
2. **Dialogue starts** (`dialogue.py` → `start_dialogue()`)
   - Loads dialogue from `dialogue_*.json`
   - Checks conditions (rapport, flags, items)
   - Filters available nodes
3. **Player chooses option**
   - `rapport_delta` applied
   - `set_flags` updates state
   - `next_node_id` loads next node
4. **Dialogue continues** until exit node
5. **State saved** with new rapport/flags

### Example: Cooking at Camp

1. **Player at camp** (`engine.py` → `_camp_phase()`)
2. **Selects "Cook"** from menu
3. **Available recipes shown** (`cooking.py` → `get_available_recipes()`)
   - Checks inventory for ingredients
   - Filters by `requires_camp`
4. **Player selects recipe**
5. **Ingredients consumed** (`state.inventory.remove()`)
6. **Output added** (`state.inventory.append(output)`)
7. **Description shown** to player

---

## Common Editing Tasks

### Adding a New Dialogue Branch

1. Open `src/lost_hiker/data/dialogue_*.json`
2. Add new node to `nodes` array:
```json
{
  "id": "my_new_node",
  "npc_id": "echo",
  "text": "Echo tilts her head curiously.",
  "conditions": {"min_rapport_tier": "neutral"},
  "options": [
    {
      "text": "What do you see?",
      "next_node_id": "echo_vision",
      "rapport_delta": 1
    }
  ]
}
```
3. Update previous node's `next_node_id` to point here
4. Test in-game

### Adding a New Food Item

1. Add to `src/lost_hiker/data/items_food.json`:
```json
{
  "wild_onions": {
    "name": "Wild Onions",
    "description": "Pungent wild onions...",
    "category": "snack",
    "is_snack": true,
    "is_meal": false
  }
}
```
2. Add to forage event in `events_forest.json`:
```json
{
  "id": "onion_patch",
  "category": "forage",
  "text": "You find wild onions...",
  "effects": {"inventory_add": ["wild_onions"]},
  "base_weight": 1.0,
  "min_depth": 0
}
```
3. Test in-game

### Adding a New Recipe

1. Add to `src/lost_hiker/data/cooking_recipes.json`:
```json
{
  "onion_soup": {
    "name": "Onion Soup",
    "requires": {"wild_onions": 3, "creek_water": 1},
    "output": "onion_soup",
    "description": "A simple but hearty soup.",
    "requires_camp": true
  }
}
```
2. Add output item to `items_food.json` (as a meal):
```json
{
  "onion_soup": {
    "name": "Onion Soup",
    "description": "Warm onion soup.",
    "category": "meal",
    "is_meal": true,
    "is_snack": false,
    "satisfy_hunger_days": 1
  }
}
```
3. Test cooking at camp

### Adding a New NPC

1. Add to `src/lost_hiker/data/npcs_forest.json`:
```json
{
  "id": "lost_miner",
  "name": "Lost Miner",
  "description": "A dusty miner with a pickaxe.",
  "appearance_first": "You spot a dusty figure...",
  "appearance_return": "The miner waves.",
  "landmarks": ["cave_entrance"],
  "dialogue_start_node": "miner_intro",
  "rapport_start": 0
}
```
2. Add dialogue in `dialogue_forest.json`:
```json
{
  "id": "miner_intro",
  "npc_id": "lost_miner",
  "text": "Lost? Me too, friend.",
  "options": [...]
}
```
3. Test at cave_entrance landmark

---

## Testing Your Changes

1. **Edit JSON file** (check syntax with jsonlint.com or VS Code)
2. **Run game:**
   ```bash
   make run
   # or
   python -m lost_hiker.main
   ```
3. **Test your content:**
   - For events: Explore forest until event triggers
   - For dialogue: Meet NPC and talk
   - For recipes: Gather ingredients and cook at camp
   - For quests: Check quest state with `status` command

4. **Debug mode** (consistent RNG for testing):
   ```bash
   LOST_HIKER_SEED=12345 python -m lost_hiker.main
   ```

---

## Hard-Coded vs JSON Content

### JSON (Easy to Edit):
- ✅ Dialogue text
- ✅ Event descriptions
- ✅ Item names and descriptions
- ✅ NPC appearances and locations
- ✅ Recipe ingredients and outputs
- ✅ Landmark names and descriptions

### Python Code (Requires Programming):
- ⚠️ Game mechanics (combat, repair puzzles)
- ⚠️ Stat calculations
- ⚠️ Command parsing
- ⚠️ Quest logic (runestone repair stages)
- ⚠️ UI/menus
- ⚠️ Save/load system

**Rule of Thumb:** If it's **text, numbers, or data**, it's likely in JSON. If it's **logic or mechanics**, it's in Python.

---

## Getting Help

- **Design docs:** `docs/design/Lost Hiker Master Design Doc.md`
- **Data guide:** `src/lost_hiker/data/README.md`
- **Code comments:** Each `.py` file has inline documentation
- **Module docstrings:** Top of each `.py` file explains its purpose

---

## Common Pitfalls

### JSON Syntax Errors
- ❌ Missing commas between objects
- ❌ Trailing commas at end of arrays
- ❌ Unescaped quotes in text (use `\"` or avoid quotes)
- ✅ Use a JSON validator before committing

### Invalid References
- ❌ `next_node_id` points to non-existent node
- ❌ `required_items` references non-existent item
- ❌ Recipe ingredient not defined in items_food.json
- ✅ Double-check all IDs exist

### Balance Issues
- ⚠️ Event `base_weight` too high (floods exploration)
- ⚠️ Recipe too cheap (breaks economy)
- ⚠️ NPC rapport too easy to gain (trivializes relationships)
- ✅ Playtest and tune numbers

---

## Advanced Topics

### Adding a New Stat
1. Add to `DEFAULT_BASE_STATS` in `character.py`
2. Add to race modifiers in `data/races.json` (optional)
3. Use in calculations (e.g., `state.character.get_stat("my_new_stat")`)

### Adding a New Quest Flag
1. Add to `GameState` in `state.py`:
   ```python
   my_quest_completed: bool = False
   ```
2. Add migration default in `state.py` → `_migrate()`:
   ```python
   data.setdefault("my_quest_completed", False)
   ```
3. Set flag in dialogue or events:
   ```json
   "set_flags": {"my_quest_completed": true}
   ```

### Adding a New Command
1. Add alias to `CommandParser.__init__` in `commands.py`:
   ```python
   "meditate": "meditate",
   ```
2. Handle in `Engine._handle_command()` in `engine.py`:
   ```python
   elif cmd.verb == "meditate":
       return self._meditate_action()
   ```
3. Implement action method
4. Add to help text

---

## Summary

- **Content editing** = JSON files in `src/lost_hiker/data/`
- **Game logic** = Python files in `src/lost_hiker/`
- **State/progress** = `state.py` (what gets saved)
- **Main loop** = `engine.py` (how game flows)
- **Entry point** = `main.py` (where game starts)

**Start with JSON editing, graduate to Python when ready!**
