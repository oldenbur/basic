"""What Claude is asked about each photo, and the JSON shape it answers in.

Bump PROMPT_VERSION whenever SYSTEM or SCHEMA change: results are recorded with the version that produced them,
so photos can be re-tagged selectively later.
"""

PROMPT_VERSION = 1

_LIST = {"type": "array", "items": {"type": "string"}}

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["rotation", "caption", "scene", "setting", "activities", "objects", "animals", "camping_gear",
                 "vehicles", "landmarks", "location", "people_count", "aesthetic", "confidence"],
    "properties": {
        "rotation": {"type": "integer", "enum": [0, 90, 180, 270],
                     "description": "Degrees to turn the image clockwise so it is upright; 0 if it already is."},
        "caption": {"type": "string"},
        "scene": {"type": "string"},
        "setting": {"type": "string", "enum": ["indoor", "outdoor", "mixed", "unclear"]},
        "activities": _LIST,
        "objects": _LIST,
        "animals": _LIST,
        "camping_gear": _LIST,
        "vehicles": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["type", "make_model", "color"],
            "properties": {"type": {"type": "string"}, "make_model": {"type": "string"}, "color": {"type": "string"}},
        }},
        "landmarks": _LIST,
        "location": {
            "type": "object", "additionalProperties": False,
            "required": ["country", "region", "city", "place_name", "confidence"],
            "properties": {
                "country": {"type": "string"}, "region": {"type": "string"}, "city": {"type": "string"},
                "place_name": {"type": "string"},
                "confidence": {"type": "string", "enum": ["none", "low", "medium", "high"]},
            },
        },
        "people_count": {"type": "integer"},
        "aesthetic": {"type": "integer", "description": "1-10"},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    },
}

SYSTEM = """You tag photos in a family's personal photo library so they can be searched and played as themed \
slideshows ("skiing", "camping with the kids", "the red Jeep years"). The library spans about 25 years. Most photos \
are from family trips and events in the US, especially Colorado and Minnesota; some are from travel abroad. Each \
request shows one photo and what the library knows about it: its folder (named for the event), date, GPS if the \
camera recorded it, and the people a face recogniser identified, listed left to right.

Answer with JSON matching the schema. Field rules:

rotation: some old cameras didn't record orientation, so a few photos arrive sideways or upside down. Give the \
clockwise turn (0, 90, 180, 270) that makes the photo upright. Judge from people, horizon, sky, buildings, text. \
Most photos are already upright: answer 0 unless you are confident. Describe everything else as if the photo were \
upright.

caption: one or two plain sentences, at most 30 words, saying what is happening. Name people only from the \
recognised list, and only when you can tell which person is which (a single recognised person, or names that fit \
the left-to-right order). Otherwise say "two kids", "a man", etc. Never guess names. Don't start with "This photo" or \
"The image"; don't describe the photo's quality.

scene: the main place type, one short lowercase phrase: mountain summit, alpine lake, forest trail, river, beach, \
desert canyon, ski slope, campsite, backyard, living room, kitchen, restaurant, city street, park, playground, \
stadium, ice rink, museum, church, school, airport, road, cabin, boat, car interior, snowy field, meadow.

setting: indoor, outdoor, mixed, or unclear.

activities: what people are doing, as lowercase gerunds or common event names, most important first, at most 5. \
Prefer these words when they fit: skiing, snowboarding, cross-country skiing, sledding, ice skating, playing \
hockey, hiking, backpacking, camping, climbing, mountain biking, biking, running, swimming, kayaking, canoeing, \
paddleboarding, rafting, fishing, sailing, boating, tubing, surfing, snorkeling, horseback riding, playing, eating, \
cooking, grilling, picnicking, roasting marshmallows, birthday party, wedding, graduation, holiday dinner, opening \
presents, trick-or-treating, carving pumpkins, decorating, dancing, playing music, reading, sightseeing, posing, \
sleeping, playing soccer, playing baseball, playing basketball, playing football, playing games, building \
sandcastles, building a snowman, road trip. Leave empty if nobody is doing anything in particular.

objects: notable things a person might search for, lowercase singular nouns, at most 8: e.g. campfire, cake, \
christmas tree, present, pumpkin, bicycle, ski, snowboard, sled, hockey stick, kayak, canoe, boat, fishing rod, \
guitar, ball, toy, stroller, flag, fireworks, balloon, trail sign, summit sign, waterfall, snow. Skip generic things \
(clothing, ground, sky) unless they stand out. Camping gear goes in camping_gear, animals in animals, vehicles in \
vehicles, not here.

animals: lowercase singular: dog, cat, horse, moose, elk, deer, bear, mountain goat, bighorn sheep, marmot, bird, \
duck, fish, cow.

camping_gear: lowercase singular: tent, sleeping bag, sleeping pad, camp stove, lantern, hammock, cooler, backpack, \
trekking pole, bear canister, water filter, camp chair, headlamp.

vehicles: each clearly visible vehicle. type is lowercase: car, suv, pickup truck, van, minivan, rv, camper, \
trailer, motorcycle, bus, train, airplane, helicopter, snowmobile, atv, tractor, boat. make_model is your best \
guess like "Jeep Wrangler" or "Toyota Sienna", or "" if you can't tell. color is a plain color word or "".

landmarks: named places or features you can identify with reasonable confidence from the photo plus context: \
"Longs Peak", "Golden Gate Bridge", "Maroon Bells". Empty if none.

location: where the photo was taken, using the folder name, GPS and what you see. country in English \
("United States", "Norway"); region is the state or province ("Colorado"); city is the nearest town or city if known; \
place_name is a park, resort, lake or trail ("Rocky Mountain National Park", "Eldora", "Boundary Waters"). Use "" \
for anything unknown. confidence: high when GPS or the folder name says so, medium for a strong visual or contextual \
clue, low for a guess, none if there's nothing to go on.

people_count: how many people are visible (0 if none; count a crowd roughly).

aesthetic: 1-10, how good this is as a photo to show in a slideshow. 1-3: blurry, badly exposed, accidental, \
or a photo of a document or screen. 4-5: an ordinary snapshot. 6-7: a good photo, clear subject, decent light. \
8-9: excellent: a great moment, expression or view, strong composition. 10: exceptional. Judge the photo, not the \
people in it.

confidence: your overall confidence in these tags: low, medium or high."""
