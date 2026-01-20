# Lost Hiker Content Data Files

This directory contains all the game's content in JSON format. This is where you edit dialogue, items, recipes, events, and more.

## Overview

Game content is separated into JSON files by type:
- **Dialogue**: NPC conversations and player choices
- **Events**: Random occurrences during exploration
- **Items & Recipes**: Food, tools, crafting recipes
- **NPCs**: NPC definitions and behaviors
- **Quests**: Quest data and runestone definitions
- **World**: Landmarks, seasons, scenes

---

## File Guide

### Dialogue Files

Dialogue files define NPC conversations using a node-based system.

**Files:**
- `dialogue_echo.json` - Echo the serpent's dialogue (radio-based)
- `dialogue_naiad.json` - Naiad at the creek
- `dialogue_druid.json` - Forest druid
- `dialogue_fisher.json` - Fisher at the creek
- `dialogue_astrin.json` - Astrin the herbalist
- `dialogue_forest.json` - General forest NPCs

**Structure:**
```json
{
  "nodes": [
    {
      "id": "echo_start",                    // Unique node ID
      "npc_id": "echo",                      // Which NPC speaks
      "text": "[RADIO] Warm… curious…",      // What they say
      "conditions": {                         // When this node appears
        "min_rapport_tier": "neutral"        // Requires neutral+ rapport
      },
      "options": [                            // Player choices
        {
          "text": "Hello, Echo.",            // Choice text
          "next_node_id": "echo_greeting",   // Next node to visit
          "rapport_delta": 1,                // Rapport change (+1)
          "set_flags": {                     // Set game flags
            "echo_met": true
          }
        }
      ]
    }
  ]
}
```

**Conditions:**
- `min_rapport_tier`: "hostile", "neutral", "friendly", "close"
- `required_flags`: Dict of flags that must be true
- `forbidden_flags`: Dict of flags that must be false
- `min_day`: Minimum in-game day
- `max_day`: Maximum in-game day
- `required_items`: List of items player must have
- `required_season`: Season name ("spring", "summer", "fall", "winter")

**Rapport Tiers:**
- hostile: < 0
- neutral: 0-4
- friendly: 5-9
- close: 10+

**Special Dialogue Tokens:**
- `[RADIO]` - Radio transmission prefix (for Echo)
- `{player_name}` - Player's character name
- `{race}` - Player's race
- Line breaks: Use `\n` in text

---

### Events (events_forest.json)

Random events that occur during forest exploration.

**Event Types (category field):**
- `forage` - Finding food/resources
- `flavor` - Atmospheric text (no mechanical effect)
- `hazard` - Dangerous situations (stamina loss, etc.)
- `encounter` - Creature encounters

**Structure:**
```json
{
  "id": "berry_bush_patch",                // Unique ID
  "category": "forage",                    // Event type
  "text": "Wild berry bushes cluster...",  // Description shown to player
  "effects": {                             // What happens
    "inventory_add": ["forest_berries"],   // Add items
    "inventory_add_count": [[2, 5]]        // Random count (2-5)
  },
  "base_weight": 1.4,                      // Base probability (1.0 = normal)
  "depth_weight": -0.12,                   // Weight change per depth (+ or -)
  "min_depth": 0,                          // Minimum depth
  "max_depth": 15,                         // Maximum depth (optional)
  "season_weights": {                      // Seasonal modifiers (optional)
    "spring": 1.5,                         // 1.5x more likely in spring
    "winter": 0.3                          // 0.3x less likely in winter
  }
}
```

**Effect Types:**
- `inventory_add`: List of item IDs to add
- `inventory_add_count`: List of [min, max] count ranges
- `stamina_delta`: Change stamina (can be negative)
- `rapport_delta`: Dict of NPC rapport changes {"echo": 1}
- `timed_modifiers`: Temporary stat buffs/debuffs

**Weighting System:**
- `base_weight`: Base probability (higher = more common)
  - 0.5 = rare
  - 1.0 = normal
  - 2.0 = common
- `depth_weight`: Change per depth level
  - Negative values (-0.12) = less common deeper
  - Positive values (+0.15) = more common deeper
  - Zero (0.0) = consistent at all depths

