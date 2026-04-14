"""
Single source of truth for all belief/stance items.

  DYNAMIC_ITEMS — 13 items on a 6-point agreement scale (no midpoint).
                  Used by DynamicBeliefRating (both conditions), LLM stance
                  detection, and canvas display.
                  Values 1–3 = disagree side; 4–6 = agree side.

Each item has:
  id        : short identifier used throughout the codebase
  template  : sentence with [SCALE] as placeholder for the selected label
  labels    : dict mapping 1–6 to the label inserted at [SCALE]
  anchor_lo : left anchor shown below the slider
  anchor_hi : right anchor shown below the slider
  label     : short human-readable label (used in graphs/reporting)
  direction : pro_meat | anti_meat | mixed
  codebook  : LLM coding guidance — what counts as evidence and how to
              calibrate the scale anchors for this specific item
"""

_AGREE_6 = {
    1: "strongly disagree",
    2: "disagree",
    3: "somewhat disagree",
    4: "somewhat agree",
    5: "agree",
    6: "strongly agree",
}

DYNAMIC_ITEMS = [
    # -------------------------------------------------------------------------
    # Enjoyment / Hedonic
    # -------------------------------------------------------------------------
    {
        "id": "taste",
        "template": "I [SCALE] that I love the taste of meat",
        "template_v2": "I [SCALE] that meat tastes great",
        "labels": _AGREE_6,
        "anchor_lo": "Strongly disagree",
        "anchor_hi": "Strongly agree",
        "label": "Taste enjoyment",
        "short_label": "Meat for taste",
        "direction": "pro_meat",
        "codebook": (
            "Evidence: explicit statements about loving, enjoying, or craving "
            "the taste, flavour, or texture of meat (e.g. 'meat is delicious', "
            "'nothing beats a good steak', 'I love how it tastes'). Also count "
            "strong hedonic descriptions of specific meats. Statements about "
            "enjoying eating meat in general (not just taste) count as weak "
            "evidence. Disliking the taste of certain meats is evidence against. "
            "Only omit if taste is never mentioned; a passing or lukewarm mention "
            "should receive a low-to-mid score rather than being skipped. "
            "Scale anchors: "
            "6 = explicitly loves/craves meat's taste; "
            "3-4 = likes the taste but with some ambivalence or qualification; "
            "1 = actively states disliking or being put off by the taste of meat."
        ),
    },

    # -------------------------------------------------------------------------
    # Current behavior
    # -------------------------------------------------------------------------
    {
        "id": "frequency",
        "template": "I [SCALE] that I eat meat on most days",
        "template_v2": "I [SCALE] that I eat meat most days",
        "labels": _AGREE_6,
        "anchor_lo": "Strongly disagree",
        "anchor_hi": "Strongly agree",
        "label": "Eating frequency",
        "short_label": "Meat frequency",
        "direction": "pro_meat",
        "codebook": (
            "Evidence: explicit statements about how often the participant eats "
            "meat, including qualitative frequency words. Base the score on "
            "stated frequency — do not infer from unrelated context. "
            "Qualitative anchors: 'often', 'regularly', 'usually' = 4–5; "
            "'sometimes', 'fairly often' = 3. "
            "Scale anchors: "
            "6 = eats meat daily or at least once every day; "
            "5 = eats meat 5–6 days per week / 'most days'; "
            "4 = eats meat 3–4 days per week; "
            "3 = eats meat a few times a week; "
            "2 = eats meat once or twice a week / occasionally; "
            "1 = rarely or never eats meat. "
            "If no frequency information is present, do not detect this stance."
        ),
    },
    {
        "id": "habit",
        "template": "I [SCALE] that eating meat is something I do out of habit",
        "template_v2": "I [SCALE] that I eat meat out of habit",
        "labels": _AGREE_6,
        "anchor_lo": "Strongly disagree",
        "anchor_hi": "Strongly agree",
        "label": "Habit",
        "short_label": "Meat-eating habit",
        "direction": "pro_meat",
        "codebook": (
            "Evidence: framing meat eating as automatic, routine, or unthinking "
            "rather than an active choice — e.g. 'I've always eaten meat', "
            "'I never really thought about it', 'it's just what I do', "
            "'I eat meat without thinking'. 'Grew up eating meat' counts as "
            "moderate evidence (overlaps with culture item). Distinguish from "
            "culture: habit is about personal automaticity; culture is about "
            "societal or family norms. "
            "Only omit if there is no indication whatsoever of routine or "
            "unthinking eating; a vague suggestion of routine counts as low evidence. "
            "Scale anchors: "
            "6 = explicitly describes meat eating as habitual or automatic; "
            "3-4 = suggests routine eating without explicitly calling it a habit; "
            "1 = explicitly states they think carefully about eating meat or that it is a deliberate choice."
        ),
    },

    # -------------------------------------------------------------------------
    # Social / Cultural / Normative
    # -------------------------------------------------------------------------
    {
        "id": "culture",
        "template": "I [SCALE] that eating meat is a normal part of our culture",
        "template_v2": "I [SCALE] that meat-eating is part of our culture",
        "labels": _AGREE_6,
        "anchor_lo": "Strongly disagree",
        "anchor_hi": "Strongly agree",
        "label": "Cultural norm",
        "short_label": "Meat culture",
        "direction": "pro_meat",
        "codebook": (
            "Evidence: belief that meat eating is culturally normal, traditional, "
            "or expected at a societal or community level — e.g. 'it's just what "
            "people do', 'meat is part of every meal in my culture', 'I was "
            "raised in a culture where meat is central', 'it's a tradition'. "
            "Also count: holiday or celebratory meat traditions, religious or "
            "ethnic food traditions involving meat. "
            "Do NOT use for statements purely about the participant's immediate "
            "social circle (family/friends) — that is the social_norm item. "
            "Only omit if culture and tradition around food are never mentioned. "
            "Scale anchors: "
            "6 = strongly affirms meat as a cultural tradition or norm; "
            "3-4 = acknowledges cultural aspect but with some ambivalence; "
            "1 = explicitly challenges or rejects the idea that meat is a cultural norm."
        ),
    },
    {
        "id": "social_norm",
        "template": "I [SCALE] that most people close to me eat meat",
        "template_v2": "I [SCALE] that most people close to me eat meat",
        "labels": _AGREE_6,
        "anchor_lo": "Strongly disagree",
        "anchor_hi": "Strongly agree",
        "label": "Personal social norm",
        "short_label": "Most people eat meat",
        "direction": "pro_meat",
        "codebook": (
            "Evidence: statements about the participant's immediate social circle "
            "— family, friends, partner, housemates — eating meat regularly. "
            "E.g. 'my family eats meat every day', 'all my friends eat meat', "
            "'my partner is a big meat eater'. "
            "Do NOT use for broad cultural statements (that is the culture item). "
            "Focus on named or described personal relationships. "
            "Only omit if the social circle is never mentioned. "
            "Scale anchors: "
            "6 = explicitly states everyone or almost everyone close to them eats meat; "
            "3-4 = mixed social circle, some eat meat some do not; "
            "1 = explicitly states that most people close to them avoid or do not eat meat."
        ),
    },

    # -------------------------------------------------------------------------
    # Health beliefs — pro-meat
    # -------------------------------------------------------------------------
    {
        "id": "protein",
        "template": "I [SCALE] that meat is an important source of protein for me",
        "template_v2": "I [SCALE] that meat is a great source of protein",
        "labels": _AGREE_6,
        "anchor_lo": "Strongly disagree",
        "anchor_hi": "Strongly agree",
        "label": "Protein belief",
        "short_label": "Meat for protein",
        "direction": "pro_meat",
        "codebook": (
            "Evidence: belief that meat is a key or significant source of "
            "dietary protein, iron, amino acids, or nutrients. E.g. 'I eat "
            "meat for the protein', 'meat gives me the nutrients I need', "
            "'I need meat for iron'. Does NOT need to say 'necessary' — "
            "importance is sufficient. Count even if the participant also "
            "mentions other protein sources. "
            "Only omit if nutrition and protein are never mentioned in any form. "
            "Scale anchors: "
            "6 = strongly and explicitly believes meat is their primary or "
            "essential protein/nutrient source; "
            "3-4 = mentions protein as one of several reasons to eat meat; "
            "1-2 = vague mention of nutrition or actively states they get protein from non-meat sources."
        ),
    },
    {
        "id": "fitness",
        "template": "I [SCALE] that eating meat is important for my fitness and physical health",
        "template_v2": "I [SCALE] that meat is important for fitness",
        "labels": _AGREE_6,
        "anchor_lo": "Strongly disagree",
        "anchor_hi": "Strongly agree",
        "label": "Fitness and health belief",
        "short_label": "Meat for fitness",
        "direction": "pro_meat",
        "codebook": (
            "Evidence: belief that meat supports physical fitness, muscle "
            "building, energy levels, weight management, athletic performance, "
            "or overall physical health — beyond just protein. E.g. 'meat gives "
            "me energy', 'I eat meat to build muscle', 'my low-carb diet relies "
            "on meat', 'I need meat to stay strong'. "
            "Distinguish from protein: this is about broader fitness/body goals. "
            "Only omit if health and physical wellbeing in relation to diet are never mentioned. "
            "Scale anchors: "
            "6 = explicitly and strongly links meat to fitness or physical health goals; "
            "3-4 = vague health motivation without a clear fitness link; "
            "1 = explicitly states meat is bad for their health or undermines fitness."
        ),
    },

    # -------------------------------------------------------------------------
    # Health concern — anti-meat
    # -------------------------------------------------------------------------
    {
        "id": "health_concern",
        "template": "I [SCALE] that the health effects of eating too much meat concern me",
        "template_v2": "I [SCALE] that too much meat is bad for your health",
        "labels": _AGREE_6,
        "anchor_lo": "Strongly disagree",
        "anchor_hi": "Strongly agree",
        "label": "Health concern",
        "short_label": "Meat health concern",
        "direction": "anti_meat",
        "codebook": (
            "Evidence: worry or concern about negative health consequences of "
            "eating meat — cholesterol, saturated fat, cancer risk, diabetes, "
            "heart disease, processed meat risks, digestive issues, weight "
            "concerns linked to meat intake. Also count: doctor advice to reduce "
            "meat, family history of diet-related illness, general healthy-eating "
            "motivation where reducing meat is part of the goal. "
            "Score based on strength of concern, not on whether the participant "
            "has actually reduced consumption. "
            "Only omit if health in relation to meat is never mentioned. "
            "Scale anchors: "
            "6 = strong and explicit health concern, mentions specific conditions or medical advice; "
            "3-4 = general or vague health worry about meat; "
            "1 = actively states that meat is healthy and poses no health concern."
        ),
    },

    # -------------------------------------------------------------------------
    # Behavioral intention — toward change
    # -------------------------------------------------------------------------
    {
        "id": "reduce_meat",
        "template": "I [SCALE] that I want to reduce how much meat I eat",
        "template_v2": "I [SCALE] that I want to reduce how much meat I eat",
        "labels": _AGREE_6,
        "anchor_lo": "Strongly disagree",
        "anchor_hi": "Strongly agree",
        "label": "Meat reduction intention",
        "short_label": "Meat reduction",
        "direction": "anti_meat",
        "codebook": (
            "Evidence: desire, intention, or active effort to eat less meat — "
            "regardless of whether the participant is succeeding. E.g. 'I would "
            "like to eat less meat', 'I have been trying to cut back', 'I wish "
            "I ate less meat', 'I am considering reducing'. Past reduction "
            "efforts count as evidence of ongoing intention. "
            "Score based on strength of intention, not success. "
            "Only omit if reducing meat is never mentioned in any form. "
            "Scale anchors: "
            "6 = strong explicit desire or active sustained effort to reduce meat consumption; "
            "3-4 = mild consideration or passing wish to eat less; "
            "1-2 = mentions the idea but dismisses it, or actively wants to eat more meat."
        ),
    },
    {
        "id": "plant_based",
        "template": "I [SCALE] that I want to eat more plant-based foods",
        "template_v2": "I [SCALE] that I want to eat more plant-based foods",
        "labels": _AGREE_6,
        "anchor_lo": "Strongly disagree",
        "anchor_hi": "Strongly agree",
        "label": "Plant-based intention",
        "short_label": "More plant-based",
        "direction": "anti_meat",
        "codebook": (
            "Evidence: desire or intention to eat more plant-based foods — "
            "vegetables, legumes, tofu, meat alternatives, vegetarian/vegan "
            "meals. E.g. 'I want to eat more vegetables', 'I have been trying "
            "plant-based options', 'I am open to a vegan diet'. "
            "Count even if the participant is currently struggling with it. "
            "Do NOT count statements about disliking plant-based food — those are evidence against. "
            "Only omit if plant-based foods are never mentioned. "
            "Scale anchors: "
            "6 = actively pursuing or strongly desires a plant-based shift; "
            "3-4 = open to plant-based foods but not committed; "
            "1 = explicitly rejects plant-based eating or has no interest."
        ),
    },
    {
        "id": "avoidance",
        "template": "I [SCALE] that I avoid or limit certain types of meat",
        "template_v2": "I [SCALE] that I avoid or limit some types of meat",
        "labels": _AGREE_6,
        "anchor_lo": "Strongly disagree",
        "anchor_hi": "Strongly agree",
        "label": "Selective meat avoidance",
        "short_label": "Avoid meat types",
        "direction": "mixed",
        "codebook": (
            "Evidence: selective avoidance or deliberate limitation of specific "
            "meat types while still eating meat overall — red meat, processed "
            "meat, pork, beef, etc. E.g. 'I don't eat red meat', 'I avoid pork', "
            "'I have cut back on beef', 'I only eat chicken and fish now'. "
            "Reasons may vary: health, religious, taste, ethics — all count. "
            "Distinguish from reduce_meat: this is selective avoidance of "
            "certain types, not a general reduction of all meat. "
            "Only omit if specific meat preferences or restrictions are never mentioned. "
            "Scale anchors: "
            "6 = explicitly avoids or significantly limits a specific meat type as a consistent pattern; "
            "3-4 = occasional or mild avoidance of certain meats; "
            "1 = explicitly states they eat all meat types without any restriction."
        ),
    },

    # -------------------------------------------------------------------------
    # Ethical / Environmental
    # -------------------------------------------------------------------------
    {
        "id": "animal_welfare",
        "template": "I [SCALE] that animal welfare is a concern in meat production",
        "template_v2": "I [SCALE] that animals suffer in meat production",
        "labels": _AGREE_6,
        "anchor_lo": "Strongly disagree",
        "anchor_hi": "Strongly agree",
        "label": "Animal welfare concern",
        "short_label": "Animal welfare concern",
        "direction": "anti_meat",
        "codebook": (
            "Evidence: any mention of how animals are treated in meat production, "
            "including: factory farming, animal suffering, humane slaughter, living "
            "conditions, ethical sourcing (grass-fed, free-range), moral conflict "
            "about eating animals, documentary-inspired concern. "
            "Also detect when the participant mentions animals in passing or says "
            "they do not think much about it — score low (1-2) rather than omitting. "
            "Only omit entirely if animals and meat production are never mentioned. "
            "Scale anchors: "
            "6 = strong explicit concern, mentions specific welfare issues or expresses moral conflict; "
            "3-4 = passing or vague mention of animal welfare; "
            "1-2 = mentions animals but dismisses concern ('circle of life', 'I don't think about it')."
        ),
    },
    {
        "id": "environment",
        "template": "I [SCALE] that the environmental impact of meat production concerns me",
        "template_v2": "I [SCALE] that meat production harms the environment",
        "labels": _AGREE_6,
        "anchor_lo": "Strongly disagree",
        "anchor_hi": "Strongly agree",
        "label": "Environmental concern",
        "short_label": "Environment concern",
        "direction": "anti_meat",
        "codebook": (
            "Evidence: concern about environmental, ecological, or climate "
            "consequences of meat production. E.g. 'meat has a large carbon "
            "footprint', 'I worry about the climate impact', 'meat production "
            "uses too much water/land', 'deforestation for cattle'. "
            "Match climate-specific statements even if 'environment' is not used. "
            "Only omit if environment, climate, and sustainability are never mentioned. "
            "Scale anchors: "
            "6 = strong explicit environmental or climate concern linked to meat production; "
            "3-4 = general vague environmental awareness without specific connection to meat; "
            "1 = explicitly states meat production is not an environmental concern."
        ),
    },
]
