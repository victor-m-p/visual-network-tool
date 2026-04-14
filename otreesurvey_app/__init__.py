from otree.api import *
import json, time, asyncio, re
import random
from .llm_prompts import *
from datetime import datetime
from otree.api import Page

# for local, on HEROKU needs to be set. 
from openai import AsyncOpenAI # OpenAI
from dotenv import load_dotenv
load_dotenv()
ASYNC_CLIENT = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# for the training
from dataclasses import dataclass
from typing import Dict, List, Tuple

doc = """
Your app description
"""

US_STATES = [
    'Not Applicable', 'Alaska', 'Alabama', 'Arkansas', 'Arizona',
    'California', 'Colorado', 'Connecticut', 'District of Columbia',
    'Delaware', 'Florida', 'Georgia', 'Hawaii',
    'Iowa', 'Idaho', 'Illinois', 'Indiana',
    'Kansas', 'Kentucky', 'Louisiana', 'Massachusetts',
    'Maryland', 'Maine', 'Michigan', 'Minnesota',
    'Missouri', 'Mississippi', 'Montana', 'North Carolina',
    'North Dakota', 'Nebraska', 'New Hampshire', 'New Jersey',
    'New Mexico', 'Nevada', 'New York', 'Ohio',
    'Oklahoma', 'Oregon', 'Pennsylvania', 'Rhode Island',
    'South Carolina', 'South Dakota', 'Tennessee', 'Texas',
    'Utah', 'Virginia', 'Vermont', 'Washington',
    'Wisconsin', 'West Virginia', 'Wyoming']

DISTRACTORS = [
    "My friends often go out to eat seahorse",
]

# =============================================================================
# NODE VISUAL ENCODING
# Shared by MapNodePlacement, MapEdgePos, MapEdgeNeg (and any future variants).
# rating    = agreement  1–7  → node color (diverging red→grey→blue)
# relevance = importance 1–7  → node radius (10–22 px)
# =============================================================================
_AGREEMENT_COLORS = {
    1: '#d73027',  # red   (disagree — values 1–3)
    2: '#d73027',
    3: '#d73027',
    4: '#006d2c',  # green (agree    — values 4–6)
    5: '#006d2c',
    6: '#006d2c',
}

def _node_radius(importance):
    v = max(1, min(7, importance or 4))
    return 10 + (v - 1) * 2           # 1→10 px, 2→12, 3→14, 4→16, 5→18, 6→20, 7→22 px

def _node_color(agreement):
    v = max(1, min(6, agreement or 4))
    return _AGREEMENT_COLORS[v]

def get_node_display_data(player):
    """Return [{belief, short_label, radius, color}, ...] for every node in final_nodes."""
    nodes = json.loads(player.final_nodes or '[]')
    return [
        {
            "belief":      n.get("dynamic_sentence_simple") or n.get("belief", ""),
            "short_label": n.get("short_label", ""),
            "radius":      14,  # fixed size
            "color":       _node_color(n.get("rating")),
        }
        for n in nodes
    ]


def stamp(player, label: str):
    """Append {'label': <string>, 'ts': <float>} to player's JSON log."""
    # 1) Load existing JSON (or empty list)
    try:
        arr = json.loads(player.page_timings_json or '[]')
        if not isinstance(arr, list):
            arr = []
    except Exception:
        arr = []
    # 2) Append a record; make sure 'label' is a string
    arr.append({'label': str(label), 'ts': time.time()})
    # 3) Save it back as JSON
    player.page_timings_json = json.dumps(arr)

# temporary for testing # 
from .interview_001 import RECORDED_QA
def preload_interview(player, qa_pairs):
    dummy_time = datetime.utcnow().isoformat()
    conversation = []

    # If qa_pairs is a dict, use .items(); if it's already a list of tuples, use it directly.
    iterator = qa_pairs.items() if isinstance(qa_pairs, dict) else qa_pairs

    for q, a in iterator:
        conversation.append({
            "question": q,
            "answer": a,
            "input_mode": "text",
            "time_sent": dummy_time,
            "time_received": dummy_time,
        })

    player.conversation_json = json.dumps(conversation)
    player.participant.vars["interview_turns"] = len(conversation)

# for trainining
@dataclass
class TrainingScenario:
    key: str
    name: str
    vignette_html: str
    train_stance_list: List[str]
    stance_id_to_text: Dict[int, str]
    allowed_relations: Dict[Tuple[int, int], List[str]]
    required_positive_pairs: List[Tuple[int, int]]
    required_negative_pairs: List[Tuple[int, int]]

