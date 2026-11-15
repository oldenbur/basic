"""Turn the model's free-text tags into a tidy vocabulary: lowercase, singular nouns, one spelling per idea.
Anything this misses can be merged on the Tags page (merges also apply to future answers)."""

import re

CATEGORIES = ("activity", "scene", "object", "animal", "gear", "vehicle", "landmark")
# Result field -> tag category
FIELDS = {"activities": "activity", "objects": "object", "animals": "animal", "camping_gear": "gear",
          "landmarks": "landmark"}

SYNONYMS = {
    "activity": {
        "downhill skiing": "skiing", "alpine skiing": "skiing", "snow skiing": "skiing", "ski": "skiing",
        "nordic skiing": "cross-country skiing", "xc skiing": "cross-country skiing",
        "cycling": "biking", "bicycling": "biking", "bike riding": "biking", "riding bikes": "biking",
        "riding a bike": "biking", "hockey": "playing hockey", "ice hockey": "playing hockey",
        "trick or treating": "trick-or-treating", "swim": "swimming", "hike": "hiking", "trekking": "hiking",
        "paddle boarding": "paddleboarding", "stand-up paddleboarding": "paddleboarding",
        "sup": "paddleboarding", "rock climbing": "climbing", "bouldering": "climbing",
        "playing in the snow": "playing", "snowball fight": "playing", "barbecuing": "grilling",
        "bbq": "grilling", "having a picnic": "picnicking", "picnic": "picnicking",
        "christmas dinner": "holiday dinner", "thanksgiving dinner": "holiday dinner",
        "unwrapping presents": "opening presents", "opening gifts": "opening presents",
        "sightseeing tour": "sightseeing", "touring": "sightseeing", "posing for a photo": "posing",
        "posing for photo": "posing", "group photo": "posing", "jogging": "running", "boat ride": "boating",
        "riding horses": "horseback riding", "horse riding": "horseback riding",
    },
    "object": {
        "birthday cake": "cake", "xmas tree": "christmas tree", "gift": "present", "jack-o'-lantern": "pumpkin",
        "jack o lantern": "pumpkin", "bike": "bicycle", "skis": "ski", "fire": "campfire", "bonfire": "campfire",
        "firework": "fireworks", "american flag": "flag",
    },
    "animal": {"puppy": "dog", "kitten": "cat", "bighorn": "bighorn sheep"},
    "gear": {"backpacking pack": "backpack", "pack": "backpack", "trekking poles": "trekking pole",
             "hiking pole": "trekking pole", "stove": "camp stove", "folding chair": "camp chair"},
    "vehicle": {"pickup": "pickup truck", "truck": "pickup truck", "automobile": "car", "sedan": "car",
                "plane": "airplane", "jet": "airplane", "motorhome": "rv", "camper van": "camper"},
}
# Plurals that aren't (or whose singular isn't what you'd search for).
KEEP = {"fireworks", "sunglasses", "glasses", "goggles", "pants", "shorts", "jeans", "binoculars", "scissors",
        "clothes", "dishes", "s'mores", "smores", "christmas lights", "lights", "bus", "canvas", "gas", "grass",
        "glass", "cactus", "moss", "dress", "chess", "series", "species"}
IRREGULAR = {"leaves": "leaf", "geese": "goose", "mice": "mouse", "people": "person", "children": "child",
             "wolves": "wolf", "knives": "knife", "loaves": "loaf", "shelves": "shelf", "sheep": "sheep",
             "deer": "deer", "fish": "fish", "elk": "elk", "moose": "moose", "skis": "ski"}

_SPACE = re.compile(r"\s+")


def singular(word: str) -> str:
    if word in IRREGULAR:
        return IRREGULAR[word]
    if word in KEEP or len(word) <= 3:
        return word
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith(("ches", "shes", "sses", "xes", "zes")):
        return word[:-2]
    if word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def normalize(category: str, value: str) -> str | None:
    v = _SPACE.sub(" ", value.strip().lower()).strip(" .,;:!\"'")
    if not v or len(v) > 60:
        return None
    if category in ("object", "animal", "gear", "vehicle") and v not in KEEP:
        *head, last = v.split(" ")
        v = " ".join([*head, singular(last)])
    return SYNONYMS.get(category, {}).get(v, v)


def tags_from(result: dict) -> list[tuple[str, str]]:
    """(category, value) pairs from one answer, normalised and de-duplicated, in answer order."""
    out: list[tuple[str, str]] = []
    if result.get("scene"):
        out.append(("scene", result["scene"]))
    for field, cat in FIELDS.items():
        out += [(cat, v) for v in result.get(field) or [] if isinstance(v, str)]
    for v in result.get("vehicles") or []:
        out.append(("vehicle", v.get("type") or ""))
        if (v.get("make_model") or "").strip():
            out.append(("vehicle", v["make_model"]))
    seen, tags = set(), []
    for cat, raw in out:
        v = normalize(cat, raw) if cat != "landmark" else (_SPACE.sub(" ", raw.strip()) or None)
        if v and (cat, v.lower()) not in seen:
            seen.add((cat, v.lower()))
            tags.append((cat, v if cat == "landmark" else v.lower()))
    return tags
