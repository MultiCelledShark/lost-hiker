# Lost Hiker - Master Design Document

## 1. Setting & World Lore

The game unfolds in a vibrant yet perilous fantasy world where the player, an ordinary hiker, is abruptly transported from the modern real world through a mystical runic tree portal during a raging thunderstorm. A mysterious hooded figure—revealed as a reclusive wizard experimenting with unstable portal magic—attempts to warn the player just before the transfer. This wizard resides in isolation within the lakeside town on a central island.

The elder dragon perched atop the distant mountain peak holds the key to stabilizing a return portal home. The world is alive with dynamic seasonal cycles that transform the landscape:
- **Winter**: Bare trees cloaked in snow, frozen streams, and biting winds.
- **Spring**: Flowering trees swaying in gentle breezes, bubbling streams, and renewed life.
- **Summer**: Lush green foliage, warm sunlight filtering through leaves, and vibrant streams.
- **Fall**: Golden grasses rustling, colorful autumn leaves, and quiet, reflective waters.

The expansive lake serves as a self-contained saltwater sea teeming with exotic marine life. The overall atmosphere is tense and mysterious, blending portal fantasy tropes with an edgy tone that embraces dark, violent, or intensely adult themes in a fictional context.

## 2. Story & Plot

As a lost hiker thrust into this alien realm, the player's primary goal is to find a way back home. The core narrative arc involves:
- Arriving disoriented in the central Glade.
- Venturing to the lakeside island town via docks, mingling with NPCs in the local bar to gather rumors about the hooded wizard.
- Building relationships through fetch quests, guided escorts, and rapport-building interactions to acquire essential gear.
- Scaling the mountain path to consult the wise elder dragon for portal insights.
- Confronting the wizard to activate a stable return portal.

Branching paths emerge through seasonal variations, such as snow-blocked mountain trails in winter, a harvest festival in fall, or a flower festival in spring, altering quests and encounters. Endings remain **[TBD]**. Success hinges on forging NPC alliances, solving environmental puzzles, and taming creatures for aid.

## 3. Zones to Explore

The world is divided into interconnected zones, each with unique terrain, seasonal flavors, and progression gates (e.g., tools like axes or picks unlock paths). Exploration uses action-based movement with buffers that shorten on repeat visits.

- **Glade**: The safe central hub, nestled deeper west in the forest. Seasonal visuals shift dramatically: snow-dusted bare trees in winter, blooming canopies in spring, verdant lushness in summer, and golden foliage in fall.
- **Forest Path/Forest**: South from the Glade; initial trips require 10-15 actions (shortening to 5-7 on second, direct access thereafter). Brambles block the western mountain route until cleared with an axe; a winding stream leads to Dock 1.
- **Forest Exploration Loop (Prototype)**: Each in-game day, the player has stamina_max exploration steps.
  Each step in the Forest:
    Triggers one event (forage, encounter, hazard, or flavor).
    Costs 1 stamina (unless modified).
    Ends with a choice:
    Continue deeper into the forest
    Make camp here (end day + summary)
    Return to the Glade (end day + summary)
  Depth:
    Track a simple depth counter per day (0 = edge, 1–2 = mid, 3+ = deep).
    Event odds change with depth (safer near edge, more predators deeper).
  End of day:
    Day only advances on Camp/Return/Collapse.
    Camp summary shows: day, stamina reset, inventory changes, rapport changes.
- **Mountain Path/Peak Temple**: West from the Glade, initially bramble-blocked. Follow the stream to foothills and Waterfall 1 (pickaxe needed for rockslides). Culminates at the elder dragon's peak temple.
- **Plains**: North/east from the Glade; buffer of 2-8 actions initially, then direct. Expansive treks (20-30 actions max) to Dock 2 across open grasslands.
- **Lake**: Vast saltwater sea north of the Glade, with the island town at its heart. Access via Dock 1 (south shore, stream-unlocked, 1 action slot) or Dock 2 (east shore, Plains-unlocked, 1 slot). Risky swims possible with a stash pack (1 slot, prone to gulps); winter allows ice traversal with sleds.
- **Waterfall 1**: Adjacent to the mountain, feeding serene pools; frozen solid in winter, swimmable in summer.
- **Waterfall 2**: Towering on the lake's northeast shore, enveloped in perpetual mist with a deafening roar echoing into town. Ideal for dramatic rapport-building scenes revealing under-lake lore.
- **Cave Opening**: East near Plains/Dock 2; subterranean gateway to fungal forests, mycelial fields, and under-lake caverns, blocked by cave-ins.

## 4. Creatures by Zone

