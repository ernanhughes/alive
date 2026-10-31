"""Immutable catalogue of code-owned YAML recipes, using PI-03A's restricted reader."""

from importlib import resources

from alive.bespoke.contracts import Recipe
from alive.capabilities.bindings import digest
from alive.capabilities.manifest import ManifestError, load_declaration

MAX_RECIPES = 32


def parse_recipe(raw):
    recipe = Recipe.model_validate(load_declaration(raw))
    if len({p.stage_id for p in recipe.capabilities}) != len(recipe.capabilities):
        raise ManifestError("duplicate recipe stage pin")
    for items in (recipe.context_types, recipe.intents, recipe.limits.permissions):
        if len(set(items)) != len(items):
            raise ManifestError("duplicate recipe set item")
    return recipe


def recipe_hash(recipe):
    return digest(recipe.model_dump(mode="json"))


def load_catalogue():
    folder = resources.files("alive.bespoke") / "recipes"
    result = []
    for path in sorted(folder.iterdir(), key=lambda p: p.name):
        if path.name.endswith(".yaml"):
            if len(result) == MAX_RECIPES:
                raise ManifestError("recipe catalogue limit")
            result.append(parse_recipe(path.read_bytes()))
    if len({(r.id, r.version) for r in result}) != len(result):
        raise ManifestError("duplicate recipe identity/version")
    return tuple(result)
