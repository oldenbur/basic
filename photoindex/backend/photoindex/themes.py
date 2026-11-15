"""Starter themes drafted from the library's event names. Seeded once by `photoindex seed-themes`; edit or delete
them in the UI. Text alternatives are separated by "|" and each word prefix-matches an event-name word."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from photoindex.models import Theme
from photoindex.search import ThemeQuery

WINTER = [12, 1, 2, 3, 4]

STARTER_THEMES: list[tuple[str, ThemeQuery]] = [
    ("Skiing", ThemeQuery(
        text="ski | eldora | abasin | steamboat | winter park | mary jane | keystone | snowmass | telluride"
             " | crested butte | deer valley | big sky | powder | birkie | giants ridge | berthoud",
        months=WINTER)),
    ("Fourteeners", ThemeQuery(
        text="antero | belford | bierstadt | crestones | ellingwood | longs peak | elbert | massive"
             " | missouri gulch | missouri monarch | quandry | sherman | shavano | torreys | uncompagre"
             " | chicago basin | la platta | mt evans")),
    ("Camping & backcountry", ThemeQuery(
        text="camping | bwca | wilderness | weminuche | rawah | sawtooths | eagle cap | seagull | hut | solo"
             " | camp dick | jasper lake | lake evelyn")),
    ("National parks", ThemeQuery(text="np | rmnp | ynp")),
    ("Desert", ThemeQuery(text="moab | fruita | zion | arches | sand dunes | narrows | grand canyon | vedauwoo")),
    ("Hockey", ThemeQuery(text="hockey | loco | tourney | silver sticks | centennial cup")),
    ("Christmas", ThemeQuery(text="xmas | christmas | holiday | ugly sweaters", months=[12, 1])),
    ("Halloween", ThemeQuery(text="halloween | haloween | monster dash")),
    ("Thanksgiving", ThemeQuery(text="thanksgiving")),
    ("Trips abroad", ThemeQuery(states=["abroad"])),
    # These need AI tags (captions and tags are searched too); they fill in as highlights are tagged.
    ("Beach days", ThemeQuery(text="beach | ocean | snorkel")),
    ("On the water", ThemeQuery(text="kayak | canoe | paddleboard | raft | sail | boat | tubing")),
    ("Campfires", ThemeQuery(text="campfire | marshmallow")),
    ("Dogs", ThemeQuery(text="dog")),
    ("Birthdays", ThemeQuery(text="birthday")),
    ("The best of", ThemeQuery(min_score=8)),
]
SORTS = {"The best of": "best"}


def seed(session: Session) -> list[str]:
    """Add any starter theme whose name isn't taken yet. Returns the names added."""
    existing = set(session.scalars(select(Theme.name)))
    added = []
    for name, q in STARTER_THEMES:
        if name not in existing:
            session.add(Theme(name=name, query=q.model_dump(exclude_defaults=True),
                              sort=SORTS.get(name, "event_shuffle")))
            added.append(name)
    session.commit()
    return added