class C(BaseConstants): 
    NAME_IN_URL = 'survey'
    PLAYERS_PER_GROUP = None 
    NUM_ROUNDS = 1 # is this a special variable or can I delete it?  
    MAX_TURNS = 8 # for the adaptive interview
    MAX_BELIEF_ITEMS = 30  # safely above max limimt.
    MEAT_FREQ_CATEGORIES = [
        "never",
        "less than once a week",
        "one or two days a week",
        "three or four days a week",
        "five or six days a week",
        "every day"
    ]
    NUM_NODES_THRESHOLD=3 
    NUM_NODES_MAX=10 

    # for pairwise questions
    TARGET_PER_BUCKET = 3  # we aim for up to 3 per polarity bucket
    N_PAIR_QUESTIONS = 3 * TARGET_PER_BUCKET  # upper bound, e.g. 9

    # --- Alex (your real example) ---
    TRAIN_TEXT_1 = (
        "Alex decided to learn Spanish to improve job prospects and to be able to "
        "speak with locals while traveling. To practice speaking, Alex occasionally "
        "attends a conversational meetup. Some of Alex’s colleagues are also learning "
        "Spanish and attending the meetup, and this motivates Alex to go as well. "
        "However, Alex feels very embarrassed speaking out loud, and this sometimes "
        "makes Alex avoid the meetup. To remain consistent, Alex tries to practice "
        "Spanish every day using a language-learning app. Alex has a busy job, and "
        "when it gets hectic Alex skips the daily practice."
    )

    STANCE_LIST_1 = [
        "Alex sees career benefits from learning Spanish",
        "Alex wants to speak with locals",
        "Alex practices daily with an app",
        "Alex has a busy job",
        "Alex attends a conversational meetup",
        "Colleagues are learning Spanish",
        "Alex feels embarrassed speaking out loud",
    ]

    STANCE_ID_TO_TEXT_1 = {
        1: STANCE_LIST_1[0],
        2: STANCE_LIST_1[1],
        3: STANCE_LIST_1[2],
        4: STANCE_LIST_1[3],
        5: STANCE_LIST_1[4],
        6: STANCE_LIST_1[5],
        7: STANCE_LIST_1[6],
    }

    RELATIONS_1 = {
        # 1 with others (career benefits)
        (1, 2): ["positive", "none"],                  # career benefits & locals: usually support
        (1, 3): ["positive", "none"],                  # app practice supports career benefits
        (1, 4): ["positive", "negative", "none"],      # busy job can increase importance or hinder progress, or be unrelated
        (1, 5): ["positive", "none"],                  # meetup helps learning → career benefits
        (1, 6): ["positive", "none"],                  # colleagues learning signals career value / motivation
        (1, 7): ["positive", "negative", "none"],      # embarrassment can motivate or hinder effort, or be unrelated

        # 2 with others (speak with locals)
        (2, 3): ["positive", "none"],                  # practice supports speaking with locals
        (2, 4): ["negative", "none"],                  # busy job undermines time/energy to speak
        (2, 5): ["positive"],                          # REQUIRED POS: meetup is direct speaking practice
        (2, 6): ["positive", "none"],                  # colleagues may motivate engagement
        (2, 7): ["negative", "none"],                  # embarrassment makes speaking harder

        # 3 with others (daily app practice)
        (3, 4): ["negative"],                          # REQUIRED NEG: busy job makes Alex skip practice
        (3, 5): ["positive", "none"],                  # meetup & app both help learning
        (3, 6): ["positive", "none"],                  # colleagues motivate practice
        (3, 7): ["positive", "negative", "none"],      # embarrassment can either push to practice more or avoid it

        # 4 with others (busy job)
        (4, 5): ["negative", "none"],                  # busy job makes it harder to attend meetup
        (4, 6): ["none"],                              # no systematic link in vignette
        (4, 7): ["none"],                              # no systematic link in vignette

        # 5 with others (meetup)
        (5, 6): ["positive"],                          # REQUIRED POS: colleagues at meetup motivate attendance
        (5, 7): ["negative"],                          # REQUIRED NEG: embarrassment leads to avoiding meetup

        # 6 with 7 (colleagues & embarrassment)
        (6, 7): ["positive", "negative", "none"],      # colleagues can reduce or increase embarrassment, or be neutral
    }

    REQUIRED_POS_1 = [(2, 5), (5, 6)]
    REQUIRED_NEG_1 = [(3, 4), (5, 7)]

    # --- Dummy 1 (Sam, simple) ---

    TRAIN_TEXT_2 = (
    "Jordan wants to improve their physical fitness and to have more energy during the day. "
    "A friend has invited Jordan to join their gym sessions, and the gym is located on "
    "Jordan’s way home from work, which makes it convenient to go. Jordan plans to go to "
    "the gym three times a week. However, Jordan often feels exhausted after work and "
    "feels self-conscious exercising in front of others, and these feelings sometimes "
    "lead Jordan to skip the gym."
    )
    
    STANCE_LIST_2 = [
    "Jordan wants to improve their physical fitness",          # 1
    "Jordan wants to have more energy during the day",         # 2
    "Jordan plans to go to the gym three times a week",        # 3
    "Jordan often feels exhausted after work",                 # 4
    "A friend has invited Jordan to join their gym sessions",  # 5
    "The gym is located on Jordan’s way home from work",       # 6
    "Jordan feels self-conscious exercising in front of others",  # 7
    ]

    STANCE_ID_TO_TEXT_2 = {
        1: STANCE_LIST_2[0],
        2: STANCE_LIST_2[1],
        3: STANCE_LIST_2[2],
        4: STANCE_LIST_2[3],
        5: STANCE_LIST_2[4],
        6: STANCE_LIST_2[5],
        7: STANCE_LIST_2[6],
    }


    REQUIRED_POS_2 = [
        (1, 3), # wanting better fitness + plan to go to gym
        (3, 5), # friend invitation + plan to go to gym
    ]

    REQUIRED_NEG_2 = [
        (3, 4), # gym plan + exhaustion after work
        (3, 7), # gym plan + self-consciousness 
    ]
    
    RELATIONS_2 = {
    # 1. Fitness goal with others
    (1, 2): ["positive", "none"],              # improving fitness and having more energy fit together
    (1, 3): ["positive"],                      # REQUIRED POS: plan clearly supports fitness
    (1, 4): ["negative", "none"],             # exhaustion makes fitness goal harder
    (1, 5): ["positive", "none"],             # friend invite helps with fitness goal
    (1, 6): ["positive", "none"],             # convenient gym helps with fitness goal
    (1, 7): ["negative", "none"],             # self-consciousness can undermine pursuing fitness

    # 2. Energy goal with others
    (2, 3): ["positive", "none"],             # plan to exercise supports energy goal
    (2, 4): ["negative", "none"],             # exhaustion conflicts with wanting more energy
    (2, 5): ["positive", "none"],             # friend invite supports exercising, so energy
    (2, 6): ["positive", "none"],             # convenient gym supports exercising, so energy
    (2, 7): ["negative", "none"],             # self-consciousness makes it harder to exercise, so less energy

    # 3. Gym plan with others
    (3, 4): ["negative"],                     # REQUIRED NEG: exhaustion makes it hard to follow the plan
    (3, 5): ["positive"],                     # REQUIRED POS: friend invite directly supports going
    (3, 6): ["positive", "none"],             # gym on the way home supports the plan
    (3, 7): ["negative"],                     # REQUIRED NEG: self-consciousness leads to skipping the gym

    # 4. Exhaustion with others
    (4, 5): ["positive", "negative", "none"], # friend might help (encouragement) or conflict (still too tired), or no clear link
    (4, 6): ["none"],                         # exhaustion & gym location: no necessary systematic relation here
    (4, 7): ["positive", "none"],             # feeling exhausted can increase self-consciousness about exercising

    # 5. Friend invitation with others
    (5, 6): ["positive", "none"],             # invitation + convenient location both make going easier
    (5, 7): ["positive", "negative", "none"], # friend may reduce self-consciousness (supportive) or increase it (comparison), or no clear effect

    # 6. Gym location with self-consciousness
    (6, 7): ["none"],                         # location itself doesn’t systematically change self-consciousness
    }

    # --- Dummy 2 (really simple) ---

    TRAIN_TEXT_3 = (
    "Riley wants to get more involved in the local community and registered for a weekly "
    "volunteer shift. A close friend also volunteers there, which makes Riley feel welcome. "
    "The community center is located close to Riley’s home, so getting there is usually easy. "
    "However, Riley sometimes needs to take care of a younger relative on short notice, which "
    "makes it difficult to attend the volunteer shift consistently. Riley tries to plan ahead "
    "each week, using reminders and a shared calendar, but unexpected caregiving needs sometimes "
    "interfere."
    )

    STANCE_LIST_3 = [
        "Riley wants to contribute to the local community",                # 1
        "Riley registered for a weekly volunteer shift",                   # 2
        "A close friend also volunteers there",                            # 3
        "The community center is close to Riley’s home",                   # 4
        "Riley sometimes needs to take care of a younger relative on short notice",  # 5
        "Riley tries to plan ahead using reminders and a shared calendar", # 6
        "Unexpected caregiving needs sometimes interfere with Riley’s plans",        # 7
    ]

    STANCE_ID_TO_TEXT_3 = {
        1: STANCE_LIST_3[0],
        2: STANCE_LIST_3[1],
        3: STANCE_LIST_3[2],
        4: STANCE_LIST_3[3],
        5: STANCE_LIST_3[4],
        6: STANCE_LIST_3[5],
        7: STANCE_LIST_3[6],
    }

    REQUIRED_POS_3 = [
        (2, 3),  # friend also volunteers + registered shift
        (2, 4),  # center is close + registered shift
    ]

    REQUIRED_NEG_3 = [
        (2, 5),  # caregiving on short notice + registered shift
        (2, 7),  # unexpected caregiving interference + registered shift
    ]

    RELATIONS_3 = {
        # 1. Community contribution goal
        (1, 2): ["positive", "none"],      # volunteering supports contributing
        (1, 3): ["positive", "none"],      # friend encouragement supports goal
        (1, 4): ["positive", "none"],      # easy location supports goal
        (1, 5): ["negative", "none"],      # caregiving makes contributing harder
        (1, 6): ["positive", "none"],      # planning supports contributing
        (1, 7): ["negative", "none"],      # unexpected conflicts undermine goal

        # 2. Registered volunteer shift (central action)
        (2, 3): ["positive"],              # REQUIRED POS: friend boosts attendance
        (2, 4): ["positive"],              # REQUIRED POS: location makes attending easy
        (2, 5): ["negative"],              # REQUIRED NEG: caregiving prevents attendance
        (2, 6): ["positive", "none"],      # planning helps maintain commitment
        (2, 7): ["negative"],              # REQUIRED NEG: disruptions conflict with shift

        # 3. Friend also volunteers
        (3, 4): ["positive", "none"],      # social + convenience both help attendance
        (3, 5): ["none"],                  # caregiving unrelated to friend
        (3, 6): ["positive", "none"],      # planning + social support both help
        (3, 7): ["none"],                  # disruptions unrelated to friend

        # 4. Location is close by
        (4, 5): ["none"],                  # caregiving unrelated to location
        (4, 6): ["positive", "none"],      # planning supports making use of location
        (4, 7): ["none"],                  # disruptions unrelated to distance

        # 5. Caregiving on short notice
        (5, 6): ["negative", "none"],      # planning may help but often cannot fix it
        (5, 7): ["positive"],              # caregiving increases unexpected disruptions

        # 6. Planning with reminders
        (6, 7): ["negative", "none"],      # planning reduces unexpected conflicts, though imperfect
    }

    TRAINING_SCENARIOS: dict[str, TrainingScenario] = {
        "example1": TrainingScenario(
            key="example1",
            name="Alex",
            vignette_html=TRAIN_TEXT_1,
            train_stance_list=STANCE_LIST_1,
            stance_id_to_text=STANCE_ID_TO_TEXT_1,
            allowed_relations=RELATIONS_1,
            required_positive_pairs=REQUIRED_POS_1,
            required_negative_pairs=REQUIRED_NEG_1,
        ),
        "example2": TrainingScenario(
            key="example2",
            name="Jordan",
            vignette_html=TRAIN_TEXT_2,
            train_stance_list=STANCE_LIST_2,
            stance_id_to_text=STANCE_ID_TO_TEXT_2,
            allowed_relations=RELATIONS_2,
            required_positive_pairs=REQUIRED_POS_2,
            required_negative_pairs=REQUIRED_NEG_2,
        ),
        "example3": TrainingScenario(
            key="example3",
            name="Riley",
            vignette_html=TRAIN_TEXT_3,
            train_stance_list=STANCE_LIST_3,
            stance_id_to_text=STANCE_ID_TO_TEXT_3,
            allowed_relations=RELATIONS_3,
            required_positive_pairs=REQUIRED_POS_3,
            required_negative_pairs=REQUIRED_NEG_3,
        ),
    }
    
    # VEMI questionnaire
    VEMI_ITEMS = [
        ("I want to be healthy", "H"),
        ("Plant-based diets are better for the environment", "E"),
        ("Animals do not have to suffer", "A"),
        ("Animals’ rights are respected", "A"),
        ("I want to live a long time", "H"),
        ("Plant-based diets are more sustainable", "E"),
        ("I care about my body", "H"),
        ("Eating meat is bad for the planet", "E"),
        ("Animal rights are important to me", "A"),
        ("Plant-based diets are environmentally-friendly", "E"),
        ("It does not seem right to exploit animals", "A"),
        ("Plants have less of an impact on the environment than animal products", "E"),
        ("I am concerned about animal rights", "A"),
        ("My health is important to me", "H"),
        ("I don’t want animals to suffer", "A"),
    ]
    
    # MEMI questionnaire
    MEMI_ITEMS = [
    ("It goes against nature to eat only plants.", "Natural"),
    ("Our bodies need the protein.", "Necessary"),
    ("I want to fit in.", "Normal"),
    ("It is delicious.", "Nice"),
    ("It makes people strong and vigorous.", "Necessary"),
    ("I don’t want other people to be uncomfortable.", "Normal"),
    ("It is in all of the best tasting food.", "Nice"),
    ("It could be unnatural not to eat meat.", "Natural"),
    ("It is necessary for good health.", "Necessary"),
    ("It is just one of the things people do.", "Normal"),
    ("It gives me pleasure.", "Nice"),
    ("I want to be sure I get all of the vitamins and minerals I need.", "Necessary"),
    ("Everybody does it.", "Normal"),
    ("It has good flavor.", "Nice"),
    ("It gives me strength and endurance.", "Necessary"),
    ("I don’t want to stand out.", "Normal"),
    ("Meals without it don’t taste good.", "Nice"),
    ("It is human nature to eat meat.", "Natural"),
    ("Eating meat is part of our biology.", "Natural"),
]

class Subsession(BaseSubsession):
    pass


def creating_session(subsession: Subsession):
    for player in subsession.get_players():
        player.condition = 'color_tag'

class Group(BaseGroup):
    pass

