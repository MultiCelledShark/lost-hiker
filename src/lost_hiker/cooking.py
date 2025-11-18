"""Cooking system for camp meals in Lost Hiker."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

from .state import GameState


class CookingRecipe:
    """Represents a cooking recipe."""

    def __init__(
        self,
        recipe_id: str,
        name: str,
        requires: Dict[str, int],
        output: str,
        description: str,
        requires_camp: bool = True,
    ):
        self.recipe_id = recipe_id
        self.name = name
        self.requires = requires
        self.output = output
        self.description = description
        self.requires_camp = requires_camp


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

