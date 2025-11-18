# Forest Balance Notes - Act I Core Loop

This document summarizes the tuned baseline values for the Forest Act I balance pass. These values serve as a reference for future work (Act II, combat expansion, belly-loop, etc.).

## Food & Resource Economy

### Starting Food
- **Starting rations**: 2-4 random food items (berries, nuts, dried berries)
- **Rationale**: Gives new players a small buffer to learn foraging without immediate starvation

### Forage Yields
- **Berry bushes**: 2-5 berries (was 2-4), base_weight 1.4 (was 1.2)
- **Trail nuts**: 3-7 nuts (was 3-6), base_weight 1.1 (was 1.0)
- **Mushrooms**: 2-4 mushrooms (was 2-3), base_weight 1.2 (was 1.1)
- **Mint**: base_weight 1.5 (was 1.6), depth_weight -0.12 (was -0.15)
- **Mossy log cache**: base_weight 1.0 (was 0.9), depth_weight 0.1 (was 0.15)

### Forage Spawn Rates (Category Weights)
- **Shallow (edge)**: forage 1.5x (was 1.35x) - safer, more food available
- **Mid**: forage 1.0x - balanced survival tension zone
- **Deep**: forage 0.65x (was 0.7x) - leaner, riskier

### Safety Net
- **Force forage event**: Triggers if player hasn't found food in 7+ steps
- **Rationale**: Prevents pure RNG starvation deaths

## Stamina & Exploration

### Base Stamina Costs
- **Exploration step**: 0.9 stamina (was 1.0)
- **Rationale**: Allows ~10% more exploration per day, reducing constant exhaustion

### Stamina Recovery
- **Wake restore**: 1.0 (unchanged)
- **Camp restore**: 3.0 (unchanged)
- **Field camping**: 75% of max stamina (unchanged)
- **Glade rest**: 100% of max stamina (unchanged)
- **Collapse**: 50% of max stamina, 50% stamina cap (unchanged)

### Glade vs Field Camping
- **Glade**: Full stamina restoration, safe location, access to NPCs (Astrin, Echo), special events
- **Field camping**: 75% stamina restoration, riskier location, no NPC access
- **Rationale**: Glade is clearly superior but field camping remains viable for extended exploration

## Hunger System

### Hunger Thresholds (Stamina Cap Multipliers)
- **0 days without meal**: 100% stamina cap
- **1 day**: 80% stamina cap (was 75%) - slightly more forgiving
- **2 days**: 55% stamina cap (was 50%) - slightly more forgiving
- **3 days**: 30% stamina cap (was 25%) - slightly more forgiving
- **4+ days**: 0% stamina cap (game over)

### Rationale
- Slightly more forgiving to allow careful players to survive without constant death threats
- Still punishing enough that food management matters

## Encounter Weighting

### Base Encounter Chance
- **Base chance**: 10% per exploration step (was 12%)
- **Shallow (depth 0-9)**: 0.5x multiplier (was 0.7x) - much safer
- **Mid (depth 10-24)**: 1.3x multiplier (was 1.2x) - main tension zone
- **Deep (depth 25+)**: 1.6x multiplier (was 1.5x) - most dangerous

### Category Weights by Depth Band

#### Shallow (Edge)
- **Forage**: 1.5x (was 1.35x) - more food
- **Flavor**: 1.3x (was 1.2x)
- **Encounter**: 0.5x (was 0.6x) - fewer predators
- **Hazard**: 0.5x (was 0.6x) - fewer hazards
- **Boon**: 1.2x (was 1.1x)

#### Mid
- **Forage**: 1.0x - balanced
- **Flavor**: 1.0x
- **Encounter**: 1.15x (was 1.1x) - more encounters
- **Hazard**: 1.1x (was 1.05x)
- **Boon**: 1.0x

#### Deep
- **Forage**: 0.65x (was 0.7x) - leaner
- **Flavor**: 0.75x (was 0.8x)
- **Encounter**: 1.4x (was 1.35x) - more dangerous
- **Hazard**: 1.3x (was 1.25x) - more hazards
- **Boon**: 1.15x (was 1.1x) - slightly more mystical encounters after stabilization

### Threat Encounters
- **Threat preference**: Only at depth 10+ (was 8+)
- **Rationale**: Shallow forest should rarely have threats

## Kirin & Rare Creatures

### Kirin Foreshadowing
- **After 1 repair**: 3% chance (was 5%) - rare, like a rumor
- **After 2 repairs**: 6% chance (was 8%) - still uncommon
- **After 3 repairs**: 12% chance (was 10%) - more noticeable
- **Rationale**: Kirin should feel rare early, more common as Act I progresses

### Kirin Travel
- **Unlock**: Requires Act I completion (3 runestones repaired)
- **Usage**: Once per day
- **Destinations**: Landmarks with path stability >= 2 ("familiar" or "well-worn")
- **Rationale**: Reliable but not guaranteed travel option in late Act I