class Player(BasePlayer):
    
    # Consent.html (used)
    consent_given = models.BooleanField(
        choices=[[True, 'I consent'], [False, 'I do not consent']],
        widget=widgets.RadioSelect,
        label=''
    ) 
    
    # MeatScale.html (used)
    meat_consumption_present = models.IntegerField(min=1, max=100)
    meat_consumption_past    = models.IntegerField(min=1, max=100)
    meat_consumption_future  = models.IntegerField(min=1, max=100)
    dissonance_personal = models.IntegerField(min=1, max=100)
    dissonance_social = models.IntegerField(min=1, max=100)

    # Intervention
    intervention_label              = models.StringField(blank=True)
    intervention_convincing         = models.IntegerField(min=1, max=7, blank=True)
    intervention_surprising         = models.IntegerField(min=1, max=7, blank=True)
    intervention_understandable     = models.IntegerField(min=1, max=7, blank=True)
    intervention_emotional          = models.IntegerField(min=1, max=7, blank=True)
    # Shuffled display order, e.g. [1, 0] — set in PreviewTransition.before_next_page
    direct_belief_comment           = models.LongStringField(blank=True)
    intervention_order_json         = models.LongStringField(blank=True)
    # Optional open comment per intervention (overwritten each page; saved to JSON)
    intervention_comment            = models.LongStringField(blank=True)
    # Accumulated ratings for all intervention texts: [{index, label, convincing, surprising, understandable, emotional, comment}, ...]
    intervention_ratings_json       = models.LongStringField(blank=True)

    # LLM nodes generation (used)
    prompt_used = models.LongStringField(blank=True) # "node_prompt"
    llm_result = models.LongStringField(blank=True) # "node_result"

    # LLM nodes (BeliefAccuracyRating.html)
    generated_nodes = models.LongStringField(blank=True) # used 
    generated_nodes_accuracy = models.LongStringField(blank=True) # used 
    generated_nodes_relevance = models.LongStringField(blank=True) # used 

    # process/filter nodes 
    final_nodes = models.LongStringField(blank=True) # used 
    num_nodes = models.IntegerField(initial=0) # used only during

    # for distractors (used)
    distractor_problem = models.BooleanField(initial=False)
    distractor_ratings = models.LongStringField(blank=True)

    # main task (used)
    positions_1 = models.LongStringField(blank=True) 
    positions_2 = models.LongStringField(blank=True)
    positions_3 = models.LongStringField(blank=True)

    edges_2 = models.LongStringField(blank=True)
    edges_3 = models.LongStringField(blank=True)

    # MapProximity (experimental auto-edge page)
    positions_auto = models.LongStringField(blank=True)
    edges_auto     = models.LongStringField(blank=True)
   
    # demographics (used)
    age = models.IntegerField(label='How old are you?', min=18, max=130) 
    gender = models.StringField(
        label='What is your gender?',
        choices=[
            "Female", 
            "Male", 
            "Non-binary", 
            "Prefer not to disclose", 
            "Other"],
        widget=widgets.RadioSelect
        ) 
    education = models.StringField(
        label='What is the highest level of school you have completed or the highest degree you have received?',
        choices=[
            "Less than high school degree", 
            "High school degree or equivalent (e.g., GED)",
            "Some college but no degree", 
            "Associate degree", 
            "Bachelor degree",
            "Graduate degree (e.g., Masters, PhD, M.D)"
            ],
        widget=widgets.RadioSelect
    ) 
    politics = models.StringField(
        label='How would you describe your political viewpoints?',
        choices=[
            "Very liberal",
            "Slightly liberal",
            "Moderate",
            "Slightly conservative",
            "Very conservative",
            "Prefer not to disclose"
            ],
        widget=widgets.RadioSelect
    ) 
    state = models.StringField(
        label="In which state do you currently live?",
        choices=US_STATES
    ) 
    zipcode = models.StringField(
        label="Please enter your 5-digit ZIP code:",
        min_length=5,
        max_length=5,
    ) 
    
    # This does not do anything now I believe.
    force_answer = models.BooleanField(initial=True)
    
    # Logging conversation (clean this up as well.) 
    conversation_json = models.LongStringField(initial="[]") # used 
    current_answer = models.LongStringField(blank=True) # not used in post-experiment
    voice_answer = models.LongStringField(blank=True) # not used in post-experiment
    interview_feedback = models.LongStringField(
        label="",
        blank=True
    ) # used in post-experiment
    interview_test = models.LongStringField(
        label="",
        blank=True
    ) # does not work 
    
    # page timings (used)
    page_timings_json = models.LongStringField(initial='[]')

    # test audio
    audio_data = models.LongStringField(blank=True) # allows blank
    
    # final feedback (used)
    final_feedback = models.LongStringField(label='', blank=True)
    
    # VEMI.html + MEMI.html
    vemi_responses = models.LongStringField(blank=True)
    memi_responses = models.LongStringField(blank=True)
    
    # edge prompts 
    llm_edge_prompt = models.LongStringField(blank=True) # used
    llm_edges = models.LongStringField(blank=True) # used 
    # Let's just try this: 
    conv_overall_0_100 = models.IntegerField(min=0, max=100)
    conv_overall_cat = models.IntegerField(
        choices=[
            (1, 'Terrible'),
            (2, 'Not good'),
            (3, 'Average / Neutral'),
            (4, 'Good'),
            (5, 'Excellent'),
        ]
    )

    # 2. Questions relevant
    conv_relevant_0_100 = models.IntegerField(min=0, max=100)
    conv_relevant_cat = models.IntegerField(
        choices=[
            (1, 'Strongly disagree'),
            (2, 'Somewhat disagree'),
            (3, 'Neither agree nor disagree'),
            (4, 'Somewhat agree'),
            (5, 'Strongly agree'),
        ]
    )

    # 3. Easy to express in chat
    conv_easy_chat_0_100 = models.IntegerField(min=0, max=100)
    conv_easy_chat_cat = models.IntegerField(
        choices=[
            (1, 'Strongly disagree'),
            (2, 'Somewhat disagree'),
            (3, 'Neither agree nor disagree'),
            (4, 'Somewhat agree'),
            (5, 'Strongly agree'),
        ]
    )

    # 4. Comfortable to be honest
    conv_comfort_0_100 = models.IntegerField(min=0, max=100)
    conv_comfort_cat = models.IntegerField(
        choices=[
            (1, 'Strongly disagree'),
            (2, 'Somewhat disagree'),
            (3, 'Neither agree nor disagree'),
            (4, 'Somewhat agree'),
            (5, 'Strongly agree'),
        ]
    )

    # 5. AI model felt creepy/intrusive
    conv_creepy_0_100 = models.IntegerField(min=0, max=100)
    conv_creepy_cat = models.IntegerField(
        choices=[
            (1, 'Strongly disagree'),
            (2, 'Somewhat disagree'),
            (3, 'Neither agree nor disagree'),
            (4, 'Somewhat agree'),
            (5, 'Strongly agree'),
        ]
    )

    # Optional open comment
    conv_open_feedback = models.LongStringField(blank=True)
    
    # Training main data
    training_order_json      = models.LongStringField(blank=True)
    training_nodes           = models.LongStringField(blank=True)
    training_positions_1     = models.LongStringField(blank=True)
    training_positions_2     = models.LongStringField(blank=True)
    training_positions_3     = models.LongStringField(blank=True)
    training_edges_2         = models.LongStringField(blank=True)  # positive only (last example)
    training_edges_3         = models.LongStringField(blank=True)  # pos+neg merged (last example)

    training_pos_retry_count = models.IntegerField(initial=0)
    training_neg_retry_count = models.IntegerField(initial=0)

    # Attempt logs (all examples)
    training_pos_attempts_json = models.LongStringField(initial='[]')
    training_neg_attempts_json = models.LongStringField(initial='[]')

    # Per-page logs (overwritten each time)
    training_pos_attempts_page = models.LongStringField(blank=True)
    training_neg_attempts_page = models.LongStringField(blank=True)

    # NEW: map page log (all examples + per-page buffer)
    training_map_attempts_json = models.LongStringField(initial='[]')
    training_map_attempts_page = models.LongStringField(blank=True)

    # Testing that we are getting prolific IDs out
    prolific_pid = models.StringField(blank=True)
    prolific_study_id = models.StringField(blank=True)
    prolific_session_id = models.StringField(blank=True)

    # Testing getting exit pages out
    exit_status = models.StringField(blank=True)
    last_page = models.StringField(blank=True)
    exit_url = models.StringField(blank=True)

    # Post-canvas usability ratings (1–7)
    canvas_difficulty_placement = models.IntegerField(blank=True)
    canvas_difficulty_pos       = models.IntegerField(blank=True)
    canvas_difficulty_neg       = models.IntegerField(blank=True)
    canvas_clarity_statements   = models.IntegerField(blank=True)
    canvas_usability_comment    = models.LongStringField(blank=True)

    # Condition selector
    condition = models.StringField(
        choices=[
            ['interview_tag', 'With interview'],
            ['color_tag',     'Without interview'],
            ['demo',          'Demo (recording only)'],
        ],
        widget=widgets.RadioSelect,
        blank=True,
    )

    # DirectBeliefRating: raw ratings for all predefined stances (JSON)
    stance_ratings_json = models.LongStringField(blank=True)

    # DynamicBeliefRating: [{id, value, sentence}, ...]
    dynamic_belief_ratings_json = models.LongStringField(blank=True)

for i in range(C.MAX_BELIEF_ITEMS):
    setattr(Player, f"belief_accuracy_{i}", models.IntegerField(blank=True))
    setattr(Player, f"belief_relevance_{i}", models.IntegerField(blank=True))

def _strip_prefix(template):
    """Remove 'I [SCALE] that ' prefix, leaving just the declarative content."""
    return re.sub(r'^I \[SCALE\] that ', '', template)


