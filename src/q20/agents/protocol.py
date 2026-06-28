"""Natural-language prompt builders + tolerant parsers for the Judge/Player brains.

The wire between the agents is free language; the receiver privately runs an LLM in
JSON mode to turn prose into structured questions / answers / a guess. These builders
own the prompts; the parsers are *tolerant* — malformed model output decodes to a
safe default instead of raising, so a flaky local model can never crash a round.

NOTE: prompts are provisional stubs (rules still ``[TBD-confirm]``); they live behind
this single module so refining them never touches the engine.
"""

import json
import re

_JSON_RE = re.compile(r"\{.*\}|\[.*\]", re.DOTALL)


def _extract_json(text: str):
    """Pull the first JSON value out of arbitrary model text; None if hopeless."""
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    match = _JSON_RE.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except (json.JSONDecodeError, TypeError):
        return None


def ask_prompt(view: dict, n_questions: int, n_options: int) -> list[dict]:
    """Messages asking the Player to emit ``n_questions`` MCQs as a JSON array."""
    system = (
        "You are the PLAYER in a '20 Questions' association game. Using ONLY the hint and the "
        f"associative-word chain, output a JSON array of exactly {n_questions} multiple-choice "
        f"questions. Each item is {{\"text\": str, \"options\": [{n_options} short strings]}}. "
        "Output JSON only, in English, no prose."
    )
    user = f"Hint: {view.get('hint')!r}. Chain: {view.get('chain')}. Emit the JSON array now:"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def answer_prompt(spec_text: str, questions: list[dict]) -> list[dict]:
    """Messages asking the Judge to answer each MCQ with an option index."""
    system = (
        "You are the JUDGE. You secretly know the target paragraph. Answer each multiple-choice "
        "question truthfully by the index (0-based) of the best option. Output ONLY a JSON array "
        "of integers, one per question. Never reveal the paragraph."
    )
    user = f"Target (secret): {spec_text!r}\nQuestions: {json.dumps(questions)}\nEmit the index array:"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def guess_prompt(view: dict, qa: list[dict]) -> list[dict]:
    """Messages asking the Player to guess the opening sentence + associative word."""
    system = (
        "You are the PLAYER. From the hint, chain, and your answered questions, output ONLY a JSON "
        'object {"opening_sentence": str, "associative_word": str} — your final guess. English only.'
    )
    user = f"Hint: {view.get('hint')!r}. Chain: {view.get('chain')}.\nAnswered: {json.dumps(qa)}\nGuess:"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_questions(text: str, n_options: int) -> list[dict]:
    """Parse a model reply into a list of well-formed MCQ dicts (drops malformed)."""
    arr = _extract_json(text)
    out: list[dict] = []
    if not isinstance(arr, list):
        return out
    for item in arr:
        if not isinstance(item, dict):
            continue
        opts = item.get("options")
        if isinstance(opts, list) and len(opts) >= 1:
            out.append({"text": str(item.get("text", "")),
                        "options": [str(o) for o in opts[:n_options]]})
    return out


def parse_answers(text: str, count: int) -> list[int]:
    """Parse a reply into ``count`` option indices; missing/garbage default to 0."""
    arr = _extract_json(text)
    answers = arr if isinstance(arr, list) else []
    out: list[int] = []
    for i in range(count):
        val = answers[i] if i < len(answers) else 0
        out.append(int(val) if isinstance(val, (int, float)) else 0)
    return out


def parse_guess(text: str) -> dict:
    """Parse a reply into ``{opening_sentence, associative_word}`` (empty on failure)."""
    obj = _extract_json(text)
    obj = obj if isinstance(obj, dict) else {}
    return {
        "opening_sentence": str(obj.get("opening_sentence", "")),
        "associative_word": str(obj.get("associative_word", "")),
    }
