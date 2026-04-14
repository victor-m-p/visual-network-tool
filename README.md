# Collaborator Guide — otreesurvey

This document describes the overall structure, the six core
experiment pages, and which parts are not in active use.

## Project layout

```
otreesurvey/
├── otreesurvey_app/        ← the entire experiment lives here
│   ├── __init__.py         ← all page classes, player fields, page_sequence
│   ├── templates/
│   │   └── otreesurvey_app/  ← one .html file per page
│   ├── dynamic_items.py    ← 13 predefined belief stances
│   ├── study_config.py     ← study-level settings (label, consent text, etc.)
│   ├── llm_prompts.py      ← prompts used by the LLM interviewer
│   ├── interview_001.py    ← for testing if you do not want to always do an interview to get to other pages.
│   ├── interventions.py    ← intervention content (not in active page sequence: can be deleted.)
│   └── static/             ← JS/CSS assets
├── settings.py             ← oTree settings (apps, auth, database URL, etc.)
├── requirements.txt
└── db.sqlite3              ← local dev database (not committed)
```

The two things that matter most are the `__init__.py` file and the `templates/` folder.
Everything else is support code.

---

## The active page sequence

Only these pages are wired into `page_sequence` in `__init__.py`:

```python
page_sequence = [
    Consent,
    LinkNoConsent,
    ConditionSelector,
    # Interview condition only:
    Information,
    InterviewMain,          # repeated C.MAX_TURNS times
    ConversationFeedback,
    # Both conditions:
    DynamicBeliefRating,
    MapVideoIntro,
    MapIntro,
    MapNodePlacement,
    MapEdgePos,
    MapEdgeNeg,
    CanvasFeedback,
    Feedback,
    LinkCompletion,
]
```

Currently I was testing a version of the canvas without the interview.
There are many pages that can be deleted as well, below I explain the core pages that you will focus on.

---

## The six core pages

### 1. Interview

**Class:** `InterviewMain` (in `__init__.py:830`)
**Template:** `InterviewMain.html`

A multi-turn LLM-driven interview. The participant answers an opening question,
and the LLM generates a follow-up question after each answer. Runs for
`C.MAX_TURNS` turns. Supports both text and voice input. Only shown in
interview conditions.

The opening question and system prompt are in `llm_prompts.py`.
For this part it might be better to refer to the "Scientist Survey" project by Florian.

---

### 2. Stance detection (background, during conversation feedback)

**Class:** `ConversationFeedback` (in `__init__.py:907`)
**Template:** `ConversationFeedback.html`

While the participant fills out a short feedback questionnaire about the
interview (how it felt, how relevant it was, etc.), the page runs a background
LLM call via `live_method`. The LLM receives the full interview transcript and
identifies which of the 13 predefined stances the participant expressed.

The prompt is built by `make_node_prompt()` (from `llm_prompts.py`) and the
call targets GPT-4.1. Results are enriched by `enrich_detected_stances()` and
stored in:

- `player.generated_nodes` — JSON list of detected stances
- `player.num_nodes` — count of detected stances
- `player.llm_result` — raw LLM output for debugging

So in this case we will be using an LLM to detect which stances are expressed in the interview.
In the other versions (the original VN Tool, and the project that Florian works on), we extract
"open stances". But it happens in the same place (i.e., in the background on the same page).

---

### 3. Node rating

**Class:** `DynamicBeliefRating` (in `__init__.py:1949`)
**Template:** `DynamicBeliefRating.html`

For each stance that was detected (or all 13 in non-interview conditions), the
participant rates their **agreement** (1–6 scale, no midpoint) and
**importance**. These two ratings become the properties of each node
on the belief map: agreement → node color, importance → node size.

The 13 stances are defined in `dynamic_items.py` as `DYNAMIC_ITEMS`. Each item
has a sentence template, scale labels, anchors, and an LLM codebook.

The output of this page is stored in `player.final_nodes` (JSON) and
`player.num_nodes`. All subsequent canvas pages read from `final_nodes`.

For the other projects (original + Florian), we are using a different scale (e.g., 101-point),
and rating the items that are detected by the LLM (not predefined). So this will need to be
as flexible as possible. Might be good to have a configuration document where users can specify
the questions that need to be rated and the scales (i.e., 7-point, 100-point, anchors...)

---

### 4. Spatial arrangement

**Class:** `MapNodePlacement` (in `__init__.py:1502`)
**Template:** `MapNodePlacement.html`

The participant drags belief nodes onto a circular canvas to arrange them
spatially. Node positions are saved as `player.positions_1` (JSON array of
`{label, x, y}`). Node appearance (color, radius) comes from
`get_node_display_data(player)`.

---

### 5. Supporting connections

**Class:** `MapEdgePos` (in `__init__.py:1532`)
**Template:** `MapEdgePos.html`

The participant draws supporting (positive) connections between nodes. Inherits
node positions from `positions_1`. Saves updated positions as `positions_2` and
edges as `edges_2`.

---

### 6. Conflicting connections

**Class:** `MapEdgeNeg` (in `__init__.py:1648`)
**Template:** `MapEdgeNeg.html`

The participant draws conflicting (negative) connections between nodes. Inherits
node positions from `positions_2` (falls back to `positions_1`) and prior edges
from `edges_2`. Saves updated positions as `positions_3` and all edges as
`edges_3`.

---

## What is not in active use

The following page classes exist in `__init__.py` but are **not** in
`page_sequence` and are not needed for the core flow. They are legacy or
experimental pages that can be ignored when building new functionality:

- `BeliefRating` — earlier rating format, superseded by `DynamicBeliefRating`
- `DirectBeliefRating` — another earlier rating variant
- `TrainingBrief`, `TrainingIntro1/2/3`, `TrainingMap1/2/3`, `TrainingPos1/2/3`, `TrainingNeg1/2/3` — a training sequence that is no longer used
- `MapEdgeCreation`, `MapEdgeReview`, `MapPractice` — earlier canvas interaction variants
- `MapProximity` — experimental auto-edge generation from node proximity
- `MapVideoIntro`, `MapIntro` — intro/tutorial pages still in sequence but essentially pass-through
- `VEMI`, `MEMI` — mental imagery measures, not part of current study
- `MeatScale` — single-item scale, not in current flow
- `Plausibility` — plausibility rating, not in current flow
- `InterventionDisplay`, `InterventionRating` — intervention conditions, defined in `interventions.py`, not currently used
- `PairInterview`, `PairInterviewLLM` — paired interview variants, not used
- `PreviewInfo`, `PreviewTransition` — Prolific preview pages, not in active sequence
- `InterviewTest` — development/testing page

Corresponding `.html` files exist for all of the above in `templates/` - they should be cleaned up,
lots of things should just be deleted (of course without breaking the core pages).

---

## Node display data

The helper `get_node_display_data(player)` (defined near the top of
`__init__.py`) translates `player.final_nodes` into a list of dicts with
`belief`, `short_label`, `color`, and `radius`. All canvas pages call this
function to get consistent node rendering. Color encodes agreement
(red → gray → green); radius encodes importance (10–22 px). Although currently
just logging radius for analysis and not using it visually. Again, these choices
should be made as easy as possible.
