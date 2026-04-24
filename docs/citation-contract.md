# Citation Contract

The product's only defensible promise: **every answer carries verifiable citations,
or the system refuses to answer.** This document formalizes that contract.

## Hard rules

1. **No retrieval, no answer.** If hybrid retrieval returns zero chunks above
   `EVG_RETRIEVAL_MIN_SCORE` (default 0.35), the LLM is never invoked. The response is:
   ```json
   { "answer": "No supporting evidence found.", "citations": [], "confidence": 0.0, "refused": true }
   ```

2. **JSON-only LLM output.** Ollama is called with `format=json`. The expected shape is:
   ```json
   {
     "answer": "<string>",
     "citations": [ { "chunk_id": "<id>", "excerpt": "<verbatim substring>" } ],
     "confidence": <float 0..1>
   }
   ```
   Anything that fails to parse → refusal.

3. **Citation IDs must be from the retrieved set.** A citation whose `chunk_id` was not
   among the chunks we passed to the LLM is dropped. (LLM cannot cite outside the evidence.)

4. **Excerpts must be verbatim substrings** of the cited chunk's text, ≥12 characters.
   Case- and whitespace-insensitive comparison; otherwise no transformation. Excerpts
   that fail this check are dropped — and if all fail, the answer is replaced with the
   refusal string.

5. **The refusal string is fixed.** Exactly `"No supporting evidence found."` — UI and
   tests pin against this constant.

## Where it lives

- `backend/app/services/answer.py::_validate` — the validator.
- `backend/app/services/answer.py::answer_with_proof` — non-streaming entrypoint.
- `backend/app/services/answer.py::stream_answer` — streaming variant; same validator
  runs after the stream completes.
- `ai/prompts/answer_with_citations.txt` — the prompt that explains all of this to the LLM.
- `tests/unit/test_citation_validator.py` — exhaustive unit tests of the validator.
- `tests/integration/test_no_hallucination.py` — empty-DB and unreachable-LLM both refuse.
- `tests/integration/test_api_endpoints.py::test_query_with_no_data_returns_refusal`.

## What this prevents

- The LLM "remembering" something not in your evidence and answering from training.
- The LLM making up source IDs.
- The LLM citing a real source but with a paraphrased / fabricated excerpt.
- The LLM returning malformed structured output that we then guess at.

## What this does NOT prevent (yet)

- A citation whose excerpt is real but whose **interpretation** in the answer is wrong.
  The contract guarantees provenance, not correctness of inference.
- The user trusting an answer that aggregates contradictory evidence into a confident
  claim. The post-MVP **Contradiction Engine** addresses this by surfacing conflicts
  before they reach the LLM.