**Example Weight Curve:**
```
Berry bushes: base=1.4, depth=-0.12
Depth 0:  1.4         (common at edge)
Depth 5:  0.8         (uncommon mid-forest)
Depth 10: 0.2         (rare deep forest)
```

---

### Cooking & Food (cooking_recipes.json, items_food.json)

**Recipes (cooking_recipes.json):**
```json
{
  "forest_stew": {
    "name": "Forest Stew",                      // Display name
    "requires": {                               // Ingredients needed
      "edible_mushroom": 1,
      "forest_berries": 1
    },
    "output": "forest_stew",                    // Item created
    "description": "A hearty stew...",          // Flavor text
    "requires_camp": true                       // Must be at camp
  }
}
```

**Food Items (items_food.json):**
```json
{
  "forest_berries": {
    "name": "Forest Berries",
    "description": "Tart wild berries...",
    "category": "snack",                        // "snack" or "meal"
    "satisfy_hunger_days": 0,                   // 0 for snacks, 1+ for meals
    "is_meal": false,                           // true for full meals
    "is_snack": true                            // true for snacks
  }
}
```

**Food Categories:**
- **Snack**: Doesn't count as full meal, but can be eaten on the same day as a meal
- **Meal**: Counts as full meal, resets hunger counter

---

### NPCs (npcs_forest.json)

NPC definitions and spawn locations.

```json
{
  "npcs": [
    {
      "id": "forest_hermit",                   // Unique NPC ID
      "name": "Forest Hermit",                 // Display name
      "description": "A weathered figure...",   // Initial description
      "appearance_first": "You notice...",      // First meeting text
      "appearance_return": "The hermit...",     // Subsequent meetings
      "landmarks": ["fallen_giant"],            // Where they appear
      "dialogue_start_node": "hermit_start",    // Entry dialogue node
      "rapport_start": 0,                       // Starting rapport
      "tags": ["hermit", "reclusive"]           // NPC tags
    }
  ]
}
```

**NPC Locations:**
NPCs appear at specific landmarks. List landmark IDs in the `landmarks` array.

---

### Landmarks (landmarks_forest.json)

Discoverable locations in the forest.

```json
{
  "landmarks": [
    {
      "id": "fallen_giant",                    // Unique ID
      "name": "The Fallen Giant",              // Display name
      "discovery_text": "You discover...",     // First visit
      "description": "A massive tree...",      // General description
      "category": "major",                     // "major" or "minor"
      "actions": [                             // Available actions
        "look_closer",
        "rest_here",
        "examine_roots"
      ],
      "min_depth": 3,                          // Minimum depth to discover
      "discovery_weight": 1.0                  // Discovery probability
    }
  ]
}
```

**Landmark Categories:**
- `major`: Important story locations
- `minor`: Flavor locations, less significant

---

### Runestones (runestones_forest.json, runestone_glade.json)

Quest-related runestones that can be repaired.

```json
{
  "runestones": [
    {
      "id": "runestone_glade_edge",            // Unique ID
      "name": "Glade Edge Runestone",          // Display name
      "location": "glade",                     // Zone ID
      "landmark_id": null,                     // Landmark (if any)
      "fractured": true,                       // Is it broken?
      "description_intact": "A smooth...",     // Before breaking
      "description_fractured": "Cracks...",    // After breaking
      "repair_stages": {                       // Repair quest stages
        "physical": false,
        "resonance": false,
        "pulse": false
      }
    }
  ]
}
```

---

### Seasons (seasons.json)

Season definitions and cycle configuration.

```json
{
  "cycle_length": 56,                          // Days per full cycle
  "seasons": [
    {
      "name": "spring",                        // Season ID
      "display_name": "Spring",                // Display name
      "duration": 14,                          // Days in season
      "description": "Flowers bloom...",       // Flavor text
      "sky_colors": {                          // Time-of-day colors
        "dawn": "pale pink fading to blue",
        "day": "bright clear blue",
        "dusk": "soft gold blending to purple",
        "night": "deep indigo scattered with stars"
      }
    }
  ]
}
```

---

### Races (races.json)

Player race definitions.

```json
{
  "human": {
    "name": "Human",                           // Display name
    "display_name": "Human",
    "description": "An ordinary human...",     // Character creation text
    "body_type_default": "humanoid",           // Default body type
    "size_default": "medium",                  // Default size
    "archetype_default": "forest_creature",    // Default archetype
    "flavor_tags": [                           // Tags for NPC reactions
      "mammal",
      "warm_blooded",
      "bipedal"
    ],
    "tags": [],                                // Gameplay tags
    "modifiers": []                            // Stat modifiers
  }
}
```

