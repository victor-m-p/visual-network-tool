from openai import OpenAI
import os
from dotenv import load_dotenv
import instructor
from tenacity import retry, stop_after_attempt, wait_fixed
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Tuple

from .dynamic_items import DYNAMIC_ITEMS

STANCE_LOOKUP = {item["id"]: item for item in DYNAMIC_ITEMS}

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

custom_retry = retry(
    stop=stop_after_attempt(5),
    wait=wait_fixed(2),
    reraise=True,
)

@custom_retry
def call_openai(response_model, content_prompt, model_name='gpt-4.1-2025-04-14', temp=0.7):
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    client = instructor.from_openai(client, mode=instructor.Mode.TOOLS)

    kwargs = dict(
        model=model_name,
        messages=[{"role": "user", "content": content_prompt}],
        response_model=response_model,
    )

    if model_name not in ['o3', 'o3-mini', 'o4-mini']:
        kwargs['temperature'] = temp

    try:
        return client.chat.completions.create(**kwargs)
    except Exception as exc:
        print(f"Exception with model {model_name}: {exc}")
        raise


# =============================================================================
# INTERVIEW
# =============================================================================

class UserAnswer(BaseModel):
    question: str
    answer: str

class InterviewTurn(BaseModel):
    interviewer_utterance: str = Field(
        ...,
        description=(
            "The interviewer's utterance, containing acknowledgment of the "
            "previous answer and a relevant follow-up question."
        ),
    )
    rationale: Optional[str] = Field(
        None,
        description="Short rationale explaining why this utterance is appropriate given the context.",
    )

INTERVIEW_OPENING_QUESTION = (
    "In this interview, we're talking about meat-eating. "
    "What's the first thing that comes to your mind?"
)

def _build_target_list() -> str:
    return "\n".join(f"- {item['template'].replace('[SCALE]', 'agree')}" for item in DYNAMIC_ITEMS)


def generate_conversational_question(history: List[UserAnswer], n_rounds=8) -> InterviewTurn:
    conversation_str = ""
    for turn in history:
        conversation_str += f"Interviewer: {turn.question}\nParticipant: {turn.answer}\n\n"

    current_round = len(history) + 1

    penultimate_turn = n_rounds - 1

    system_prompt = f"""
You are a thoughtful, empathetic, and curious interviewer. Your job is to have a
genuine conversation about meat-eating — not to conduct a structured survey.

Current conversation:
{conversation_str}

=*=*=

Your purpose:
Help the participant surface what is genuinely salient to them about meat-eating.
You are not trying to ensure every topic gets covered. What comes up naturally is
the data. What does not come up is also the data.

What you want to learn about, broadly:
- Their habits and how they came about
- Anything that shapes how they think or feel about meat — enjoyment, health,
  ethics, convenience, identity, social pressure, concerns, values, or anything else
- Their social context — what people around them do and think

=*=*=

Internal reference — do not surface these directly:
The following are specific topics we are interested in. Never ask about them directly
or paraphrase them as questions. Use this list only to check, at the end of the
conversation, whether whole areas have had no opportunity to surface.

{_build_target_list()}

=*=*=

How to generate your next question:

Scan the FULL conversation before deciding.

PHASE 1 — turns 1 to {penultimate_turn} (you are on turn {current_round}):

  Priority 1: Find something the participant mentioned but that was never followed up.
  Look for their own words, asides, or passing remarks — especially anything vague or
  emotionally loaded ("I've been thinking about it", "some ethical ideas", "I indulge
  sometimes"). These are the best hooks: they follow the participant's language, feel
  natural, and surface what is genuinely there.
  Do NOT convert these into domain names. If they said "indulge", ask about that word.
  Do not turn it into a question about "taste" or "enjoyment".

  Priority 2: If stuck on the same narrow thread for two turns, open space broadly.
  Do not name a new topic. Instead ask something that invites anything:
  "What else comes to mind when you think about this?" or
  "Is there anything else that shapes how you feel about it?"
  This creates opportunity without steering toward a specific domain.

  Priority 3: Only if the conversation has genuinely stalled with nothing unresolved —
  use one of the broad questions below to open a new area. These are last resort only.
  - "Does any of this connect to how you think about health?"
  - "Does it connect to values or things you care about more broadly?"
  - "What do the people close to you tend to think about it?"

PHASE 2 — turn {penultimate_turn} onward:

  Check the internal reference above. If whole broad areas have had no opportunity to
  surface at all, you may ask one open question to create space — without naming the
  specific topic. Frame it as an invitation, not a probe.

  On the final turn ({n_rounds}), always close with:
  "Is there anything else — whether practical, personal, ethical, or just something
  that matters to you — that shapes how you think about meat that we haven't touched on?"

=*=*=

Guidelines:
1) Acknowledge the participant's last answer briefly to show you are listening.
2) Be curious, warm, and non-judgmental.
3) One focused open question per turn — no multi-part questions, no leading phrasing.
4) Keep it concise: ~1 sentence acknowledgment, then 1 clear question.
5) No moralizing, advice, assumptions, checklists, or multiple-choice framing.
6) If the participant explicitly refuses to answer, move on without pressing.

Conversation constraints:
- You have {n_rounds} total turns; this is round {current_round} of {n_rounds}.

Generate the next interviewer question.
    """

    return call_openai(
        response_model=InterviewTurn,
        content_prompt=system_prompt,
        model_name='gpt-4.1-2025-04-14',
        temp=0.7,
    )