# Condition helpers — update here when adding new conditions
_INTERVIEW_CONDITIONS   = {'interview', 'interview_short', 'interview_tag'}
_CANVAS_CONDITIONS      = {'direct', 'direct_short', 'direct_v2', 'direct_v2_short',
                           'direct_noprefix', 'color', 'color_tag',
                           'interview', 'interview_short', 'interview_tag', 'demo'}
_SHORT_LABEL_CONDITIONS = {'direct_short', 'interview_short', 'direct_v2_short'}
_V2_CONDITIONS          = {'direct_v2', 'direct_v2_short', 'color', 'color_tag',
                           'interview_tag'}
_NOPREFIX_CONDITIONS    = {'direct_noprefix', 'color', 'color_tag', 'interview_tag', 'demo'}
_TAG_CONDITIONS         = {'color_tag', 'interview_tag'}

# Hardcoded nodes for the demo condition (Spanish learning scenario)
_DEMO_NODES = [
    {"dynamic_sentence_simple": "I want to become fluent in Spanish: agree",                              "short_label": "Fluency goal",     "rating": 5},
    {"dynamic_sentence_simple": "I practice Spanish for 20 minutes every day: agree",                    "short_label": "Daily practice",   "rating": 5},
    {"dynamic_sentence_simple": "A colleague has invited me to join a Spanish conversation group: agree", "short_label": "Conversation group","rating": 5},
    {"dynamic_sentence_simple": "I enjoy practicing Spanish: disagree",                                   "short_label": "Enjoy practicing", "rating": 2},
    {"dynamic_sentence_simple": "I feel self-conscious when speaking Spanish in front of others: agree",  "short_label": "Self-conscious",   "rating": 5},
]

###### PAGES ######
# CONSENT
class Consent(Page):
    form_model = 'player'
    form_fields = ['consent_given']

    @staticmethod
    def vars_for_template(player: Player):
        from .study_config import CONSENT_INTRO, CONSENT_HIGHLIGHT
        stamp(player, 'consent:render')
        return dict(
            consent_intro=CONSENT_INTRO,
            consent_highlight=CONSENT_HIGHLIGHT,
        )

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        # logging things now
        participant = player.participant
        pid = participant.label or participant.vars.get('PROLIFIC_PID') or ''
        player.prolific_pid = pid

        # not sure how to log this right now
        player.prolific_study_id = (
            participant.vars.get('STUDY_ID')
            or participant.vars.get('study_id')
            or ''
        )
        player.prolific_session_id = (
            participant.vars.get('SESSION_ID')
            or participant.vars.get('session_id')
            or ''
        )

        # Condition is selected via ConditionSelector page after consent

        stamp(player, 'consent:submit')
        player.force_answer = True

    def error_message(self, values):
        if values['consent_given'] is None:
            return "Please indicate whether you consent to participate."

# INTERVIEW 
class ConditionSelector(Page):
    """Supervisor-facing page: choose which experimental condition to run."""
    form_model  = 'player'
    form_fields = ['condition']

    @staticmethod
    def is_displayed(player: Player):
        return False  # auto-assign condition; remove this line to re-enable manual selection

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        if not player.field_maybe_none('condition'):
            player.condition = 'color_tag'
        if player.field_maybe_none('condition') == 'demo':
            player.final_nodes = json.dumps(_DEMO_NODES)
            player.num_nodes   = len(_DEMO_NODES)


class Information(Page):
    form_model = 'player'

    @staticmethod
    def is_displayed(player: Player):
        return player.consent_given and player.field_maybe_none('condition') in _INTERVIEW_CONDITIONS

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        stamp(player, 'information:submit')

# we should remove the audio data
# just douple check this.
class InterviewTest(Page):
    form_model = 'player'
    form_fields = ['interview_test', 'audio_data'] # testing audio

    @staticmethod
    def is_displayed(player: Player):
        return player.consent_given
    
    @staticmethod 
    def before_next_page(player: Player, timeout_happened):
        stamp(player, 'interviewtest:submit')

class InterviewMain(Page):
    form_model = 'player'
    form_fields = ['current_answer', 'voice_answer']

    @staticmethod
    def vars_for_template(player: Player):
        conversation = json.loads(player.conversation_json)

        if "interview_turns" not in player.participant.vars:
            player.participant.vars["interview_turns"] = 1

        if not conversation:
            from .llm_prompts import INTERVIEW_OPENING_QUESTION
            conversation.append({
                "question": INTERVIEW_OPENING_QUESTION,
                "answer": "",
                "time_sent": datetime.utcnow().isoformat(),
                "time_received": None
            })
            player.conversation_json = json.dumps(conversation)

        return dict(
            conversation=conversation,
            current_turn=player.participant.vars["interview_turns"],
            max_turns=C.MAX_TURNS,
            progress_percentage=int(100 * player.participant.vars["interview_turns"] / C.MAX_TURNS)
        )

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        conversation = json.loads(player.conversation_json)

        # Determine response and input mode
        response = player.current_answer.strip() if player.current_answer else player.voice_answer.strip()
        input_mode = "text" if player.current_answer.strip() else "voice" if player.voice_answer.strip() else "unknown"

        # Always save the last given response if not empty
        if response:
            conversation[-1]["answer"] = response
            conversation[-1]["input_mode"] = input_mode
            conversation[-1]["time_received"] = datetime.utcnow().isoformat()
        else:
            # Fallback for debuging (should not happen with proper UI)
            conversation[-1]["answer"] = "[No response detected]"
            conversation[-1]["input_mode"] = "unknown"
            conversation[-1]["time_received"] = datetime.utcnow().isoformat()

        current_turn = player.participant.vars["interview_turns"]

        # Only append a new question if there are remaining turns
        if current_turn < C.MAX_TURNS:
            # Collect non-empty Q&A pairs only
            qa_history = [
                UserAnswer(question=entry["question"], answer=entry["answer"])
                for entry in conversation if entry.get("answer") and entry["answer"].strip()
            ]
            llm_turn = generate_conversational_question(qa_history, C.MAX_TURNS)

            conversation.append({
                "question": llm_turn.interviewer_utterance,
                "answer": "",  # start empty for next turn
                "time_sent": datetime.utcnow().isoformat()
            })

        # Save updated conversation
        player.conversation_json = json.dumps(conversation)
        player.participant.vars["interview_turns"] = current_turn + 1
        stamp(player, 'interviewmain:submit')

    @staticmethod
    def is_displayed(player: Player):
        return (
            player.consent_given
            and player.field_maybe_none('condition') in _INTERVIEW_CONDITIONS
            and player.participant.vars.get("interview_turns", 1) <= C.MAX_TURNS
        )

class ConversationFeedback(Page):
    form_model = 'player'
    form_fields = [
        'conv_overall_0_100', 'conv_overall_cat',
        'conv_relevant_0_100', 'conv_relevant_cat',
        'conv_easy_chat_0_100', 'conv_easy_chat_cat',
        'conv_comfort_0_100', 'conv_comfort_cat',
        'conv_creepy_0_100', 'conv_creepy_cat',
        'conv_open_feedback',
    ]
    
    @staticmethod
    def is_displayed(player):
        return player.consent_given and player.field_maybe_none('condition') in _INTERVIEW_CONDITIONS

    # async live method
    @staticmethod
    async def live_method(player, data):
        async def call_and_parse(prompt, retries=3, delay=3):
            """Call OpenAI safely and ensure valid parsed list of detected stances."""
            for attempt in range(retries):
                try:
                    completion = await ASYNC_CLIENT.chat.completions.create(
                        model="gpt-4.1-2025-04-14",
                        messages=[{"role": "user", "content": prompt}],
                        stream=False,
                    )
                    raw = completion.choices[0].message.content.strip()

                    # Try JSON parsing
                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError:
                        cleaned = raw.replace("```json", "").replace("```", "").strip()
                        parsed = json.loads(cleaned)

                    # Normalize structure — closed-stance returns {"detected": [...]}
                    if isinstance(parsed, dict) and "detected" in parsed:
                        return parsed["detected"]
                    elif isinstance(parsed, dict) and "results" in parsed:
                        return parsed["results"]
                    elif isinstance(parsed, list):
                        return parsed
                    else:
                        raise ValueError("Response not in expected JSON list format.")

                except Exception as e:
                    print(f"⚠️ Attempt {attempt+1} failed:", e)
                    if attempt < retries - 1:
                        await asyncio.sleep(delay)
                    else:
                        raise  # Final failure after retries

        try:
            # --- Build the prompt ---
            # preload_interview(player, RECORDED_QA)  # uncomment to use recorded QA
            conversation = json.loads(player.conversation_json or "[]")
            qa = {
                e["question"]: e["answer"]
                for e in conversation
                if e.get("answer") and str(e["answer"]).strip()
            }

            prompt = make_node_prompt(qa)
            player.prompt_used = prompt

            # --- Run background call ---
            llm_nodes_list = await call_and_parse(prompt, retries=3, delay=2)

            # Enrich with statement/label from STANCE_LOOKUP
            llm_nodes_list = enrich_detected_stances(llm_nodes_list or [])

            # --- Store for later use (no save()) ---
            player.llm_result = json.dumps({"detected": llm_nodes_list}, indent=2)
            player.generated_nodes = json.dumps(llm_nodes_list)
            player.num_nodes = len(llm_nodes_list)

            yield {player.id_in_group: {"done": True}}

        except Exception as e:
            print("❌ LLM permanently failed:", e)
            yield {player.id_in_group: {"done": False}}

    @staticmethod
    def before_next_page(player, timeout_happened):
        stamp(player, "conv_feedback:submit")


