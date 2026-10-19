"""Normalized, curated exercise catalog backed by the bundled CSV datasets."""

from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


CATALOG_DIRECTORY = (
    Path(__file__).resolve().parents[1] / "db" / "seed_data"
)
GYM_DATASET = CATALOG_DIRECTORY / "gym_exercise_dataset.csv"
STRETCH_DATASET = CATALOG_DIRECTORY / "stretch_exercise_dataset.csv"

# Names are deliberately explicit: the raw files contain movements that are
# too specialized or unsafe to expose as automatic plan candidates.
V1_ALLOWLIST = frozenset(
    {
        # Free weights and compound lifts.
        "barbell bench press",
        "barbell squat",
        "bench press",
        "deadlift",
        "front squat",
        "military press",
        "pull-up",
        "chin-up",
        "squat",
        "stiff-leg deadlift",
        "t-bar row",
        # Dumbbell, kettlebell, and bodyweight options.
        "bird dog",
        "bodyweight squat",
        "dead bug",
        "dumbbell bench press",
        "dumbbell row",
        "front plank",
        "glute bridge",
        "goblet squat",
        "incline push-up",
        "jumping jack",
        "plank",
        "push-up",
        "reverse lunge",
        "romanian deadlift",
        "side plank",
        "step-up",
        "walking lunge",
        # Selectorized, plate-loaded, and Smith-machine options.
        "chest press",
        "hack squat",
        "incline chest press",
        "leg curl",
        "leg extension",
        "leg presses",
        "lateral raise",
        "lat pulldown",
        "pulldown",
        "seated leg curl",
        "seated row",
        "shoulder press",
        "standing calf raise",
        "triceps extension",
        "v-squat",
    }
)

# Stretch-dataset rows reuse generic names ("Seated", "Standing", "Lying")
# across many unrelated muscle groups, so the stretch allowlist keys on the
# (raw name, main muscle region) pair rather than the name alone. These cover
# warm-up/cool-down coverage for the major muscle regions trained in V1 plans.
STRETCH_ALLOWLIST = frozenset(
    {
        ("retraction", "neck"),
        ("neck extensor", "neck"),
        ("doorway", "chest"),
        ("standing side reach", "back"),
        ("supine lat", "back"),
        ("overhead", "upper arms"),
        ("lying", "hips"),
        ("seated", "hips"),
        ("standing", "hips"),
        ("standing", "thighs"),
        ("lying", "thighs"),
        ("wall", "calves"),
        ("standing", "calves"),
    }
)

_EQUIPMENT_ALIASES = {
    "body weight": "bodyweight",
    "bodyweight": "bodyweight",
    "dumbbell": "dumbbell",
    "barbell": "barbell",
    "cable": "cable",
    "kettlebell": "kettlebell",
    "lever (selectorized)": "machine",
    "lever": "machine",
    "lever (plate loaded)": "machine",
    "assisted": "machine",
    "assisted (machine)": "machine",
    "smith": "smith-machine",
    "smith machine": "smith-machine",
    "sled": "machine",
    "sled (selectorized)": "machine",
    "sled (plate loaded)": "machine",
    "weighted": "weighted",
    "band-assisted": "band",
    "band resistive": "band",
    "machine": "machine",
    "stretch": "none",
    "none": "none",
}
_DIFFICULTIES = {
    1: "beginner",
    2: "beginner",
    3: "intermediate",
    4: "advanced",
    5: "advanced",
}
_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class ExerciseCatalogEntry:
    """A stable exercise record used by planners and retrieval indexes."""

    slug: str
    name: str
    equipment: tuple[str, ...]
    difficulty: str
    movement_pattern: str
    primary_muscles: tuple[str, ...]
    preparation: str
    execution: str
    search_text: str
    source_dataset: str


def normalize_text(value: str | None) -> str:
    """Normalize whitespace and remove invisible formatting characters."""
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKC", value).replace("\u200b", " ")
    return _WHITESPACE.sub(" ", normalized).strip()


def _key(value: str) -> str:
    return normalize_text(value).casefold()


def _slug(value: str) -> str:
    return _NON_ALPHANUMERIC.sub("-", _key(value)).strip("-")


def _split_values(value: str | None) -> tuple[str, ...]:
    values = []
    for item in normalize_text(value).split(","):
        item = normalize_text(item)
        if item and _key(item) not in {"none", "n/a"}:
            values.append(item.casefold())
    return tuple(dict.fromkeys(values))


def _equipment(value: str | None) -> tuple[str, ...]:
    raw = normalize_text(value)
    key = _key(raw)
    if "stretch" in key:
        # Stretch-dataset "equipment" values are really muscle annotations
        # (e.g. "Stretch (Piriformis)", "Dynamic Stretch"); no equipment is used.
        return ("none",)
    canonical = _EQUIPMENT_ALIASES.get(key, key)
    return (canonical,) if canonical else ("none",)


def _stretch_display_name(raw_name: str, main_muscle: str) -> str:
    """Disambiguate generic stretch names (e.g. "Seated") with their muscle region."""
    if not main_muscle:
        return raw_name if "stretch" in _key(raw_name) else f"{raw_name} Stretch"
    if _key(main_muscle) in _key(raw_name):
        return raw_name if "stretch" in _key(raw_name) else f"{raw_name} Stretch"
    return f"{raw_name} {main_muscle} Stretch"