Creatures are predatory or tamable beasts with distinct behaviors, appearances, and vore potential. Taming unlocks summoning, carrying, and escort services.

### Forest
- **Red Wolf**: Lithe pack hunter with reddish fur, issuing yipping warnings before strikes.
- **Grey Wolf**: Stealthy loner cloaked in silver pelt, communicating via low, ominous growls.
- **Timber Wolf**: Burly forest brute with thick, bark-mimicking fur and deep, echoing howls.
- **Dire Wolf**: Massive prehistoric relic with scarred maw and thunderous roars.
- **Bear (Grizzly)**: Lumbering powerhouse, honey-scented, delivering devastating claw swipes.
- **Coyote**: Scavenger trickster in yipping packs, expert at sly dodges.
- **Giant Centipede**: Writhing burrower with venomous legs and eerie chittering; rare, hints at underground realms.
- **Boar**: Tusked charger with bristly hide and aggressive grunts.
- **Owl**: Silent glider with wise, piercing eyes; hoots cryptic riddles; rare.
- **Deer**: Graceful fleetfoot with antler clashes; herbivorous predator.
- **Glow Elk**: Ethereal deer adorned with bioluminescent antlers; ideal starter tame, neutral on first encounter.
- **Dragon-Wolf**: Intelligent wild NPC that mimics dire wolf ferocity until tamed via belly interaction; special.
- **Echo**: Radio-attuned snake guardian, friendly recurring ally warped by portal energies.

### Plains
- **Raptor Pack**: Sleek saurian hunters with feathered quills, launching screeching chases.
- **T-Rex**: Apex tyrant unleashing earth-shaking roars from its massive maw.
- **Hadrosaur Pack**: Duckbilled herd with crested trumpets and charging stampedes.
- **Dire Raptor**: Ferocious larger kin with expanded maw and feral screeches.
- **Long-Necked Dino**: Slender sauropod using whip-like neck lashes; high-browser, smaller than the Thunder Lizard.
- **Gryphon**: Mountain swooper, a lion-eagle hybrid generating wing gusts.
- **Stridebird Pack**: Speedy bird-runners with fluffy plumes and distinctive "kweh" calls.
- **Giant Bird (Roc)**: Colossal sky diver with thunderous wings that eclipse the sun in shadow.
- **Pitfall Insect (Sand Beetle)**: Burrowing gobbler with clacking mandibles erupting from below; teases cave/water links.
- **Sand Worm**: Subterranean gulper with segmented maw, ambushing via quakes.
- **Mirage Spirit**: Illusory hunger lure manifesting shimmering forms and whispering temptations.
- **Thrumbo**: Tanky rhino-elephant hybrid with silver fur and horned charges; predator-only, huntable for fur.
- **Horse Herd**: Feral stampeding steeds with mane-whipped charges and whinny lures; herbivorous predators.
- **Antelope Herd**: Lithe leapers executing horned chargers amid dust clouds; herbivorous predators.
- **Jackalope**: Horned hare scout hopping with illusion lures; cryptid, predator-focused tame.
- **Thunder Lizard**: Colossal sauropod with storm-roaring breath and thunderous tail sweeps; cryptid power escort tame.

### Lake
- **Orcas**: Aquatic predators, hostile in open water until tamed; edge-tameable.
- **Eels**: Swarming gulpers delivering instant swallows during swims.

### Waterfall 1
- **Pool Beast**: Aquatic ambush predator that lurks in the plunge pool; bargains for items or offers vore rides.

### Waterfall 2
- **Pool Beast**: Larger, mist-shrouded variant with the same bargain/vore behavior; roar audible in town.

## 5. Non-Combat Features

- **Character Creation**: Customize name, height, build, gender, and race. Presets (human/elf/dwarf/gnome/halfling: prey-only). Custom races include wolfkin (fur/paws/panting), lizardkin (scales/claws/cold-sensitive), avians (feathers/talons/light bones), dragonkin (scales/claws/wings + subtype powers), slime folk (amorphous/absorbent/regenerative/dry-sensitive), or herbivorous cow-kin (hooves/horns/grazing). Seasonal gear auto-adjusts (e.g., poofy jacket in winter, swimwear in summer).
- **Inventory Management**: 
  - **Backpack**: Exactly 20 slots (consumables deplete on use).
  - **Personal slots**: 4 fixed items (bottle, phone, belt knife, HT radio).
  - Expanded via camp storage (10 slots) or tamed creatures (5 slots each).