class BeliefRating(Page):
    form_model = 'player'

    @staticmethod
    def _all_items(player: Player):
        nodes = json.loads(player.generated_nodes or '[]')
        real = [{"belief": n.get("statement", ""), "is_distractor": False} for n in nodes]
        items = real
        rnd = random.Random(player.participant.code)
        rnd.shuffle(items)
        return items

    @staticmethod
    def get_form_fields(player: Player):
        items = BeliefRating._all_items(player)
        fields = []
        for i in range(len(items)):
            fields.append(f"belief_accuracy_{i}")
            fields.append(f"belief_relevance_{i}")
        return fields

    @staticmethod
    def vars_for_template(player: Player):
        items = BeliefRating._all_items(player)
        qa_pairs = json.loads(player.conversation_json or "[]")

        belief_items = []
        for i, it in enumerate(items):
            belief_items.append({
                "index": i,
                "belief": it["belief"],
                "agreement": player.field_maybe_none(f"belief_accuracy_{i}"),
                "relevance": player.field_maybe_none(f"belief_relevance_{i}"),
            })

        return dict(belief_items=belief_items, transcript=qa_pairs, C=C)

    @staticmethod
    def error_message(player: Player, values):
        items = BeliefRating._all_items(player)
        missing = False
        accuracy_ratings = []
        relevance_ratings = []

        for i, it in enumerate(items):
            belief = it["belief"]
            is_distractor = it["is_distractor"]
            agreement = values.get(f"belief_accuracy_{i}", None)
            relevance = values.get(f"belief_relevance_{i}", None)

            setattr(player, f"belief_accuracy_{i}",
                    int(agreement) if agreement not in (None, "") else None)
            setattr(player, f"belief_relevance_{i}",
                    int(relevance) if relevance not in (None, "") else None)

            if agreement in (None, "") or relevance in (None, ""):
                missing = True

            accuracy_ratings.append({
                "belief": belief,
                "rating": None if agreement in (None, "") else int(agreement),
                "is_distractor": is_distractor,
            })
            relevance_ratings.append({
                "belief": belief,
                "relevance": None if relevance in (None, "") else int(relevance),
                "is_distractor": is_distractor,
            })

        player.generated_nodes_accuracy = json.dumps(accuracy_ratings)
        player.generated_nodes_relevance = json.dumps(relevance_ratings)
        player.distractor_ratings = json.dumps([
            {"index": i, "belief": r["belief"], "rating": r["rating"]}
            for i, r in enumerate(accuracy_ratings) if r["is_distractor"]
        ])

        if missing:
            return "Please rate all items before continuing."

        # distractor_problem: any distractor with agreement >= 4 (neutral or above)
        player.distractor_problem = any(
            r["is_distractor"] and r["rating"] is not None and r["rating"] >= 4
            for r in accuracy_ratings
        )

        # no filtering — all real (non-distractor) items go to the canvas
        final = []
        for a, rv in zip(accuracy_ratings, relevance_ratings):
            if not a["is_distractor"]:
                final.append({
                    "belief":    a["belief"],
                    "rating":    a["rating"],    # agreement 1–7
                    "relevance": rv["relevance"], # importance 1–7
                })
        player.final_nodes = json.dumps(final)
        player.num_nodes = len(final)

    @staticmethod
    def is_displayed(player: Player):
        return (
            player.num_nodes >= C.NUM_NODES_THRESHOLD
            and player.consent_given
            and player.field_maybe_none('condition') == 'A'
        )

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        stamp(player, 'belief_rating:submit')
    

# TRAINING PAGES 
# [ insert page with more general description of training. ]
# [ but probably we will want to combine this ]
class TrainingBrief(Page):
    form_model = 'player'
    form_fields: list[str] = []

    @staticmethod
    def is_displayed(player: Player):
        return player.num_nodes >= C.NUM_NODES_THRESHOLD and player.consent_given

    @staticmethod
    def vars_for_template(player: Player):
        wave = player.session.config.get('wave', 'w1')  # default w1 if missing
        return dict(wave=wave)

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        stamp(player, "training_brief:submit")


# INTRO HELPERS 
def _get_training_order(player: Player) -> list[str]:
    pv = player.participant.vars

    # Only draw a fresh random order if not already present
    if 'training_order' not in pv:
        keys = list(C.TRAINING_SCENARIOS.keys())   # e.g. ["example1","example2","example3"]
        random.shuffle(keys)
        pv['training_order'] = keys

    return pv['training_order']

def _get_scenario_for_index(player: Player, idx: int) -> TrainingScenario:
    order = _get_training_order(player)  # will crash if not set
    key = order[idx]                     # IndexError if out of range -> good
    return C.TRAINING_SCENARIOS[key]     # KeyError if mis-specified -> good

def _training_intro_vars_for(player: Player, idx: int):
    scenario = _get_scenario_for_index(player, idx)
    return dict(
        training_items=scenario.train_stance_list,
        vignette_html=scenario.vignette_html,
        vignette_name=scenario.name,
        training_example_index=idx,
        training_example_key=scenario.key,
    )

def _training_intro_before_next_for(player: Player, idx: int, timeout_happened):
    scenario = _get_scenario_for_index(player, idx)
    nodes = [{"belief": b} for b in scenario.train_stance_list]
    player.training_nodes = json.dumps(nodes, ensure_ascii=False)

    # store full order once (only if not already stored)
    current = player.field_maybe_none('training_order_json')
    if not current:
        order = _get_training_order(player)
        player.training_order_json = json.dumps(order, ensure_ascii=False)

    stamp(player, f"training_intro_{idx}:submit")

# MAP HELPERS
def _training_map_vars_for(player: Player, idx: int):
    scenario = _get_scenario_for_index(player, idx)

    nodes = json.loads(player.training_nodes or '[]')
    labels = [n.get('belief') for n in nodes if n.get('belief')]

    return dict(
        belief_labels_json=json.dumps(labels, ensure_ascii=False),
        vignette_html=scenario.vignette_html,
        vignette_name=scenario.name,
        training_example_index=idx,
        training_example_key=scenario.key,
    )

def _training_map_before_next_for(player: Player, idx: int, timeout_happened):
    _merge_map_attempts(player, idx)
    scenario = _get_scenario_for_index(player, idx)
    stamp(player, f"training_map_{idx}:submit")

# POS HELPERS
def _training_pos_vars_for(player: Player, idx: int):
    scenario = _get_scenario_for_index(player, idx)

    positions = json.loads(player.training_positions_1)  # must exist
    pos_by_label = {p["label"]: p for p in positions}

    ordered_ids = sorted(scenario.stance_id_to_text.keys())
    labels = [scenario.stance_id_to_text[i] for i in ordered_ids]

    belief_points = [
        {"x": pos_by_label[label]["x"], "y": pos_by_label[label]["y"]}
        for label in labels
    ]

    allowed_map = {
        f"{a}-{b}": allowed
        for (a, b), allowed in scenario.allowed_relations.items()
    }
    required_pos = [f"{a}-{b}" for (a, b) in scenario.required_positive_pairs]

    return dict(
        belief_labels_json=json.dumps(labels, ensure_ascii=False),
        belief_points=json.dumps(belief_points),
        allowed_map_json=json.dumps(allowed_map),
        required_positive_json=json.dumps(required_pos),
        stance_id_to_text_json=json.dumps(scenario.stance_id_to_text),
        training_pos_retry_count=player.training_pos_retry_count,
        vignette_html=scenario.vignette_html,
        vignette_name=scenario.name,
        training_example_index=idx,
        training_example_key=scenario.key,
    )

def _training_pos_before_next_for(player: Player, idx: int, timeout_happened):
    _merge_pos_attempts(player, idx)
    scenario = _get_scenario_for_index(player, idx)
    stamp(player, f"training_edge_pos_{idx}:submit")

# NEG HELPERS
def _merge_map_attempts(player: Player, idx: int):
    raw_page = player.training_map_attempts_page or "[]"
    try:
        page_attempts = json.loads(raw_page)
    except:
        page_attempts = []

    raw_all = player.training_map_attempts_json or "[]"
    try:
        all_attempts = json.loads(raw_all)
    except:
        all_attempts = []

    for attempt in page_attempts:
        attempt["example_index"] = idx

    all_attempts.extend(page_attempts)

    player.training_map_attempts_json = json.dumps(all_attempts, ensure_ascii=False)
    player.training_map_attempts_page = ""
    
def _merge_pos_attempts(player: Player, idx: int) -> None:
    """
    Take the per-page JSON from `training_pos_attempts_page`, attach it to the
    global list in `training_pos_attempts_json`, and clear the per-page field.
    """
    raw_page = player.training_pos_attempts_page or "[]"
    try:
        page_attempts = json.loads(raw_page)
    except json.JSONDecodeError:
        page_attempts = []

    raw_all = player.training_pos_attempts_json or "[]"
    try:
        all_attempts = json.loads(raw_all)
    except json.JSONDecodeError:
        all_attempts = []

    # Optionally enforce example_index = idx (even though JS already sets it)
    for attempt in page_attempts:
        attempt["example_index"] = idx

    all_attempts.extend(page_attempts)

    player.training_pos_attempts_json = json.dumps(all_attempts, ensure_ascii=False)
    player.training_pos_attempts_page = ""


def _merge_neg_attempts(player: Player, idx: int) -> None:
    """
    Same idea for the negative page. Read from `training_neg_attempts_page`,
    append to `training_neg_attempts_json`, clear page field.
    """
    raw_page = player.training_neg_attempts_page or "[]"
    try:
        page_attempts = json.loads(raw_page)
    except json.JSONDecodeError:
        page_attempts = []

    raw_all = player.training_neg_attempts_json or "[]"
    try:
        all_attempts = json.loads(raw_all)
    except json.JSONDecodeError:
        all_attempts = []

    for attempt in page_attempts:
        attempt["example_index"] = idx

    all_attempts.extend(page_attempts)

    player.training_neg_attempts_json = json.dumps(all_attempts, ensure_ascii=False)
    player.training_neg_attempts_page = ""