# =============================================================================
# CLOSED-STANCE NODE DETECTION
# =============================================================================

class StanceScore(BaseModel):
    stance_id: str
    likert: int
    evidence: str

class StanceDetectionResult(BaseModel):
    detected: List[StanceScore]


def _build_stance_block() -> str:
    lines = []
    for item in DYNAMIC_ITEMS:
        meta = STANCE_LOOKUP.get(item["id"], {})
        statement = meta.get("statement") or item["template"].replace("[SCALE]", "agree")
        codebook = meta.get("codebook", "")
        lines.append(f'[{item["id"]}] "{statement}"')
        if codebook:
            lines.append(f'  Guidance: {codebook}')
        lines.append("")
    return "\n".join(lines)

STANCE_BLOCK = _build_stance_block()

NODE_PROMPT_TEMPLATE = """\
You are a social scientist analysing interview transcripts about meat-eating habits.

You are given an interview transcript and a fixed list of predefined stances, \
each with coding guidance that describes what counts as evidence and how to \
calibrate the rating scale.

Your task:
1. Identify which stances are clearly evidenced in the transcript.
2. For each evidenced stance, assign a Likert score from 1 to 7 based on how \
strongly the participant agrees or disagrees with that statement.
3. Omit any stance for which there is no evidence in the transcript.

Agreement scale (6-point, no midpoint):
  1 = strongly disagree
  2 = disagree
  3 = somewhat disagree
  4 = somewhat agree
  5 = agree
  6 = strongly agree

Important:
- Score what the participant expresses, not whether they mentioned the topic. \
If they say "I rarely eat meat", score "I eat meat on most days" as 1–2 rather \
than omitting it.
- A low score (1–3) should only be assigned when the participant actively \
expresses disagreement or the opposite position — not simply because the topic \
was not mentioned.
- Follow the per-stance guidance carefully, especially for stances that may overlap.

=*=*=

Predefined stances with coding guidance:

{stance_block}

=*=*=

INTERVIEW TRANSCRIPT:
{transcript}
END TRANSCRIPT

Return ONLY the JSON object. For each detected stance provide:
  stance_id  — must exactly match one of the ids above
  likert     — integer 1–6
  evidence   — one sentence quoting or paraphrasing the relevant part of the transcript
"""


def make_node_prompt(questions_answers: dict) -> str:
    transcript_str = "\n".join(
        f"Q: {q}\nA: {a}" for q, a in questions_answers.items()
    )
    return NODE_PROMPT_TEMPLATE.format(
        stance_block=STANCE_BLOCK,
        transcript=transcript_str,
    )


def detect_stances(questions_answers: dict) -> List[StanceScore]:
    """Sync stance detection via instructor — returns scored stances for the transcript."""
    prompt = make_node_prompt(questions_answers)
    result = call_openai(
        response_model=StanceDetectionResult,
        content_prompt=prompt,
        model_name='gpt-4.1-2025-04-14',
        temp=0.1,
    )
    return result.detected


def enrich_detected_stances(detected: list) -> list:
    """
    Given a list of dicts with stance_id/likert/evidence (as parsed from raw JSON
    in the async live_method), add the statement and label from STANCE_LOOKUP so
    downstream code can read the human-readable text directly.
    """
    enriched = []
    for item in detected:
        sid = item.get("stance_id", "")
        meta = STANCE_LOOKUP.get(sid, {})
        enriched.append({
            "stance_id": sid,
            "statement": meta.get("statement", sid),
            "label":     meta.get("label", sid),
            "direction": meta.get("direction", ""),
            "likert":    item.get("likert"),
            "evidence":  item.get("evidence", ""),
        })
    return enriched