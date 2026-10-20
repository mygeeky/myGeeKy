"""How you move around: six groups, their sections, and a section's parts -- the orbit zoom and the folded dock.

Tap a group and its sections take its place, with a back planet first (in the colour of where it goes, named
after it); tap a section with parts and its parts appear the same way; tap a part to open it. The panel's planet
row works this way; the phone's orbit and folded dock too (lib/nav-tree.ts, the same groups and rules;
tests/test_navtree.py checks they agree).

Each app hangs its own pages under the groups (the panel has a Market tab where the phone has Papers and AI
models), so a tree is built per app; what's shared is the groups, their order, and how a level is shown.
"""

from __future__ import annotations

from typing import Any

# the groups: id, name, colour, and the line icon each app draws for them
GROUPS = [
    {"id": "you", "label": "You", "color": "#ffd24a"},
    {"id": "grow", "label": "Grow", "color": "#4ade80"},
    {"id": "world", "label": "World", "color": "#eab308"},
    {"id": "circle", "label": "Circle", "color": "#ff6fd8"},
    {"id": "repos", "label": "Repos", "color": "#7fd8ff"},
    {"id": "chances", "label": "Chances", "color": "#f472b6"},
]
ROOT_LABEL = "All"          # what the back planet says on the way out of a group
MAX_PER_ROW = 6             # the folded dock's rows: a group's parts in one row up to six, else two


def node(id_: str, label: str, color: str = "", icon: str = "", tab: str = "", part: str = "",
         children: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"id": id_, "label": label, "color": color, "icon": icon, "tab": tab, "part": part, "children": children or []}


def finish(root: dict[str, Any]) -> dict[str, Any]:
    """Children inherit their parent's colour, and every node learns its parent (for the back planet)."""
    def walk(n: dict[str, Any], parent: dict[str, Any] | None) -> None:
        n["parent"] = parent
        n["color"] = n["color"] or (parent["color"] if parent else "#ff6fd8")
        for c in n["children"]:
            walk(c, n)
    walk(root, None)
    return root


def find(root: dict[str, Any], id_: str) -> dict[str, Any] | None:
    if root["id"] == id_:
        return root
    for c in root["children"]:
        hit = find(c, id_)
        if hit:
            return hit
    return None


def path(n: dict[str, Any] | None) -> list[dict[str, Any]]:
    out = []
    while n is not None:
        out.insert(0, n)
        n = n["parent"]
    return out


def first_leaf(n: dict[str, Any]) -> dict[str, Any]:
    return first_leaf(n["children"][0]) if n["children"] else n


def walk(root: dict[str, Any]) -> list[dict[str, Any]]:
    """Every node, parents before children, in order."""
    out = [root]
    for c in root["children"]:
        out.extend(walk(c))
    return out


def leaf_for(root: dict[str, Any], tab: str, part: str = "") -> dict[str, Any] | None:
    """The page you're on: the node for this tab and part; else the tab's own node (its first page, if it has
    parts); else the first page of that tab anywhere."""
    nodes = walk(root)
    exact = next((n for n in nodes if n["tab"] == tab and n["part"] == part and not n["children"]), None)
    if exact:
        return exact
    own = next((n for n in nodes if n["tab"] == tab and not n["part"]), None)
    if own:
        return first_leaf(own) if own["children"] else own
    return next((n for n in nodes if n["tab"] == tab and not n["children"]), None)


def level(at: dict[str, Any]) -> dict[str, Any]:
    """What a level shows: a back planet (where it goes, and what it says) unless at the top, then the children."""
    parent = at["parent"]
    back = None if parent is None else {"to": parent["id"], "label": ROOT_LABEL if parent["parent"] is None else parent["label"],
                                        "color": parent["color"]}
    return {"back": back, "items": [c["id"] for c in at["children"]]}


def rows(count: int) -> list[int]:
    """How many planets go in each row of the folded dock."""
    if count <= MAX_PER_ROW:
        return [count]
    first = (count + 1) // 2
    return [first, count - first]


def tap(root: dict[str, Any], at_id: str, picked_id: str, open_id: str) -> dict[str, str]:
    """A planet was tapped at a level: where the level goes and which page is open now.

    A planet with parts becomes the level (and opens its first page, unless you're already on one of its pages);
    a page opens and the level stays; the back planet ("back") goes up a level and keeps the page."""
    at, opened = find(root, at_id) or root, find(root, open_id)
    if picked_id == "back":
        return {"at": (at["parent"] or root)["id"], "open": open_id}
    picked = find(root, picked_id)
    if picked is None:
        return {"at": at["id"], "open": open_id}
    if picked["children"]:
        keep = opened is not None and picked in path(opened)
        return {"at": picked["id"], "open": open_id if keep else first_leaf(picked)["id"]}
    return {"at": at["id"], "open": picked["id"]}


def ordered(ids: list[str], has_github: bool, needs_github: tuple[str, ...]) -> list[str]:
    """Without GitHub, the pages that would only say "add GitHub" go last in their group."""
    if has_github:
        return list(ids)
    return [i for i in ids if i not in needs_github] + [i for i in ids if i in needs_github]