def _training_neg_vars_for(player: Player, idx: int):
    scenario = _get_scenario_for_index(player, idx)

    # Positions after the positive page; these must exist at this point
    positions = json.loads(player.training_positions_2)
    pos_by_label = {p["label"]: p for p in positions}

    ordered_ids = sorted(scenario.stance_id_to_text.keys())
    labels = [scenario.stance_id_to_text[i] for i in ordered_ids]

    belief_points = [
        {"x": pos_by_label[label]["x"], "y": pos_by_label[label]["y"]}
        for label in labels
    ]

    prior_edges = json.loads(player.training_edges_2)

    allowed_map = {
        f"{a}-{b}": allowed
        for (a, b), allowed in scenario.allowed_relations.items()
    }
    required_neg = [f"{a}-{b}" for (a, b) in scenario.required_negative_pairs]

    return dict(
        belief_points=json.dumps(belief_points),
        belief_labels_json=json.dumps(labels, ensure_ascii=False),
        belief_edges_json=json.dumps(prior_edges),
        allowed_map_json=json.dumps(allowed_map),
        required_negative_json=json.dumps(required_neg),
        stance_id_to_text_json=json.dumps(scenario.stance_id_to_text),
        training_neg_retry_count=player.training_neg_retry_count,
        vignette_html=scenario.vignette_html,
        vignette_name=scenario.name,
        training_example_index=idx,
        training_example_key=scenario.key,
    )

def _training_neg_before_next_for(player: Player, idx: int, timeout_happened):
    _merge_neg_attempts(player, idx)
    scenario = _get_scenario_for_index(player, idx)
    stamp(player, f"training_edge_neg_{idx}:submit")

class TrainingIntro1(Page):
    template_name = 'otreesurvey_app/TrainingIntro.html'
    form_model = 'player'

    @staticmethod
    def is_displayed(player: Player):
        return player.num_nodes >= C.NUM_NODES_THRESHOLD and player.consent_given

    @staticmethod
    def vars_for_template(player: Player):
        return _training_intro_vars_for(player, 0)

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        _training_intro_before_next_for(player, 0, timeout_happened)

class TrainingIntro2(TrainingIntro1):
    template_name = 'otreesurvey_app/TrainingIntro.html'
    
    @staticmethod
    def vars_for_template(player: Player):
        return _training_intro_vars_for(player, 1)

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        _training_intro_before_next_for(player, 1, timeout_happened)

class TrainingIntro3(TrainingIntro1):
    template_name = 'otreesurvey_app/TrainingIntro.html'

    @staticmethod
    def vars_for_template(player: Player):
        return _training_intro_vars_for(player, 2)

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        _training_intro_before_next_for(player, 2, timeout_happened)

class TrainingMap1(Page):
    template_name = 'otreesurvey_app/TrainingMap.html'
    form_model = 'player'
    form_fields = ['training_positions_1', 'training_map_attempts_page']

    @staticmethod
    def is_displayed(player: Player):
        return player.num_nodes >= C.NUM_NODES_THRESHOLD and player.consent_given

    @staticmethod
    def vars_for_template(player: Player):
        return _training_map_vars_for(player, 0)

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        _training_map_before_next_for(player, 0, timeout_happened)


class TrainingMap2(TrainingMap1):
    @staticmethod
    def vars_for_template(player: Player):
        return _training_map_vars_for(player, 1)

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        _training_map_before_next_for(player, 1, timeout_happened)


class TrainingMap3(TrainingMap1):
    @staticmethod
    def vars_for_template(player: Player):
        return _training_map_vars_for(player, 2)

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        _training_map_before_next_for(player, 2, timeout_happened)

class TrainingPos1(Page):
    template_name = 'otreesurvey_app/TrainingPos.html'
    form_model = 'player'
    form_fields = [
        'training_positions_2',
        'training_edges_2',
        'training_pos_retry_count',
        'training_pos_attempts_page',
    ]

    @staticmethod
    def is_displayed(player: Player):
        return player.num_nodes >= C.NUM_NODES_THRESHOLD and player.consent_given

    @staticmethod
    def vars_for_template(player: Player):
        return _training_pos_vars_for(player, 0)

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        _training_pos_before_next_for(player, 0, timeout_happened)


class TrainingPos2(TrainingPos1):
    @staticmethod
    def vars_for_template(player: Player):
        return _training_pos_vars_for(player, 1)

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        _training_pos_before_next_for(player, 1, timeout_happened)


class TrainingPos3(TrainingPos1):
    @staticmethod
    def vars_for_template(player: Player):
        return _training_pos_vars_for(player, 2)

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        _training_pos_before_next_for(player, 2, timeout_happened)
    

class TrainingNeg1(Page):
    template_name = 'otreesurvey_app/TrainingNeg.html'
    form_model = 'player'
    form_fields = [
        'training_positions_3',
        'training_edges_3',
        'training_neg_retry_count',
        'training_neg_attempts_page',
    ]

    @staticmethod
    def is_displayed(player: Player):
        return player.num_nodes >= C.NUM_NODES_THRESHOLD and player.consent_given

    @staticmethod
    def vars_for_template(player: Player):
        return _training_neg_vars_for(player, 0)

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        _training_neg_before_next_for(player, 0, timeout_happened)


class TrainingNeg2(TrainingNeg1):
    @staticmethod
    def vars_for_template(player: Player):
        return _training_neg_vars_for(player, 1)

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        _training_neg_before_next_for(player, 1, timeout_happened)


class TrainingNeg3(TrainingNeg1):
    @staticmethod
    def vars_for_template(player: Player):
        return _training_neg_vars_for(player, 2)

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        _training_neg_before_next_for(player, 2, timeout_happened)


class MapNodePlacement(Page):
    form_model = 'player'
    form_fields = ['positions_1']

    @staticmethod
    def vars_for_template(player):
        node_data = get_node_display_data(player)
        cond = player.field_maybe_none('condition') or ''
        show_transcript = cond in _INTERVIEW_CONDITIONS
        qa_pairs = json.loads(player.conversation_json or "[]") if show_transcript else []
        return dict(
            node_data_json=json.dumps(node_data),
            short_labels="true" if cond in _SHORT_LABEL_CONDITIONS else "false",
            transcript=qa_pairs,
            show_transcript=show_transcript,
        )

    @staticmethod
    def is_displayed(player: Player):
        return (
            player.num_nodes >= C.NUM_NODES_THRESHOLD
            and player.consent_given
            and player.field_maybe_none('condition') in _CANVAS_CONDITIONS
        )

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        stamp(player, 'self_map:submit')