def _difficulty(value: str | None, source_dataset: str) -> str:
    if source_dataset == "stretch":
        return "beginner"
    try:
        return _DIFFICULTIES[int(normalize_text(value))]
    except (KeyError, TypeError, ValueError):
        return "intermediate"


def _movement_pattern(name: str, muscles: Iterable[str], source_dataset: str) -> str:
    # Stretch-dataset rows are warm-up/cool-down mobility work, not a strength
    # pattern, regardless of which muscle keywords their names happen to contain.
    if source_dataset == "stretch":
        return "mobility"

    text = f"{_key(name)} {' '.join(muscles)}"
    for pattern, terms in (
        ("hinge", ("deadlift", "good morning", "hamstring")),
        ("squat", ("squat", "leg press")),
        ("lunge", ("lunge", "split squat", "step-up")),
        ("push", ("press", "push-up", "pushup", "triceps", "chest")),
        ("pull", ("row", "pull-up", "latissimus", "biceps")),
        ("core", ("plank", "dead bug", "abdominal", "oblique")),
        ("carry", ("carry", "walk")),
        # "flexion"/"extension" are deliberately excluded: they are generic
        # anatomical terms that also appear in ordinary strength exercises
        # (e.g. "Leg Extension", "Back Extension"), not reliable mobility
        # signals outside the stretch dataset handled above.
        ("mobility", ("stretch",)),
    ):
        if any(term in text for term in terms):
            return pattern
    return "full-body"


def _is_allowed(
    raw_name: str,
    main_muscle: str,
    source_dataset: str,
    allowlist: frozenset[str],
    stretch_allowlist: frozenset[tuple[str, str]],
) -> bool:
    if source_dataset == "stretch":
        return (_key(raw_name), _key(main_muscle)) in stretch_allowlist
    return _key(raw_name) in allowlist


def _entry(row: dict[str, str], source_dataset: str) -> ExerciseCatalogEntry:
    raw_name = normalize_text(row.get("Exercise Name"))
    main_muscle = normalize_text(row.get("Main_muscle"))
    muscles = _split_values(f"{row.get('Target_Muscles') or ''},{main_muscle}")
    name = (
        _stretch_display_name(raw_name, main_muscle)
        if source_dataset == "stretch"
        else raw_name
    )
    preparation = normalize_text(row.get("Preparation"))
    execution = normalize_text(row.get("Execution"))
    equipment = _equipment(row.get("Equipment") or source_dataset)
    difficulty = _difficulty(row.get("Difficulty (1-5)"), source_dataset)
    movement_pattern = _movement_pattern(name, muscles, source_dataset)
    search_text = " ".join(
        part
        for part in (
            name,
            " ".join(equipment),
            difficulty,
            movement_pattern,
            " ".join(muscles),
            preparation,
            execution,
        )
        if part
    )
    return ExerciseCatalogEntry(
        slug=_slug(name),
        name=name,
        equipment=equipment,
        difficulty=difficulty,
        movement_pattern=movement_pattern,
        primary_muscles=muscles,
        preparation=preparation,
        execution=execution,
        search_text=search_text,
        source_dataset=source_dataset,
    )


def load_exercise_catalog(
    gym_path: Path = GYM_DATASET,
    stretch_path: Path = STRETCH_DATASET,
    *,
    allowlist: frozenset[str] = V1_ALLOWLIST,
    stretch_allowlist: frozenset[tuple[str, str]] = STRETCH_ALLOWLIST,
) -> tuple[ExerciseCatalogEntry, ...]:
    """Load, curate, normalize, and deduplicate the bundled exercise files."""
    candidates: dict[tuple[str, tuple[str, ...]], ExerciseCatalogEntry] = {}
    for path, source_dataset in ((gym_path, "gym"), (stretch_path, "stretch")):
        with path.open("r", encoding="utf-8-sig", newline="") as dataset:
            for row in csv.DictReader(dataset):
                raw_name = normalize_text(row.get("Exercise Name"))
                main_muscle = normalize_text(row.get("Main_muscle"))
                if not raw_name or not _is_allowed(
                    raw_name, main_muscle, source_dataset, allowlist, stretch_allowlist
                ):
                    continue
                entry = _entry(row, source_dataset)
                key = (entry.slug, entry.equipment)
                existing = candidates.get(key)
                if existing is None or (
                    existing.source_dataset == "gym" and source_dataset == "stretch"
                ):
                    candidates[key] = entry

    entries_by_name: dict[str, list[ExerciseCatalogEntry]] = {}
    for entry in candidates.values():
        entries_by_name.setdefault(entry.slug, []).append(entry)

    entries: list[ExerciseCatalogEntry] = []
    for name_slug, variants in entries_by_name.items():
        for entry in sorted(variants, key=lambda item: item.equipment):
            slug = name_slug
            if len(variants) > 1:
                slug = f"{name_slug}-{'-'.join(entry.equipment)}"
            entries.append(
                ExerciseCatalogEntry(
                    slug=slug,
                    name=entry.name,
                    equipment=entry.equipment,
                    difficulty=entry.difficulty,
                    movement_pattern=entry.movement_pattern,
                    primary_muscles=entry.primary_muscles,
                    preparation=entry.preparation,
                    execution=entry.execution,
                    search_text=entry.search_text,
                    source_dataset=entry.source_dataset,
                )
            )
    return tuple(sorted(entries, key=lambda entry: entry.slug))