### Rare Creatures (Moss-Treader, Glow-Elk)
- **Before stabilization**: 0.6x weight (was 0.7x) - rarer
- **During stabilization (1-2 repairs)**: 1.3x weight (was 1.2x)
- **After stabilization (3+ repairs)**: 1.7x weight (was 1.5x) - more common
- **Glow-Elk event**: Requires 1+ runestone repair
- **Rationale**: Gentle, rare encounters that become slightly more common after stabilization

## Forest Memory & Navigation

### Path Stability
- **Stability 0 (unknown)**: 1.0x weight
- **Stability 1 (faint)**: 1.2x weight
- **Stability 2 (familiar)**: 1.5x weight
- **Stability 3 (well-worn)**: 2.0x weight

### Forest Memory Modifier (from Act I progress)
- **0 repairs**: 1.0x (normal)
- **1 repair**: 1.10x (10% improvement)
- **2 repairs**: 1.15x (15% improvement)
- **3+ repairs**: 1.20x (20% improvement)

### Rationale
- Early game: Getting lost is possible but player can still reach 2-3 landmarks
- After moderate play: Forest memory + NPC hints + teas make navigation noticeably easier
- Act I completion: Navigation feels "gentler" without removing missteps in deep zones

## NPC Rewards & Micro-Quests

### General Philosophy
- Rewards should feel meaningful but not mandatory
- NPC loops worth revisiting but not required for survival
- Teas and buffs provide noticeable but not overpowered benefits

### Key NPC Rewards
- **Hermit**: Trinket + map buff (wayfinding improvement)
- **Naiad**: Water blessing + Water-Clarity Tea (water management)
- **Druid**: Spore/chaga quest + Focus/Clarity Tea (forest memory +1.0)
- **Fisher**: Mussel mastery + trap reward (food gathering improvement)
- **Astrin**: Dreamleaf Tea (camp_bonus modifier), herb ID, Glade comfort
- **Echo**: Check-ins, small resource favors, Blue Fireflies event

## Difficulty Curve

### Early Act I (0 runestones)
- **Food**: Rough but survivable with foraging
- **Encounters**: Shallow areas safer, mid areas tense
- **Navigation**: Getting lost possible but manageable
- **Stamina**: Tired but not constantly at death's door

### Mid Act I (1-2 runestones)
- **Food**: Manageable with foraging + NPC help
- **Encounters**: Tense but manageable if using systems
- **Navigation**: Noticeably easier as landmarks discovered
- **Stamina**: Sustainable exploration pace with teas and Glade rest

### Late Act I (3+ runestones, stabilized)
- **Food**: Calmer but still requires attention
- **Encounters**: Fewer spiky threats, more mystical encounters
- **Navigation**: Gentler, easier to revisit landmarks
- **Stamina**: More comfortable but reckless play still punished
- **Kirin**: Available for reliable travel between familiar landmarks

## Act I Stabilization Effects

### Threat Encounter Modifier
- **0 repairs**: 1.0x (normal)
- **1 repair**: 0.95x (5% reduction)
- **2 repairs**: 0.90x (10% reduction)
- **3+ repairs**: 0.85x (15% reduction)

### Stamina Cost Modifier (by depth)
- **0 repairs**: 1.0x (normal)
- **1 repair**: 0.95x at depth 10+ (5% reduction)
- **2 repairs**: 0.90x at depth 10+, 0.95x at depth 5-9
- **3+ repairs**: 0.85x at depth 15+, 0.90x at depth 10-14, 0.95x at depth 5-9

### Event Category Modifiers (by depth band)
- **1 repair**: +5% forage/flavor, -5% hazard, -2% encounter
- **2 repairs**: +10% forage/flavor, -10% hazard, -5% encounter, +5% boon
- **3+ repairs**: +15% forage/flavor, -15% hazard, -8% encounter, +10% boon
- **Deep band amplification**: Effects are 1.1x stronger in deep areas

## Seasonal & Time-of-Day Effects

### Seasons
- **Spring**: Slightly kinder, more magical (higher forage, mystical encounters)
- **Summer**: Balanced
- **Fall**: More aggressive predators, leaner forage
- **Winter**: Leanest forage, most aggressive predators

### Time of Day
- **Dawn/Day**: Safer, more forageables active
- **Dusk/Night**: More dangerous, predators more active

## Testing Notes

### Expected Player Experience
- **New player**: Can survive several in-game weeks with basic foraging
- **Engaged player**: Can maintain food with foraging + 1-2 NPC quests
- **Optimized player**: Can thrive with NPC help, teas, and strategic exploration

### Balance Goals Met
- ✅ Shallow forest feels safer than deep
- ✅ Mid forest is the main survival tension zone
- ✅ Deep forest is dangerous but not unfair
- ✅ Act I stabilization noticeably eases the Forest
- ✅ NPC rewards feel meaningful but not mandatory
- ✅ Glade is clearly better than field camping
- ✅ Food economy allows survival without trivializing hunger
- ✅ Stamina pacing allows exploration without constant exhaustion

## Future Reference

When implementing:
- **Act II (Caves)**: Use these baselines as starting point, adjust for different environment
- **Combat expansion**: Consider current encounter rates and threat preferences
- **Belly-loop**: Balance against current food economy and stamina costs
- **New NPCs**: Follow reward philosophy (meaningful but not mandatory)

