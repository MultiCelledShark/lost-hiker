# Lost Hiker
This is a text-adventure game where you're a hiker that got lost. Yeah there's a lot more to it than that, but this is private so clearly you know what you're getting into.

## Documentation

### 📖 For Content Editors (Writers/Designers)

**Start Here:**
- **[Content Editing Guide](src/lost_hiker/data/README.md)** - How to edit dialogue, events, NPCs, recipes (JSON files)
- **[Code Guide](docs/CODE_GUIDE.md)** - Codebase overview and common tasks

**What You Can Edit:**
- Dialogue & conversations → `src/lost_hiker/data/dialogue_*.json`
- Random events (foraging, flavor text) → `src/lost_hiker/data/events_forest.json`
- Food items & recipes → `src/lost_hiker/data/items_food.json`, `cooking_recipes.json`
- NPCs & their locations → `src/lost_hiker/data/npcs_forest.json`
- Landmarks → `src/lost_hiker/data/landmarks_forest.json`
- Quest data → `src/lost_hiker/data/runestones_forest.json`

### 💻 For Developers

**Start Here:**
- **[Code Guide](docs/CODE_GUIDE.md)** - Architecture, file structure, how systems interact
- **[Documentation Summary](docs/DOCUMENTATION_SUMMARY.md)** - What's documented and where

**Key Files:**
- `src/lost_hiker/main.py` - Entry point, character creation, data loading
- `src/lost_hiker/engine.py` - Main game loop (wake → explore → camp)
- `src/lost_hiker/state.py` - Game state, save/load, persistence
- `src/lost_hiker/dialogue.py` - Dialogue tree system
- `src/lost_hiker/events.py` - Random event system

**All Python modules have comprehensive docstrings explaining:**
- What the module does
- Key concepts and patterns
- When/how to modify code
- Related systems

### 🎮 Design Reference

All gameplay systems, worldbuilding, and design principles are documented in:
- **[Lost Hiker Master Design Doc](docs/design/Lost Hiker Master Design Doc.md)** - Complete game design vision

## Quick Start

### Running the Game
```bash
make run
# or
python -m lost_hiker.main
```

### Editing Content
1. Edit JSON files in `src/lost_hiker/data/`
2. See [Content Editing Guide](src/lost_hiker/data/README.md) for JSON structure
3. Test changes in-game

### Development
1. Read [Code Guide](docs/CODE_GUIDE.md)
2. Check module docstrings for specific systems
3. Follow existing patterns and conventions
