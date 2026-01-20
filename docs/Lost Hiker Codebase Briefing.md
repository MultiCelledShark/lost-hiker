# Lost Hiker Codebase Briefing

## 1. High-Level Architecture Overview

Your game follows a classic text adventure architecture with clean separation of concerns:

### Core Architecture Pattern┌─────────────────────────────────────────────────────────────────┐│             main.py                 ││  Entry point, UI initialization (Curses/Console), main menu  │└─────────────────────────────────┬───────────────────────────────┘                 │┌─────────────────────────────────▼───────────────────────────────┐│             engine.py                ││  Core game loop: Wake → Explore → Camp → Return/Sleep     ││  Coordinates all systems, handles commands, runs daily cycle  │└────────────┬──────────────┬──────────────┬──────────────────────┘       │       │       │   ┌───────▼───────┐ ┌────▼────┐ ┌──────▼──────┐   │  state.py  │ │data/*.json│ │ Subsystems │   │ GameState   │ │ Content │ │ (modular)  │   │ Persistence  │ │ Events  │ │ echo.py   │   │ Schema v5   │ │ Dialogue │ │ kirin.py  │   └───────────────┘ │ Landmarks│ │ vore.py   │            │ NPCs   │ │ belly_*.py │            └──────────┘ │ encounters │                  │ runestones │                  └─────────────┘

### Key Components

| Module               | Purpose                                    | Lines  |
| :------------------- | :----------------------------------------- | :----- |
| engine.py            | Core game loop, all phase handlers         | ~5000+ |
| state.py             | GameState dataclass, save/load, migrations | ~480   |
| main.py              | Entry point, CursesUI, character creation  | ~960   |
| character.py         | Character model, stat calculations         | ~150   |
| events.py            | Event pool, depth-weighted drawing         | ~360   |
| encounters.py        | Creature encounter framework               | ~350   |
| echo.py              | Echo-specific interactions (pet/hug/boop)  | ~505   |
| belly_interaction.py | Vore shelter/transport system              | ~755   |
| kirin.py             | Fast-travel system post-Act I              | ~340   |

### Data-Driven Design

Content is cleanly separated into JSON files in src/lost_hiker/data/:

- 20 data files covering events, creatures, NPCs, dialogue, landmarks, races, teas, etc.

- Easy to add content without touching Python code

------

## 2. Current State Assessment

### ✅ Fully Implemented Features

Core Game Loop

- Day/night cycle with Wake → Explore → Camp stages

- Stamina management with wake/camp recovery

- Hunger system (days without meal → stamina cap reduction)

- Time-of-day tracking (Dawn/Day/Dusk/Night)

Character System

- 10 playable races with unique flavor tags and modifiers

- Body types (humanoid/taur/naga/quadruped)

- Sizes (small/medium/large)

- Archetypes (forest_creature/cave_creature/river_creature/spiritborn/leyline_touched/beastfolk)

- Custom race creation

Exploration

- Depth-based forest exploration (edge/mid/deep bands)

- 12 landmarks with unique features (runestones, food, NPCs, camp spots)

- Path stability system (forest memory)

- Seasonal effects on events and foraging

NPCs & Dialogue

- 6 NPCs: Echo, Hermit (Alder), Naiad, Druid, Fisher, Astrin

- Branching dialogue trees with conditions (rapport, race, flags)

- Micro-quests for each NPC

Act I Quest: "Mend the Forest's Pulse"

- 3 fractured runestones to repair

- Repair stages: physical repair → resonance tuning → pulse alignment

- Forest stabilization effects (event weights, stamina costs, navigation)

Vore System (Optional Toggle)

- Echo shelter interactions (hug/boop can trigger)

- Belly interaction loop (soothe/struggle/relax/call)

- Non-lethal, used for shelter and transport

- Race/tag-aware flavor text

Kirin Fast Travel

- Unlocks after Act I completion

- Once-per-day travel to familiar landmarks

- Portal or vore-based transport options

Brewing System

- 7 teas with various effects (calm beasts, improve memory, camp bonuses)

- Primitive mortar crafting for runestone repair

### ⚠️ Partially Implemented

Encounter System

- Framework exists in encounters.py

- Some threat encounters defined but combat resolution is basic

- Threat tier and resolution styles defined but not deeply used

Radio Evolution

- radio_version tracked (1 or 2) but upgrade mechanic is simplified

- Design doc describes elaborate upgrade ceremony not fully implemented

### ❌ Not Yet Implemented (Per Design Doc)

| Feature            | Design Doc Status                        |
| :----------------- | :--------------------------------------- |
| Plains Zone        | Described, blocked in game               |
| Mountain Path/Peak | Described, blocked by rockslide          |
| Lake Zone          | Described, blocked                       |
| Cave System        | Described, mouth exists but blocked      |
| Town               | Described in master doc, not implemented |
| Elder Dragon       | End-game goal, not implemented           |
| Full Combat System | Basic threat resolution only             |
| Taming/Summoning   | Framework exists but not fleshed out     |
| Player-as-Predator | Toggle exists, minimal content           |

------

## 3. Content Inventory

### Dialogue Content

| File                 | Node Count  | NPC                             |
| :------------------- | :---------- | :------------------------------ |
| dialogue_echo.json   | ~100+ nodes | Echo (extensive race/tag-aware) |
| dialogue_astrin.json | 49 nodes    | Astrin the herbalist            |
| dialogue_fisher.json | 35 nodes    | The Fisher                      |
| dialogue_forest.json | 30 nodes    | Generic forest                  |
| dialogue_druid.json  | 30 nodes    | The Druid                       |
| dialogue_naiad.json  | 28 nodes    | The Naiad                       |