- **Herb Gathering & Brewing**: Forage scene-specific herbs (e.g., soothing mint for calming tea, bramble root for axe polish). Herbs wilt over time; brew at camp (1 slot) for buffs like acid negation or beast calming.
- **Camping**: Set up mid-trail or at night to reset exhaustion (-1 meal or free grazing for herbivores). Triggers events like tame visits for rapport, intimate scenes, or vore teases.
- **Time & Seasons**: 4 slots per day (1-2 explore, 1 camp); night camps advance days. Seasons shift every 14 days, impacting everything.
- **Tech Gadgets**:
  - **Phone battery**: 10 charges total. Find-My app: 1 charge per summon, maximum 10 summons.
  - **HT radio**: 10 charges total. Used for pings to maintain rapport.
  - **Solar panel**: Charges at camp (spring/summer: 1–5 charges; winter: 0).
- **Rune Meditation**: At standing stones, guess combos for lore/knowledge (e.g., peace tea recipe).
- **Exploration Mechanics**: Zone buffers shorten with familiarity; turn-back options; infinite east forest loops for rare farming; 40-action forced Glade return with ally cameos (+rapport).
- **Resource Decay**: Rapport (decays after 3 days without ping, min 0 removes channel); runes (1/7 daily decay, cap 5); herbs (10% daily wilt). Race mods recalibrated per action.

## 6. Puzzle System

Puzzles blend environmental interaction, reaction choices, and mini-games, often season/race/gear-modified.

- **Rune Combos**: At runic trees, caves, or stones—examine 3× for hints (scratched lists), 4 guesses unlock teleports/achievements. Meditation reveals knowledge (e.g., peace tea).
- **Reaction Phases**: In encounters—choose fight/flight/freeze/reverse, influenced by race/gear/season.
- **Vore Escape Rhythm**: Match gurgle patterns after second feel.
- **Fetch Quests**: Dock 1—backtrack to pools for hat bargain; Dock 2—retrieve cave tobacco pouch/pipe.
- **Bargains**: Haggle with NPCs/monsters via vore rides or fetches.
- **Forage Challenges**: Season-dependent yields in scenes.
- **Illusions**: Resist mirage lures or face vore teases.
- **Digging**: Burrow quakes favor clawed races (e.g., lizardkin bonus).
- **Hunts**: Thrumbo struggles yield fur (no tame).

## 7. Vore System

**Toggle**: Fully optional, with player-as-predator sub-toggle. Bidirectional (prey or pred).

**Triggers**:
- Failed encounter reactions.
- Exhaustion collapses (1/4 chance).
- Quests (belly rides as shortcuts).
- High-rapport camping (bed offers, night teases).

**Escape Mini-Game**: 3–5 turns total.  
- **Feel** action unlocks map/items/rhythm **starting on the player’s 2nd turn** inside the stomach.  
- Other actions: radio talk, item use, struggle, relax/massage.  
- Friendly creatures grant +1–2 extra turns; failed reverse costs –1 turn.

**Outcomes**:
- Taming progress (3–6 threshold unlocks summon channel; herds enable multi-tames).
- **Pack handling**: Large predators retain the player’s pack 40–60% of the time. Player may recover it with a successful **FEEL** or **MASSAGE** action.
- Practice scenes (summon for safe gulps/escorts, +rapport).
- Digestion phases **[TBD]**.

**No permadeath**: Reset to Glade/tree with penalties (lost pack until retrieved; self-inventory only).

**Integration**:
- Exploration: Pitfall gulps tease caves/water.
- Combat: Reverse gulps enable taming.
- Non-combat: Belly rides shortcut travel; tames carry extra supplies.

## 8. Non-Vore Combat System

**Reaction Phase**: Initial choice—fight/flight/freeze—modified by race/gear/season/environment (e.g., yell scares branch-dwellers, knife/trowel strikes, hooves kick, claws slash; winter slips hooves).

**Evasion**: Flight succeeds easily vs. slow foes, risky vs. fast packs.

**Tools & Environment**: Teas calm beasts; axe clears brambles; pickaxe navigates rockslides.

**Stamina/Exhaustion**:
- +1 exhaustion per action without camp.
- **Exhaustion ≥ 2**: Optional camp prompt.
- **Exhaustion ≥ 4**: Forced collapse → reset to Glade.
- Camp resets exhaustion; race mods (e.g., lizardkin +1 cold penalty in winter).

**No permadeath**: Failures reset to Glade/tree; penalties include stolen packs (recover via ping/track).

## TODO (for implementation)
- [ ] Define final endings (good/bad/neutral).
- [ ] Flesh out digestion phases (safe, tingling, melting, etc.).
- [ ] Confirm Pool Beast exact stats/mechanics.
- [ ] Decide exact slot counts for future storage upgrades.