class MapEdgePos(Page):
    form_model = 'player'
    form_fields = ['positions_2', 'edges_2']

    @staticmethod
    def vars_for_template(player):
        node_data = get_node_display_data(player)
        positions = json.loads(player.positions_1 or '[]')
        pos_by_belief = {p.get('full_label', p['label']): p for p in positions}
        belief_points = [
            {
                "label":       nd["belief"],
                "short_label": nd.get("short_label", ""),
                "x":           pos_by_belief[nd["belief"]]['x'],
                "y":           pos_by_belief[nd["belief"]]['y'],
                "radius":      nd["radius"],
                "color":       nd["color"],
            }
            for nd in node_data
        ]
        cond = player.field_maybe_none('condition') or ''
        show_transcript = cond in _INTERVIEW_CONDITIONS
        qa_pairs = json.loads(player.conversation_json or "[]") if show_transcript else []
        return dict(
            belief_points=belief_points,
            short_labels="true" if cond in _SHORT_LABEL_CONDITIONS else "false",
            belief_edges_json=json.dumps([]),
            transcript=qa_pairs,
            show_transcript=show_transcript,
        )

    @staticmethod
    def is_displayed(player):
        return (
            player.num_nodes >= C.NUM_NODES_THRESHOLD
            and player.consent_given
            and player.field_maybe_none('condition') in _CANVAS_CONDITIONS
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
        stamp(player, 'self_edge_pos:submit')

class MapVideoIntro(Page):
    @staticmethod
    def vars_for_template(player):
        demo_statements = [
            {
                "text":  n["dynamic_sentence_simple"],
                "color": _node_color(n["rating"]),
            }
            for n in _DEMO_NODES
        ]
        return dict(demo_statements=demo_statements, own_statements_colored=demo_statements)

    @staticmethod
    def is_displayed(player):
        return (
            player.num_nodes >= C.NUM_NODES_THRESHOLD
            and player.consent_given
            and player.field_maybe_none('condition') in _CANVAS_CONDITIONS
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
        stamp(player, 'map_video_intro:submit')

class MapIntro(Page):
    @staticmethod
    def vars_for_template(player):
        # Final nodes with participants' own statements
        nodes = json.loads(player.final_nodes or "[]")
        cond = player.field_maybe_none('condition') or ''
        noprefix = cond in _NOPREFIX_CONDITIONS

        own_statements = [
            n.get("dynamic_sentence_simple") or n.get("dynamic_sentence_full") or n["belief"]
            for n in nodes
            if n.get("belief") or n.get("dynamic_sentence_simple")
        ]

        # For noprefix conditions, attach colors so the template can show colored dots
        own_statements_colored = [
            {
                "text":  n.get("dynamic_sentence_simple") or n.get("dynamic_sentence_full") or n["belief"],
                "color": _node_color(n.get("rating")),
                "word":  n.get("belief", ""),   # "agree" or "disagree"
            }
            for n in nodes
            if n.get("belief") or n.get("dynamic_sentence_simple")
        ]

        show_transcript = cond in _INTERVIEW_CONDITIONS
        qa_pairs = json.loads(player.conversation_json or "[]") if show_transcript else []

        return dict(
            transcript=qa_pairs,
            show_transcript=show_transcript,
            own_statements=own_statements,
            own_statements_colored=own_statements_colored,
            noprefix=noprefix,
            is_demo=cond == 'demo',
        )

    @staticmethod
    def is_displayed(player):
        return (
            player.num_nodes >= C.NUM_NODES_THRESHOLD
            and player.consent_given
            and player.field_maybe_none('condition') in _CANVAS_CONDITIONS
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
        stamp(player, 'map_intro:submit')

class MapEdgeNeg(Page):
    form_model = 'player'
    form_fields = ['positions_3', 'edges_3']

    @staticmethod
    def vars_for_template(player):
        node_data = get_node_display_data(player)
        positions = json.loads(player.positions_2 or '[]')
        if not positions:
            positions = json.loads(player.positions_1 or '[]')
        prior_edges = json.loads(player.edges_2 or '[]')
        pos_by_belief = {p.get('full_label', p['label']): p for p in positions}
        belief_points = [
            {
                "label":       nd["belief"],
                "short_label": nd.get("short_label", ""),
                "x":           pos_by_belief[nd["belief"]]['x'],
                "y":           pos_by_belief[nd["belief"]]['y'],
                "radius":      nd["radius"],
                "color":       nd["color"],
            }
            for nd in node_data
        ]
        cond = player.field_maybe_none('condition') or ''
        show_transcript = cond in _INTERVIEW_CONDITIONS
        qa_pairs = json.loads(player.conversation_json or "[]") if show_transcript else []
        return dict(
            belief_points=belief_points,
            short_labels="true" if cond in _SHORT_LABEL_CONDITIONS else "false",
            belief_edges_json=json.dumps(prior_edges),
            transcript=qa_pairs,
            show_transcript=show_transcript,
        )

    @staticmethod
    def is_displayed(player):
        return (
            player.num_nodes >= C.NUM_NODES_THRESHOLD
            and player.consent_given
            and player.field_maybe_none('condition') in _CANVAS_CONDITIONS
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
        stamp(player, 'self_edge_neg:submit')


class MapProximity(Page):
    """Experimental: nodes placed on canvas; edges auto-generated from proximity."""
    form_model  = 'player'
    form_fields = ['positions_auto', 'edges_auto']

    @staticmethod
    def vars_for_template(player):
        node_data = get_node_display_data(player)
        return dict(node_data_json=json.dumps(node_data))

    @staticmethod
    def is_displayed(player):
        return player.num_nodes >= C.NUM_NODES_THRESHOLD and player.consent_given

    @staticmethod
    def before_next_page(player, timeout_happened):
        stamp(player, 'proximity_map:submit')


class MeatScale(Page):
    form_model = 'player'
    form_fields = [
        'meat_consumption_present',
        'meat_consumption_past',
        'meat_consumption_future',
        'dissonance_personal',
        'dissonance_social'
    ]

    @staticmethod
    def is_displayed(player: Player): 
        return (
            player.num_nodes >= C.NUM_NODES_THRESHOLD
            and player.consent_given
        )

    @staticmethod
    def error_message(player: Player, values):
        # Server-side safety: require all three to be provided
        if any(values.get(f) in (None, '') for f in [
            'meat_consumption_present',
            'meat_consumption_past',
            'meat_consumption_future',
        ]):
            return "Please move each slider to select a value."

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        stamp(player, 'meatscale:submit')


def _make_intervention_display(idx, total):
    """Factory: one display page per intervention slot (text resolved at runtime)."""
    def _resolve(player):
        from .interventions import INTERVENTIONS as _I
        order = json.loads(player.field_maybe_none('intervention_order_json') or 'null')
        i = order[idx] if order else idx
        return _I[i]

    def _vars(player):
        intv = _resolve(player)
        return dict(
            intervention_text=intv['text'],
            intervention_title=intv['title'],
            intv_index=idx + 1,
            intv_total=total,
        )

    def _is_displayed(player):
        return player.consent_given and player.field_maybe_none('condition') == 'preview'

    def _before_next(player, timeout_happened):
        stamp(player, f'intervention_display_{idx}:submit')

    cls = type(
        f'InterventionDisplay_{idx}',
        (Page,),
        {
            'template_name':    'otreesurvey_app/InterventionDisplay.html',
            'vars_for_template': staticmethod(_vars),
            'is_displayed':      staticmethod(_is_displayed),
            'before_next_page':  staticmethod(_before_next),
        },
    )
    return cls


def _make_intervention_rating(idx, total):
    """Factory: one rating page per intervention slot (text resolved at runtime)."""
    def _resolve(player):
        from .interventions import INTERVENTIONS as _I
        order = json.loads(player.field_maybe_none('intervention_order_json') or 'null')
        i = order[idx] if order else idx
        return _I[i]

    def _vars(player):
        intv = _resolve(player)
        return dict(
            intervention_text=intv['text'],
            intv_index=idx + 1,
            intv_total=total,
        )

    def _is_displayed(player):
        return player.consent_given and player.field_maybe_none('condition') == 'preview'

    def _before_next(player, timeout_happened):
        intv = _resolve(player)
        raw = player.field_maybe_none('intervention_ratings_json') or '[]'
        try:
            ratings = json.loads(raw)
        except Exception:
            ratings = []
        ratings.append({
            'index':            idx,
            'label':            intv['label'],
            'convincing':       player.field_maybe_none('intervention_convincing'),
            'surprising':       player.field_maybe_none('intervention_surprising'),
            'understandable':   player.field_maybe_none('intervention_understandable'),
            'emotional':        player.field_maybe_none('intervention_emotional'),
            'comment':          player.field_maybe_none('intervention_comment') or '',
        })
        player.intervention_ratings_json = json.dumps(ratings)
        stamp(player, f'intervention_rating_{idx}:submit')

    cls = type(
        f'InterventionRating_{idx}',
        (Page,),
        {
            'template_name':    'otreesurvey_app/InterventionRating.html',
            'form_model':       'player',
            'form_fields':      [
                'intervention_convincing',
                'intervention_surprising',
                'intervention_understandable',
                'intervention_emotional',
                'intervention_comment',
            ],
            'vars_for_template': staticmethod(_vars),
            'is_displayed':      staticmethod(_is_displayed),
            'before_next_page':  staticmethod(_before_next),
        },
    )
    return cls


# Build one Display+Rating pair per intervention — update interventions.py to add/remove texts
from .interventions import INTERVENTIONS as _INTERVENTIONS
INTERVENTION_PAGE_LIST = []
for _idx in range(len(_INTERVENTIONS)):
    INTERVENTION_PAGE_LIST.append(_make_intervention_display(_idx, len(_INTERVENTIONS)))
    INTERVENTION_PAGE_LIST.append(_make_intervention_rating(_idx, len(_INTERVENTIONS)))


class PreviewInfo(Page):
    """Introduction page for the preview (intervention) condition."""

    @staticmethod
    def is_displayed(player: Player):
        return player.consent_given and player.field_maybe_none('condition') == 'preview'

    @staticmethod
    def before_next_page(player, timeout_happened):
        stamp(player, 'preview_info:submit')


class PreviewTransition(Page):
    """Transition page between DirectBeliefRating and the intervention texts."""

    @staticmethod
    def is_displayed(player: Player):
        return player.consent_given and player.field_maybe_none('condition') == 'preview'

    @staticmethod
    def before_next_page(player, timeout_happened):
        from .interventions import INTERVENTIONS as _I
        # Assign randomised order once; idempotent on back-navigation
        if not player.field_maybe_none('intervention_order_json'):
            order = list(range(len(_I)))
            random.Random(player.participant.code).shuffle(order)
            player.intervention_order_json = json.dumps(order)
        stamp(player, 'preview_transition:submit')


class DirectBeliefRating(Page):
    """Condition B: rate all predefined stances directly (no interview)."""
    form_model = 'player'

    @staticmethod
    def get_form_fields(player: Player):
        from .dynamic_items import DYNAMIC_ITEMS as STANCES
        fields = []
        for i in range(len(STANCES)):
            fields.append(f"belief_accuracy_{i}")
            fields.append(f"belief_relevance_{i}")
        fields.append('direct_belief_comment')
        return fields

    @staticmethod
    def vars_for_template(player: Player):
        from .dynamic_items import DYNAMIC_ITEMS as STANCES
        stance_items = [
            {
                "index":     i,
                "id":        s["id"],
                "statement": s["statement"],
                "agreement": player.field_maybe_none(f"belief_accuracy_{i}"),
                "relevance": player.field_maybe_none(f"belief_relevance_{i}"),
            }
            for i, s in enumerate(STANCES)
        ]
        rnd = random.Random(player.participant.code)
        rnd.shuffle(stance_items)
        return dict(stance_items=stance_items)

    @staticmethod
    def error_message(player: Player, values):
        from .dynamic_items import DYNAMIC_ITEMS as STANCES
        missing = False
        for i in range(len(STANCES)):
            agreement = values.get(f"belief_accuracy_{i}")
            relevance = values.get(f"belief_relevance_{i}")
            setattr(player, f"belief_accuracy_{i}",
                    int(agreement) if agreement not in (None, "") else None)
            setattr(player, f"belief_relevance_{i}",
                    int(relevance) if relevance not in (None, "") else None)
            if agreement in (None, "") or relevance in (None, ""):
                missing = True
        if missing:
            return "Please rate all items before continuing."

    @staticmethod
    def is_displayed(player: Player):
        return player.consent_given and player.field_maybe_none('condition') in ('B', 'preview')

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        from .dynamic_items import DYNAMIC_ITEMS as STANCES
        final = []
        for i, s in enumerate(STANCES):
            agreement = player.field_maybe_none(f"belief_accuracy_{i}")
            relevance = player.field_maybe_none(f"belief_relevance_{i}")
            if agreement is not None:
                final.append({
                    "belief":    s["statement"],
                    "rating":    agreement,
                    "relevance": relevance,
                    "stance_id": s["id"],
                })
        player.final_nodes = json.dumps(final)
        player.num_nodes   = len(final)
        stamp(player, 'direct_belief_rating:submit')


class DynamicBeliefRating(Page):
    """Condition D: sliders that build the sentence dynamically; feeds canvas."""
    form_model  = 'player'
    form_fields = ['dynamic_belief_ratings_json']

    @staticmethod
    def vars_for_template(player: Player):
        from .dynamic_items import DYNAMIC_ITEMS
        condition = player.field_maybe_none('condition')

        if condition in _INTERVIEW_CONDITIONS:
            # Use only stances detected from the interview
            detected_ids = {
                n.get('stance_id')
                for n in json.loads(player.generated_nodes or '[]')
                if n.get('stance_id')
            }
            source = [item for item in DYNAMIC_ITEMS if item['id'] in detected_ids]
            if not source:
                source = list(DYNAMIC_ITEMS)  # fallback if detection failed
        else:
            source = list(DYNAMIC_ITEMS)

        # Reproducible shuffle per participant
        rnd = random.Random(player.participant.code)
        rnd.shuffle(source)

        use_v2 = condition in _V2_CONDITIONS
        items = [
            {
                "index":     i,
                "id":        item["id"],
                "template":  item.get("template_v2", item["template"]) if use_v2 else item["template"],
                "labels":    item["labels"],
                "anchor_lo": item["anchor_lo"],
                "anchor_hi": item["anchor_hi"],
            }
            for i, item in enumerate(source)
        ]
        return dict(items_json=json.dumps(items), num_items=len(items),
                    show_importance="true", scale_max=6, start_val=1)

    @staticmethod
    def is_displayed(player: Player):
        cond = player.field_maybe_none('condition')
        return player.consent_given and cond in _CANVAS_CONDITIONS and cond != 'demo'

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        raw = player.field_maybe_none('dynamic_belief_ratings_json') or '[]'
        try:
            ratings = json.loads(raw)
        except Exception:
            ratings = []

        from .dynamic_items import DYNAMIC_ITEMS
        cond = player.field_maybe_none('condition') or ''
        use_v2       = cond in _V2_CONDITIONS
        use_noprefix = cond in _NOPREFIX_CONDITIONS
        use_tag      = cond in _TAG_CONDITIONS
        item_lookup = {item["id"]: item for item in DYNAMIC_ITEMS}
        template_lookup = {
            item["id"]: item.get("template_v2", item["template"]) if use_v2 else item["template"]
            for item in DYNAMIC_ITEMS
        }

        final = []
        for entry in ratings:
            # Canvas label: collapse to "agree"/"disagree" (values 1–3 = disagree, 4–6 = agree)
            v = entry.get("value", 0)
            simple_word = "disagree" if v <= 3 else "agree"
            tmpl = template_lookup.get(entry.get("id", ""), "")
            if use_noprefix:
                content = _strip_prefix(tmpl) if tmpl else ""
                # Version B: append ": agree" / ": disagree" after the statement
                simple_sentence = f"{content}: {simple_word}" if use_tag else content
            else:
                simple_sentence = tmpl.replace("[SCALE]", simple_word) if tmpl else simple_word
            item_meta = item_lookup.get(entry.get("id", ""), {})
            final.append({
                "belief":                  simple_word,
                "rating":                  v,
                "relevance":               entry.get("importance", 4),
                "dynamic_id":              entry.get("id", ""),
                "dynamic_val":             v,
                "dynamic_importance":      entry.get("importance"),
                "dynamic_sentence_full":   entry.get("sentence", ""),
                "dynamic_sentence_simple": simple_sentence,
                "short_label":             item_meta.get("short_label", ""),
            })
        player.final_nodes = json.dumps(final)
        player.num_nodes   = len(final)
        stamp(player, 'dynamic_belief_rating:submit')


class VEMI(Page):
    form_model = 'player'
    form_fields = ['vemi_responses']  # hidden JSON from the template

    @staticmethod
    def vars_for_template(player: Player):
        # Send items to the template (keys t/d are fine; JS handles them)
        items = [{"index": i + 1, "t": txt, "d": dom}
                 for i, (txt, dom) in enumerate(C.VEMI_ITEMS)]
        return dict(vemi_items_json=json.dumps(items))

    @staticmethod
    def error_message(player: Player, values):
        # Parse JSON, ensure every item has a 0–100 value (integer)
        raw = values.get('vemi_responses') or ''
        try:
            data = json.loads(raw)
        except Exception:
            return "There was a problem saving your answers. Please try again."

        if not isinstance(data, list) or len(data) != len(C.VEMI_ITEMS):
            return "Please answer every item before continuing."

        for row in data:
            v = row.get('value')
            if v is None:
                return "Please move every slider."
            try:
                iv = int(round(float(v)))
            except Exception:
                return "Please use the slider to select a value between 'Not Important' and 'Very Important'."
            if iv < 0 or iv > 100:
                return "Please use the slider to select a value between 'Not Important' and 'Very Important'."
            row['value'] = iv  # normalize to int 0–100

        # Store cleaned JSON
        player.vemi_responses = json.dumps(data)

    @staticmethod
    def is_displayed(player: Player): 
        return (
            player.num_nodes >= C.NUM_NODES_THRESHOLD
            and player.consent_given
        )
        
    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        stamp(player, 'questionnaire_vemi:submit')
    
class MEMI(Page):
    form_model = 'player'
    form_fields = ['memi_responses']  # just the hidden input

    @staticmethod
    def vars_for_template(player: Player):
        items = [{"index": i+1, "t": txt, "d": dom}
                for i, (txt, dom) in enumerate(C.MEMI_ITEMS)]
        return dict(memi_items_json=json.dumps(items))

    @staticmethod
    def error_message(player: Player, values):
        # Minimal validation: parse JSON, ensure every item has a 1..7 value.
        raw = values.get('memi_responses') or ''
        try:
            data = json.loads(raw)
        except Exception:
            return "There was a problem saving your answers. Please try again."

        if not isinstance(data, list) or len(data) != len(C.MEMI_ITEMS):
            return "Please answer every item before continuing."

        for row in data:
            v = row.get('value')
            if v is None:
                return "Please move every slider."
            try:
                iv = int(v)
            except Exception:
                return "Please use the slider to select a value between 'Not Important' and 'Very Important'."
            if iv < 0 or iv > 100:
                return "Please use the slider to select a value between 'Not Important' and 'Very Important'."
            row['value'] = iv  # normalize to int 0–100

        # Store the cleaned JSON
        player.memi_responses = json.dumps(data)
    
    @staticmethod
    def is_displayed(player: Player): 
        return (
            player.num_nodes >= C.NUM_NODES_THRESHOLD
            and player.consent_given
        )
        
    def before_next_page(player, timeout_happened):
        stamp(player, 'questionnaire_memi:submit')

class Demographics(Page): 
    form_model = 'player'
    form_fields = ['age', 'gender', 'education', 'politics', 'state', 'zipcode']

    @staticmethod
    def is_displayed(player: Player): 
        return (
            player.num_nodes >= C.NUM_NODES_THRESHOLD
            and player.consent_given
        )

    @staticmethod 
    def before_next_page(player: Player, timeout_happened):
        stamp(player, 'demographics:submit')

class CanvasFeedback(Page):
    form_model = 'player'
    form_fields = [
        'canvas_difficulty_placement',
        'canvas_difficulty_pos',
        'canvas_difficulty_neg',
        'canvas_clarity_statements',
        'canvas_usability_comment',
    ]

    @staticmethod
    def is_displayed(player: Player):
        return (
            player.consent_given
            and player.field_maybe_none('condition') in _CANVAS_CONDITIONS
            and player.num_nodes >= C.NUM_NODES_THRESHOLD
        )

    @staticmethod
    def before_next_page(player, timeout_happened):
        stamp(player, 'canvas_feedback:submit')


class Feedback(Page):
    form_model = 'player'
    form_fields = ['final_feedback']

    @staticmethod
    def is_displayed(player: Player):
        return player.consent_given

    @staticmethod
    def before_next_page(player, timeout_happened):
        stamp(player, 'finalfeedback:submit')

### EXIT PAGES ###
class LinkCompletion(Page):

    @staticmethod
    def is_displayed(player: Player):
        return (
            player.consent_given
            and player.num_nodes >= C.NUM_NODES_THRESHOLD
        )

    @staticmethod
    def vars_for_template(player: Player):
        player.exit_status = 'completed'
        player.last_page = 'LinkCompletion'
        player.exit_url = player.session.config['completionlink']
        stamp(player, 'exit:completed')
        return {}

    @staticmethod
    def js_vars(player: Player):
        return dict(
            url=player.session.config['completionlink']
        )

class LinkFailedChecks(Page):

    @staticmethod
    def is_displayed(player: Player):
        return (
            player.consent_given
            and player.num_nodes < C.NUM_NODES_THRESHOLD
        )

    @staticmethod
    def vars_for_template(player: Player):
        # Mark exit status as soon as the page is shown
        player.exit_status = 'failed_checks'
        player.last_page = 'LinkFailedChecks'
        player.exit_url = player.session.config.get('returnlink', player.session.config['completionlink'])
        stamp(player, 'exit:failed_checks')
        return {}

    @staticmethod
    def js_vars(player: Player):
        return dict(
            url=player.session.config.get('returnlink', player.session.config['completionlink'])
        )

class LinkNoConsent(Page):

    @staticmethod
    def is_displayed(player: Player):
        return not player.consent_given

    @staticmethod
    def vars_for_template(player: Player):
        player.exit_status = 'no_consent'
        player.last_page = 'LinkNoConsent'
        player.exit_url = player.session.config['noconsentlink']
        stamp(player, 'exit:no_consent')
        return {}

    @staticmethod
    def js_vars(player: Player):
        return dict(
            url=player.session.config['noconsentlink']
        )

page_sequence = [
    Consent,
    LinkNoConsent,
    ConditionSelector,
    # Interview condition only
    Information,
    *[InterviewMain for _ in range(C.MAX_TURNS)],
    ConversationFeedback,
    # Both conditions
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