**Stat Modifiers:**
```json
"modifiers": [
  {
    "add": {                                   // Additive bonuses
      "stamina_max": 1.0                       // +1 max stamina
    },
    "mul": {                                   // Multiplicative bonuses
      "stamina_camp_restore": 1.2              // 20% more stamina from camp
    }
  }
]
```

**Common Stats:**
- `stamina_max`: Maximum stamina
- `stamina_camp_restore`: Stamina restored from camping
- `inventory_slots`: Backpack capacity
- `explore_slots`: Actions per stamina point

---

## Content Editing Tips

### Adding a New Event

1. Open `events_forest.json`
2. Add new event object to `events` array
3. Give it unique `id` (use descriptive name: `oak_grove_discovery`)
4. Set `category` ("forage", "flavor", "hazard", or "encounter")
5. Write `text` (what player sees)
6. Add `effects` if needed (items, stamina changes, etc.)
7. Set depth range (`min_depth`, `max_depth`)
8. Tune `base_weight` and `depth_weight` for frequency

### Adding NPC Dialogue

1. Open appropriate `dialogue_*.json` file
2. Add new node to `nodes` array
3. Set `id` (unique), `npc_id`, and `text`
4. Add `conditions` for when it appears
5. Add `options` with player choices
6. Link `next_node_id` to continue conversation
7. Add `rapport_delta` to affect relationship
8. Set `set_flags` for quest progression

### Adding a Recipe

1. Open `cooking_recipes.json`
2. Add new recipe with unique key
3. Set `name`, `requires` (ingredients), and `output`
4. Write `description` (flavor text)
5. Add output item to `items_food.json` if needed

### Adding a Landmark

1. Open `landmarks_forest.json`
2. Add to `landmarks` array
3. Set `id`, `name`, `discovery_text`, `description`
4. Set `category` ("major" or "minor")
5. Define `actions` (what player can do)
6. Set `min_depth` for discovery
7. Reference in NPC `landmarks` array if NPC visits

---

## Validation Tips

**Before committing changes:**
1. Validate JSON syntax (use jsonlint.com or VS Code)
2. Check for duplicate IDs (event IDs, node IDs, item IDs must be unique)
3. Verify `next_node_id` references exist in dialogue
4. Ensure `required_items` reference valid items
5. Test in-game to verify text displays correctly

**Common Mistakes:**
- Missing commas between JSON objects
- Trailing commas at end of arrays (invalid JSON)
- Unescaped quotes in text (use `\"` or avoid quotes)
- Invalid `next_node_id` (node doesn't exist)
- Misspelled item IDs in recipes or events

---

## File Dependencies

Some files reference others:
- **Dialogue** references **NPCs** (via `npc_id`)
- **NPCs** reference **Landmarks** (via `landmarks` array)
- **NPCs** reference **Dialogue** (via `dialogue_start_node`)
- **Recipes** reference **Items** (via ingredient names)
- **Events** reference **Items** (via `inventory_add`)

When renaming IDs, update all references!

---

## Race-Specific Content

Some content changes based on player race:

**Race Tags in Flavor Text:**
- Wolves notice scent differently
- Elves sense forest magic
- Dwarves feel stone resonance
- Lizard-kin notice temperature

**Implementation:**
Race-specific flavor is added programmatically (see `race_flavor.py`), but you can add tags to races in `races.json`:
- `keen-smell`: Enhanced scent descriptions
- `ambient_magic`: Notice magical phenomena
- `stoneborn`: Sense earth/stone
- `forestborn`: Feel forest life

---

## Testing Your Changes

1. Edit JSON file
2. Save file
3. Run game: `make run` or `python -m lost_hiker.main`
4. Test new content in-game
5. Check for errors in console

**Debug mode:** Set `LOST_HIKER_SEED` env var for consistent RNG:
```bash
LOST_HIKER_SEED=12345 python -m lost_hiker.main
```

---

## Questions?

- Check design docs in `/docs/design/`
- See code comments in `/src/lost_hiker/*.py`
- Test changes in-game before committing
