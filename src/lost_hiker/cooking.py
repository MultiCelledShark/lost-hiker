"""
Cooking system for camp meals in Lost Hiker.

This module handles recipe management and cooking mechanics at camp.
Players can combine foraged ingredients into meals and teas.

## Key Concepts:
- CookingRecipe: A recipe with ingredients → output
- CookingCatalog: Collection of all recipes
- Recipes require camp (can't cook while exploring)
- Ingredients are consumed, output is added to inventory

## Recipe System:
Recipes are defined in data/cooking_recipes.json:
{
  "forest_stew": {
    "name": "Forest Stew",
    "requires": {"edible_mushroom": 1, "forest_berries": 1},
    "output": "forest_stew",
    "description": "A hearty stew...",
    "requires_camp": true
  }
}

## For Content Editors:
- Add new recipes to data/cooking_recipes.json
- Define ingredient requirements (item ID: count)
- Set output item (must match item in items_food.json)
- Write description (shown when cooking)
- Most recipes should require_camp: true
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

from .state import GameState


class CookingRecipe:
    """
    A recipe for cooking items at camp.
    
    Recipes consume ingredients from inventory and produce an output item.
    Most recipes require being at camp (can't cook while exploring).
    
    Attributes:
        recipe_id: Unique identifier (e.g., "forest_stew")
        name: Display name (e.g., "Forest Stew")
        requires: Dict of ingredient item_id → quantity needed
        output: Item ID produced by cooking
        description: Flavor text shown when cooking
        requires_camp: Whether recipe needs camp (usually True)
    """

    def __init__(
        self,
        recipe_id: str,
        name: str,
        requires: Dict[str, int],
        output: str,
        description: str,
        requires_camp: bool = True,
    ):
        self.recipe_id = recipe_id  # Unique ID (e.g., "forest_stew")
        self.name = name  # Display name (e.g., "Forest Stew")
        self.requires = requires  # Ingredients: {item_id: quantity}
        self.output = output  # Output item ID
        self.description = description  # Flavor text
        self.requires_camp = requires_camp  # Needs camp? (usually True)


class CookingCatalog:
    """Manages cooking recipes."""

    def __init__(self, recipes: Dict[str, CookingRecipe]):
        self.recipes = recipes

    def get_available_recipes(
        self, state: GameState, at_camp: bool = False
    ) -> Dict[str, CookingRecipe]:
        """
        Get recipes that can be cooked with current inventory.
        
        Args:
            state: Current game state
            at_camp: Whether the player is at camp
            
        Returns:
            Dictionary of available recipes keyed by recipe_id
        """
        inventory_counts = Counter(state.inventory)
        available: Dict[str, CookingRecipe] = {}
        
        for recipe_id, recipe in self.recipes.items():
            # Check camp requirement
            if recipe.requires_camp and not at_camp:
                continue
            
            # Check if all required ingredients are present
            if all(
                inventory_counts.get(item, 0) >= qty
                for item, qty in recipe.requires.items()
            ):
                available[recipe_id] = recipe
        
        return available

    def cook_recipe(
        self, state: GameState, recipe: CookingRecipe
    ) -> tuple[bool, str]:
        """
        Cook a recipe, consuming ingredients and producing output.
        
        Args:
            state: Current game state
            recipe: Recipe to cook
            
        Returns:
            Tuple of (success, message)
        """
        # Check inventory space
        inventory_slots = state.character.get_stat(
            "inventory_slots",
            timed_modifiers=state.timed_modifiers,
            current_day=state.day,
        )
        if len(state.inventory) >= int(inventory_slots):
            return False, "Your bag is full. You'll need to make space first.\n"
        
        # Consume ingredients
        for item, qty in recipe.requires.items():
            for _ in range(qty):
                try:
                    state.inventory.remove(item)
                except ValueError:
                    return False, f"Missing ingredient: {item}\n"
        
        # Add output to inventory
        state.inventory.append(recipe.output)
        return True, f"You cook {recipe.name}. {recipe.description}\n"


def load_cooking_catalog(data_dir: Path) -> CookingCatalog:
    """Load cooking recipes from JSON file."""
    path = data_dir / "cooking_recipes.json"
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    
    recipes: Dict[str, CookingRecipe] = {}
    for recipe_id, data in raw.items():
        recipe = CookingRecipe(
            recipe_id=recipe_id,
            name=str(data.get("name", recipe_id.replace("_", " ").title())),
            requires=dict(data.get("requires", {})),
            output=str(data.get("output", recipe_id)),
            description=str(data.get("description", "")),
            requires_camp=bool(data.get("requires_camp", True)),
        )
        recipes[recipe_id] = recipe
    
    return CookingCatalog(recipes)


def load_food_items(data_dir: Path) -> Dict[str, Dict[str, str]]:
    """Load food item definitions from JSON file."""
    path = data_dir / "items_food.json"
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)