Total: ~270+ dialogue nodes

### World Content

| Category         | Count                                                  |
| :--------------- | :----------------------------------------------------- |
| Forest Landmarks | 12 (3 with runestones, 4 with NPCs, 4 "exit blockers") |
| Creatures        | 40+ (predators, forageable, mystical)                  |
| Forest Events    | 35                                                     |
| Playable Races   | 10                                                     |
| Teas/Brews       | 7                                                      |
| Runestones       | 3 (Act I quest)                                        |

### Locations Implemented

THE GLADE (hub)

  │

  ├── Forest (explored via depth system)

  │   ├── Fallen Giant (runestone, safe haven)

  │   ├── Split Boulder (runestone, mystical)

  │   ├── Stone Lantern Clearing (runestone, ritual)

  │   ├── Creek Bend (resources, gold pan)

  │   ├── Whispering Hollow (Hermit NPC, camp)

  │   ├── Sunken Spring (Naiad NPC)

  │   ├── Verdant Hollow (Druid NPC)

  │   ├── Old Creek Bend (Fisher NPC)

  │   └── [4 exit blockers: plains_pass, mountain_route, riverside_road, cavern_mouth]

  │

  └── [Not yet implemented: Plains, Mountain, Lake, Caves, Town]

------

## 4. Design Doc Alignment

### ✅ Matches Design Doc Well

- Forest exploration loop with stamina/depth mechanics

- Hunger system with stamina cap degradation

- Runestone repair as Act I main quest

- Echo as radio-attuned companion with race-aware dialogue

- Seasonal effects on events and foraging

- Kirin as late Act I reward

- Optional vore system as shelter/transport

- Wave 1 NPCs (Hermit, Naiad, Druid, Fisher, Astrin)

### ⚠️ Simplified from Design Doc

- Radio upgrade: Design doc has elaborate Echo-eats-radio ceremony; code has simpler radio_version flag

- Mortar crafting: Simplified (ingredients + gold_pan check)

- Race modifiers: Design doc has more detailed sensory profiles; code uses flavor_tags system

### ❌ Missing from Design Doc

- Zones: Only Forest is playable; Plains, Mountain, Lake, Caves, Town are blocked

- Elder Dragon: End-game goal not implemented

- Taming/Summoning: Framework exists but no meaningful gameplay loop

- Fetch Quests: Some NPC quests are placeholder/simple

- Digestion phases: Design doc mentions [TBD], code treats vore as safe shelter

------

## 5. Quick Win Opportunities

### Easiest to Implement (Get Back Into Flow)

1. Add More Forest Events

- events_forest.json is easy to extend

- Add more forage, flavor, and encounter events

- File: src/lost_hiker/data/events_forest.json

1. Expand NPC Dialogue

- Dialogue is purely data-driven

- Add more conversation branches to existing NPCs

- Files: dialogue_*.json

1. Add New Teas/Recipes

- Simple JSON additions

- File: src/lost_hiker/data/teas.json

1. Add More Creatures

- Extend creature roster for variety

- File: src/lost_hiker/data/creatures.json

1. Polish Echo Interactions

- The echo.py module is well-structured

- Add more variant text pools for pet/hug/boop

### Medium Effort

1. Implement Radio Upgrade Ceremony

- Echo rapport threshold triggers upgrade

- Already tracked via radio_version and pending_radio_upgrade

1. Add More Landmarks

- Extend depth range of forest

- Add unique features/NPCs

1. Flesh Out Micro-Quests

- NPC quest flags exist in state.npc_state

- Implement reward logic

------

## 6. Potential Issues & Technical Debt

### 🔴 Critical Issues

1. engine.py is 5000+ lines

- Should be split into multiple modules

- Consider: engine_glade.py, engine_forest.py, engine_camp.py, etc.

1. Duplicate CursesUI class in main.py

- Lines 64-180 and 181-416 are nearly identical copies

- Should consolidate into single class

main.py

class CursesUI(UI):

  """First definition starts at line 64"""

  ...

class CursesUI(UI): # DUPLICATE!

  """Second definition starts at line 181 - shadows the first"""

  ...

### 🟡 Code Smells

1. Legacy fields in GameState

- season_index, season_day kept for migration but add confusion

- Consider removing after sufficient migration period

1. Many Optional fields

- GameState has many Optional[...] fields that could have better defaults

- Makes type checking less helpful

1. Import cycles handled with TYPE_CHECKING

- Several modules use if TYPE_CHECKING: pattern

- Not bad, but indicates tight coupling

### 🟢 Minor Issues

1. Only 1 TODO in codebase

- engine.py:1917: "TODO: Could add landmark type checking here"

- Generally clean code

1. No test files present

- tests/ directory mentioned in .cursorrules but not in project layout

- Would help with refactoring confidence

------

## Summary: Where to Start

Based on this analysis, here's a prioritized path back into the project:

| Priority | Task                              | Effort | Impact                   |
| :------- | :-------------------------------- | :----- | :----------------------- |
| 1        | Fix duplicate CursesUI class      | Low    | High (bug prevention)    |
| 2        | Add 5-10 new forest events        | Low    | Medium (content variety) |
| 3        | Expand Echo dialogue variants     | Low    | Medium (flavor)          |
| 4        | Implement 1 NPC micro-quest fully | Medium | High (progression)       |
| 5        | Split engine.py into modules      | High   | High (maintainability)   |
| 6        | Add tests for core systems        | Medium | High (confidence)        |

The codebase is well-structured and content-rich. The main technical debt is the oversized engine.py and the duplicate UI class. Content-wise, you have a solid Act I foundation—the path forward is either polishing Act I or starting to implement Act II zones.