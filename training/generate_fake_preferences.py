"""Generate sample human preference judgments for the harness.

This produces a small illustrative `data/preferences.jsonl` dataset with
20 fake raters and realistic brief/candidate pairs for the DPO pipeline.
"""
from __future__ import annotations

from pathlib import Path

from app.preference_store import PreferenceStore
from app.schemas import PreferencePair


def build_fake_preferences() -> list[PreferencePair]:
    briefs = [
        "A tense elevator ride late at night.",
        "A neon-lit alley where rain reflects city lights.",
        "A dusty library with sunlight filtering through tall windows.",
        "A rooftop sunset chase above a crowded market.",
        "A hospital corridor lit by flickering fluorescent lights.",
        "A warehouse interior with moving cranes and shafts of light.",
        "A forest clearing at golden hour with mist rising.",
        "A subway car packed with commuters during rush hour.",
        "A quiet kitchen scene early in the morning.",
        "A vintage diner booth conversation under warm neon.",
        "A mountain road bend during a stormy afternoon.",
        "A futuristic lab with glass cylinders and sparking equipment.",
        "A small town square at dusk with lanterns being lit.",
        "A wedding rehearsal in a candlelit chapel.",
        "A chaotic newsroom moments before breaking news.",
        "A ballet rehearsal under a single spotlight.",
        "A jazz club with smoke, close-ups, and rich shadows.",
        "A desert road trip scene with glowing horizon.",
        "A detective interview in a dim police station.",
        "A spacecraft cockpit with blinking panels and Earth below.",
    ]

    judgments = []
    for index, brief in enumerate(briefs, start=1):
        rater = f"rater_{index:02d}"
        candidate_a = (
            "Shot 1: wide establishes the location with motion blur.\n"
            "Shot 2: close-up on the protagonist's expression.\n"
            "Director's note: emphasize atmosphere and sound design."
        )
        candidate_b = (
            "Shot 1: medium framing introduces the main characters.\n"
            "Shot 2: cut to a low-angle detail revealing the threat.\n"
            "Director's note: keep pacing tight and visual contrast strong."
        )
        winner = "a" if index % 2 else "b"
        notes = "Prefers stronger atmospheric detail." if winner == "a" else "Prefers clearer narrative stakes."
        prompt = f"Brief: {brief}\n\nShot list:\n"

        judgments.append(
            PreferencePair(
                brief=brief,
                prompt=prompt,
                candidate_a=candidate_a,
                candidate_b=candidate_b,
                winner=winner,  # type: ignore[arg-type]
                rater=rater,
                notes=notes,
            )
        )
    return judgments


def main(database_url: str | None = None) -> None:
    output_path = Path("data/preferences.jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    prefs = build_fake_preferences()
    output_path.write_text(
        "".join(pref.model_dump_json() + "\n" for pref in prefs),
        encoding="utf-8",
    )

    # Migrate fake preferences into the SQL database for validation and evaluation.
    with PreferenceStore(database_url=database_url) as store:
        store.migrate_from_jsonl(output_path)

    print(f"Generated {len(prefs)} fake preferences to {output_path} and migrated them into the primary database backend.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate fake human preference judgments.")
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Optional SQL database URL to write fake preferences into.",
    )
    args = parser.parse_args()
    main(database_url=args.database_url)
