# 07. Re-ranking: how the chatbot finds the right text, from scratch

This guide explains, for someone who has never worked with AI search, how the AI concierge finds hotel information,
what was wrong with it, what **re-ranking** is, why it needs a *second, different* model (and why the embedding model
cannot simply do the job twice), how it is built in this project, and what it measurably changed.

Every number here was measured on this project's own test data. Commands to reproduce them are in
[section 11](#11-how-to-reproduce-every-number).

Contents:
[0. Summary](#0-the-60-second-version) ·
[1. What the chatbot needs](#1-what-the-chatbot-needs-from-search) ·
[2. Search before](#2-where-we-started-search-with-one-model) ·
[3. The problem](#3-the-problem-right-text-found-but-in-the-wrong-place) ·
[4. Why embeddings make these mistakes](#4-why-embedding-search-makes-these-mistakes) ·
[5. Cross-encoders](#5-the-fix-a-cross-encoder-a-model-that-reads-both-texts-together) ·
[6. Why not the same model twice?](#6-why-cant-the-embedding-model-just-do-it-twice) ·
[7. Two stages](#7-putting-it-together-retrieve-wide-re-rank-narrow) ·
[8. In the code](#8-how-it-is-built-in-this-project) ·
[9. Choosing the model](#9-choosing-the-model) ·
[10. Results](#10-results) ·
[11. Reproduce](#11-how-to-reproduce-every-number) ·
[12. Configure](#12-how-to-use-configure-or-turn-it-off) ·
[13. Limits](#13-limits-and-what-is-still-open) ·
[14. Glossary](#14-glossary-of-new-words) ·
[15. FAQ](#15-faq)

---

## 0. The 60-second version

* The chatbot answers from hotel text (policies, FAQs, room descriptions). For each question it must **find** the right
  pieces of text first, then Gemini writes the answer from them. This is called RAG.
* Finding used to be done by **one** model, an *embedding model*. It turns every text into 384 numbers in advance, and a
  question is matched to the texts whose numbers are closest. It is fast, but it judges each text **without ever seeing the
  question**, so it often ranked a merely *similar* text above the one that actually *answers* the question.
* We added a **second** model, a *cross-encoder re-ranker*. It reads the question and a candidate text **together** and
  outputs one score: "how well does this text answer this question?". It is much more accurate, but too slow to run on
  every text, so it only re-orders the 30 best candidates the embedding search already found. The best 8 go to Gemini.
* The embedding model cannot do this second job. Running it again gives identical numbers, and its design never compares
  the two texts at all (section 6).
* **Result** on the 46 labelled test questions: the right text ranked **first** went from 80% to **89%** (37 to 41
  questions). Follow-up questions went from 55% to 82% and pricing questions from 33% to 67%. No question got worse.
  Cost: about 0.2 to 0.5 seconds of CPU per question, no API calls, and an 80 MB model.
* Two follow-ups: Gemini used to see only the **first 350 characters** of each chunk, which was a bug and is now fixed (section 13).
  Sending 4 chunks instead of 8 was **tested and rejected** (section 10.3).

---

## 1. What the chatbot needs from search

A guest types: *"Does GrandStay Shibuya have an onsen? Is that okay if I have tattoos?"*

Gemini knows nothing about GrandStay hotels. It only knows what we put in its prompt. So before calling Gemini the
backend must pick, from all the stored hotel text, the few pieces that answer the question, and paste them into the
prompt. That is **RAG: retrieval-augmented generation**:

```
guest question
     │
     ▼
1. RETRIEVE: find the most relevant pieces of hotel text      ◄── this guide is about this step
     │
     ▼
2. GENERATE: Gemini writes the answer using only those pieces
```

If step 1 hands over the wrong pieces, even a perfect LLM answers badly ("I don't have information about tattoos")
or, worse, answers from a different hotel's text. **Retrieval quality limits answer quality.**

**Chunks.** Hotel text is stored in small pieces called *chunks* (about 500 characters each) in the table
`hotel_document_chunks`. Uploaded documents are split into chunks, and structured data (each policy, each room type,
the amenity list, the reviews) is turned into chunks by `sync_hotel_database_knowledge`. A chunk can hold several facts.
For example, the Shibuya FAQ chunk is:

> The rooftop onsen is open from 6:00 AM to 11:00 PM. Guests with visible tattoos are welcome in the private family
> baths. Breakfast is served from 6:30 AM to 10:00 AM and costs $30 per person. The Narita Express and airport limousine
> bus both stop within five minutes of the hotel.

---

## 2. Where we started: search with one model

### 2.1 Embeddings: text turned into numbers

An **embedding model** reads a text and outputs a fixed-length list of numbers (a *vector*) that captures its meaning.
Ours is `BAAI/bge-small-en-v1.5` (33 million parameters, outputs **384 numbers**), run locally by the *fastembed* library.
Code: `app/services/embedding_service.py`.

The model was trained so that texts with similar meaning get similar vectors. Picture each vector as an arrow in space.
"Breakfast is served at 7" and "What time is breakfast?" point in nearly the same direction, while "The pool closes at 9"
points elsewhere.

**Cosine similarity** measures how closely two arrows point the same way. It gives 1.0 for the same direction, around 0
for unrelated, and negative for opposite. That number is the `similarity_score` you see in search results.

### 2.2 The search, step by step (before)

```
UPLOAD TIME (once per chunk)                      QUESTION TIME (every message)
─────────────────────────────                     ──────────────────────────────
chunk text ──► embedding model ──► 384 numbers    question ──► embedding model ──► 384 numbers
                                       │                                               │
                                       ▼                                               ▼
                         stored in PostgreSQL (pgvector)  ──── compare with every stored vector (cosine)
                                                                               │
                                                                               ▼
                                                          the 8 closest chunks ──► Gemini prompt
```

The key property: **chunk vectors are computed once, when the chunk is saved**. At question time only the question is
embedded (about 17 ms here), and the database compares numbers, which is very fast even for many chunks.
Code: `document_service.search_chunks` (now `_vector_search`), using pgvector's `cosine_distance`.

Two earlier improvements also feed this step (see `03-every-change.md`):
* **A1.** Follow-ups like "What time does it open?" are searched together with the guest's previous message
  (`chat_service.build_retrieval_query`).
* **A2.** The number of chunks sent to Gemini was raised from 4 to 8, because a needed FAQ chunk was sitting at
  ranks 5 to 8.

---

## 3. The problem: right text found, but in the wrong place

The project has a labelled test set: 46 questions where we know which chunk holds the answer (`evals/datasets/golden.jsonl`).
The metrics (all computed with no AI involved, `evals/retrieval_metrics.py`) are:

* **hit@8**: is the right chunk anywhere in the 8 we send? Before: **1.00**, so always.
* **hit@1**: is the right chunk ranked **first**? Before: **0.80**, so 9 of 46 questions had something else on top.
* **MRR** (mean reciprocal rank): 1 if the right chunk is 1st, 1/2 if 2nd, 1/3 if 3rd, and so on, averaged. Before: **0.87**.

By category, hit@1 before re-ranking:

| category | questions | hit@1 | MRR |
|---|---|---|---|
| policy | 13 | 1.00 | 1.00 |
| faq | 10 | 1.00 | 1.00 |
| refund | 3 | 1.00 | 1.00 |
| discovery ("which hotel has...") | 6 | 0.67 | 0.76 |
| **follow-up** | 11 | **0.55** | 0.71 |
| **pricing** | 3 | **0.33** | 0.61 |

**Why does the rank matter if all 8 chunks are sent anyway?**
1. **Only the top k get in at all.** Anything at rank 9 or lower is invisible to Gemini. We raised k from 4 to 8 (A2) only
   because rankings were unreliable, and that costs about 350 extra prompt tokens on every message.
2. **Noise competes with the answer.** When the top of the list is a wrong-but-similar chunk (another hotel's onsen, a pet
   policy for a price question), the model has more chances to use the wrong one. LLMs are also known to pay less
   attention to material in the middle of a long context.
3. **Citations** shown to the guest are ordered by these scores.

A real example from the test set, `fu-onsen-tattoo` (search query: *"Does GrandStay Shibuya have an onsen? Is that okay
if I have tattoos?"*). With embeddings only, the top 3 were:

| rank | cosine | chunk |
|---|---|---|
| 1 | 0.706 | "Hotel Amenities for GrandStay Shibuya: Available amenities: Rooftop Onsen, Sushi..." |
| 2 | 0.696 | "Verified Guest Reviews & Ratings for GrandStay Shibuya..." |
| 3 | 0.668 | "Hotel Profile: GrandStay Shibuya, Location: 2-21-1 Shibuya, Tokyo..." |
| **8** | **0.632** | **"The rooftop onsen is open... Guests with visible tattoos are welcome in the private family baths."** |

The only chunk that answers the tattoo question came **last of 8**. The chunks above it are all "about Shibuya" and
"about an onsen", but none says anything about tattoos.

---

## 4. Why embedding search makes these mistakes

This kind of model is called a **bi-encoder** ("two encoders"): the question and the chunk are encoded **separately**,
and only the two finished vectors are compared.

```
"Is that okay if I have tattoos?" ──► [model] ──► 384 numbers ─┐
                                                               ├──► cosine ──► 0.632
"The rooftop onsen is open ...    ──► [model] ──► 384 numbers ─┘
 tattoos are welcome in ..."
            the two texts never meet inside the model
```

Three consequences:

1. **The chunk is summarised before the question exists.** Everything a chunk says (onsen hours, tattoos, breakfast,
   trains) is squeezed into 384 numbers at upload time. The model cannot know which of those facts a future question
   will care about, so it keeps a blurry "average topic": *Shibuya, onsen, times, food*. A question about one detail
   matches that blur only partly.
2. **Topic similarity is not the same as answering.** The amenities list says "Rooftop Onsen" plainly, so its topic is
   very close to the question's. But it does not answer "is it okay with tattoos?". Cosine measures closeness of topic,
   not whether one text answers the other.
3. **Small words that change everything are weak signals.** A small demonstration with our embedding model (question:
   *"What time is breakfast?"*):

   | candidate | cosine (embedding) |
   |---|---|
   | Breakfast is served from 7:00 to 10:30 in the Garden Room. | 0.761 |
   | **Check-in time is 3pm and check-out time is 11am.** | **0.709** (2nd!) |
   | Breakfast, lunch, dinner and room service menus are available on request. | 0.624 |
   | We do not serve breakfast; guests may dine at nearby cafes. | 0.532 |

   The check-in sentence is nearly as "close" as the real answer because it shares the shape *"... time is ..."*.

None of this is a bug in our code. It is the price of the design that makes embedding search fast (section 6.4).

---

## 5. The fix: a cross-encoder, a model that reads both texts together

### 5.1 What it is

A **cross-encoder** takes the question and one chunk **as a single input** and outputs **one number**, a relevance score:

```
[CLS] What time is breakfast? [SEP] Breakfast is served from 7:00 to 10:30 ... [SEP]
                                   │
                                   ▼
                         one transformer pass
                                   │
                                   ▼
                       one number: 6.06  ("very relevant")
```

### 5.2 Why reading together is so much better (a little about transformers)

Both kinds of model are **transformers**. A transformer splits text into *tokens* (word pieces) and, layer after layer,
lets every token look at every other token in its input and update itself based on what it sees. This mechanism is
called **attention**.

* In the **bi-encoder**, the input is only the question, or only the chunk. The token "tattoos" in the question can
  only look at other question tokens.
* In the **cross-encoder**, the input is both. The question's "tattoos" can attend directly to the chunk's "Guests with
  visible tattoos are welcome", and "okay" can attend to "welcome". The model sees the actual match, word against word,
  before deciding anything.

### 5.3 How it learned "relevance"

Our re-ranker was trained on **MS MARCO**, a Microsoft dataset of real Bing search questions where people marked which
web passages answer each question (hundreds of thousands of questions). It was trained as a judge: given (question,
passage), output a high number if the passage answers the question and a low one if not. That is exactly the job we need,
and it is a different job from what the embedding model was trained for (making similar texts land near each other).

### 5.4 The same demonstration, with the cross-encoder

The raw output is a **logit**, an unbounded score where positive means relevant and negative means not. We convert it
to 0..1 with the **sigmoid** function: 0 becomes 0.5, +6 becomes 0.998, and -7 becomes 0.001.

Question *"What time is breakfast?"*:

| candidate | cosine (embedding) | cross-encoder logit | score 0..1 |
|---|---|---|---|
| Breakfast is served from 7:00 to 10:30 in the Garden Room. | 0.761 | +6.06 | **0.998** |
| Check-in time is 3pm and check-out time is 11am. | 0.709 | -2.33 | 0.088 |
| Breakfast, lunch, dinner and room service menus are available on request. | 0.624 | -7.02 | 0.001 |
| We do not serve breakfast; guests may dine at nearby cafes. | 0.532 | -6.85 | 0.001 |

The gap between the right answer and the check-in sentence went from 0.05 (cosine) to 0.91. The cross-encoder is not
"a bit better at similarity". It measures a different thing.

**It is not magic either.** Question *"Are pets allowed?"*:

| candidate | cosine | cross-encoder score |
|---|---|---|
| Pets are allowed in all rooms. | 0.741 | 1.000 |
| Pets are not allowed anywhere in the hotel. | 0.713 | 0.999 |
| Our pet-friendly policy welcomes dogs under 10 kg for a $30 fee. | 0.651 | **0.051** |
| The pool is open from 7am to 9pm. | 0.467 | 0.000 |

* "Pets are not allowed" scoring 0.999 is **correct**. Relevance means "this text answers the question", and "no" is an
  answer. Deciding yes or no is Gemini's job.
* The pet-friendly sentence scoring 0.051 is a **real miss**. The model did not connect "pets allowed" with "welcomes
  dogs". Similarly, "We do not serve breakfast" above got only 0.001, although it does answer the question.

This is one reason we still send **8** chunks to Gemini rather than only the top 1, and why the decision to keep
re-ranking rests on the measured test set (section 10), not on hand-picked examples.

---

## 6. "Why can't the embedding model just do it twice?"

This is the most natural question, so here it is from every angle.

### 6.1 Running it again gives exactly the same numbers

A model is a fixed mathematical function. The same text gives the same vector every time. We checked:
`get_embedding("What time is breakfast?") == get_embedding("What time is breakfast?")` is `True`. Same vectors, same
cosine, same order. A second pass re-ranks nothing.

### 6.2 Running it on a smaller pool changes nothing either

"First search everything, then search again only among the top 30" sounds like a refinement, but the cosine between the
question and a chunk depends **only on those two vectors**. It does not care what other chunks are in the pool. The 30
survivors keep their scores and their order.

### 6.3 Feeding it "question + chunk" together does not work

You could paste the question and chunk into one string and embed it. You would get one vector describing the mixture,
**but there is nothing to compare that vector with**, and the model was never trained to output "how well does part B
answer part A". To get that number you need a model *trained to produce that number*, and that model is a
cross-encoder. That is what we added.

### 6.4 Then why not use the cross-encoder for everything and drop embeddings?

Because the cross-encoder's input includes the question, **nothing can be computed in advance**. For each question it
must run a full transformer pass on every (question, chunk) pair:

| | embedding search (bi-encoder) | cross-encoder |
|---|---|---|
| work at upload time | embed each chunk once, store it | nothing (cannot precompute) |
| work per question | embed the question once (~17 ms) + fast number comparisons in the database | one model pass **per chunk** (~10 ms each on this laptop) |
| 31 chunks (test database) | ~20 ms | ~0.3 s |
| 1,000 chunks (e.g. 50 uploaded PDFs) | ~20 ms + database | **~10 s** |
| 10,000 chunks (several hotels) | ~20 ms + database | **~100 s** |
| accuracy | good at "same topic" | good at "answers the question" |

So each model does what it is good at. The **fast, approximate** one narrows thousands of chunks to 30, and the
**slow, precise** one orders those 30. This is the standard design in search engines, often described as
"retrieve, then re-rank".

### 6.5 What about a bigger, better embedding model?

A larger embedding model would help somewhat, but it keeps the same structural limit. The chunk is still summarised
before the question exists, and the question still never meets the chunk inside the model. It would also mean
re-embedding every stored chunk. It is not ruled out (the two ideas combine), but it does not replace re-ranking.

### 6.6 What about the "keyword re-ranking" we rejected before?

Experiment #4 in `evals/baselines/EXPERIMENTS.md` re-scored results as `0.7 × cosine + 0.3 × keyword overlap` (share of
question words found in the chunk). It made things **worse** (hit 0.98 → 0.94). Word overlap is a crude rule: it counts
"is", "the" and "time" as matches and knows nothing about meaning. The cross-encoder learned relevance from data, and it
made things better (section 10). Both are called "re-ranking", but they are very different.

### 6.7 What about asking Gemini to re-rank?

An LLM can also judge relevance, but that would add one more Gemini request per message (on a free tier of 15 requests
per minute), thousands of extra tokens (30 chunks to read) and seconds of delay. It was rejected for the same reason as
the LLM query rewrite (experiment #3). It was **not measured**. The local cross-encoder costs no quota.

---

## 7. Putting it together: retrieve wide, re-rank narrow

```
guest message
   │  build_retrieval_query (adds the previous message for short follow-ups)
   ▼
search query
   │
   ▼
STAGE 1  embedding search (bge-small-en-v1.5, pgvector)             fast, approximate
   │     returns the 30 most similar chunks (RERANK_CANDIDATES)
   ▼
STAGE 2  cross-encoder (ms-marco-MiniLM-L-6-v2)                      slow, precise
   │     scores each of the 30 (question, chunk) pairs, sorts, keeps the best 8
   ▼
8 chunks ──► Gemini prompt + citations
```

The same example, `fu-onsen-tattoo`, after stage 2:

| new rank | re-rank score | (old cosine) | chunk |
|---|---|---|---|
| **1** | **0.949** | (0.632, was 8th) | "The rooftop onsen is open... **tattoos are welcome** in the private family baths." |
| 2 | 0.085 | (0.706, was 1st) | "Hotel Amenities for GrandStay Shibuya: Rooftop Onsen..." |
| 3 | 0.075 | (0.668, was 3rd) | "Hotel Profile: GrandStay Shibuya..." |

---

## 8. How it is built in this project

### 8.1 Files

| file | role |
|---|---|
| `app/services/rerank_service.py` (**NEW**) | loads the cross-encoder, scores and sorts candidates, falls back safely |
| `app/services/document_service.py` (CHANGED) | `search_chunks` = stage 1 (`_vector_search`) + stage 2 (`rerank_service.rerank`) |
| `app/core/config.py` (CHANGED) | `RERANK_ENABLED`, `RERANK_MODEL`, `RERANK_CANDIDATES` |
| `app/services/chat_service.py` (CHANGED) | citations and Phoenix traces show the re-rank score |
| `app/schemas/document.py` (CHANGED) | search results carry an optional `rerank_score` |
| `.env.example` (CHANGED) | documents the three settings |
| `tests/test_rerank.py` (**NEW**) | 9 tests (section 11) |
| `evals/retrieval_variants.py` (CHANGED) | `--rerank` compares models and pool sizes |
| `evals/test_retrieval.py`, `evals/baselines/retrieval.json` (CHANGED) | the regression gate now includes hit@1 and the new baseline |

### 8.2 One question, line by line

1. `chat_service.send_chat_message` builds the search query and calls `build_knowledge_base_context(..., top_k=8)`.
2. That calls `document_service.search_chunks(db, query, hotel_id, top_k=8)`.
3. `search_chunks` checks `settings.RERANK_ENABLED` (or the `rerank=` argument, which evals use to compare both ways):
   ```python
   candidates = _vector_search(db, query, hotel_id, max(top_k, settings.RERANK_CANDIDATES), access_level)
   return rerank_service.rerank(query, candidates, top_k)
   ```
   `_vector_search` is the old search, unchanged. The same hotel and access filters apply, so re-ranking can never
   surface a chunk the user was not allowed to see. It also works on the Python fallback path used when pgvector is missing.
4. `rerank_service.rerank`:
   * builds what the model reads for each chunk: **hotel name + title + text**, e.g.
     `"GrandStay Shibuya - GrandStay Shibuya FAQ\nThe rooftop onsen is open..."`. The title often names the topic when
     the text does not.
   * calls `model.rerank(query, passages, batch_size=32)` → one logit per chunk
   * stores `rerank_score = sigmoid(logit)` (0..1) on each chunk and **keeps** the original `similarity_score`
   * sorts by `rerank_score` and returns the best `top_k`
5. Back in `chat_service`, the 8 chunks go into the prompt. Each citation's `relevance_score` is the re-rank score, and
   the Phoenix trace records both scores (`vector=0.632 rerank=0.949`).

### 8.3 Loading the model

* **Lazy:** the model loads on the first search, not at app start. The first time ever, fastembed downloads it
  (~80 MB) from Hugging Face into `FASTEMBED_CACHE_PATH`. In Docker that is the `fastembed_cache` volume the
  embedding model already uses, so it survives restarts. Later starts load from disk in about a second.
* **Thread-safe:** FastAPI runs requests in parallel threads, so a lock ensures the model is loaded once.
* **ONNX:** fastembed runs models in the ONNX format through *onnxruntime*, which is a lightweight CPU engine. No PyTorch and no
  GPU are needed. That is why no new package was added: fastembed was already installed for embeddings.

### 8.4 Failing safely

The chatbot must keep working even if re-ranking cannot. In each case below, search returns the stage-1 order (cut to
`top_k`) and logs the error:

| situation | what happens |
|---|---|
| model cannot be downloaded (no internet) or fails to load | logged once; that model is not retried on every request |
| model raises an error while scoring | logged; this request uses the vector order |
| `RERANK_ENABLED=false` | stage 2 skipped entirely, exactly the old behaviour |

---

## 9. Choosing the model

fastembed supports several re-rankers. Four were compared on the same 46 questions (production search query, top 8,
pool of 30):

| model | size | hit@1 | MRR | time per question* |
|---|---|---|---|---|
| none (embeddings only) | n/a | 0.80 | 0.87 | ~50 ms |
| **`Xenova/ms-marco-MiniLM-L-6-v2`** (chosen) | 80 MB | **0.89** | **0.94** | ~200-600 ms |
| `Xenova/ms-marco-MiniLM-L-12-v2` | 120 MB | 0.89 | 0.94 | ~1,100 ms |
| `jinaai/jina-reranker-v1-turbo-en` | 150 MB | 0.91 | 0.94 | ~720 ms |
| `BAAI/bge-reranker-base` | 1 GB | 0.91 | 0.95 | ~2,600 ms |

\* On this Windows laptop's CPU, including stage 1. Times vary by ±50% run to run, depending on what else is running.

**Why the smallest one:** the larger models win by **one question out of 46**, which is within noise for a set this
small, while costing 1.2 to 4 times the time (and 1 GB of disk for bge). If a bigger test set later shows a real gap,
switching is one setting (section 12).

**About the chosen model:**
* *MiniLM-L-6* is a small transformer: **6 layers**, about 22 million parameters. "L-12" has 12 layers.
* *ms-marco* is the training data (section 5.3).
* *Xenova* is the Hugging Face account that publishes the ONNX conversion of the original
  `cross-encoder/ms-marco-MiniLM-L-6-v2` (from the sentence-transformers project).
* It is **English-only** and reads at most 512 tokens per (question + chunk) pair. Our chunks are ~500 characters (~120
  tokens), well within that.

**Pool size (`RERANK_CANDIDATES`):** 15, 30 and 50 gave identical quality, because each test hotel has only about 17
chunks, so every pool already contains all of them. Cost grows linearly (~10 ms per candidate on this laptop). 30 was
kept as the default at first. **Update:** on the real database (205 chunks, longer documents; `08-real-database.md`) 20 and 30 scored the same, and capping what the re-ranker reads at 600 characters raised hit@1 from 0.87 to 0.90 while halving the time, so the defaults are now 20 candidates and `RERANK_MAX_CHARS` = 600.

---

## 10. Results

### 10.1 By category (46 labelled questions, top 8)

| category | n | hit@1 before → after | MRR before → after |
|---|---|---|---|
| policy | 13 | 1.00 → 1.00 | 1.00 → 1.00 |
| faq | 10 | 1.00 → 1.00 | 1.00 → 1.00 |
| refund | 3 | 1.00 → 1.00 | 1.00 → 1.00 |
| discovery | 6 | 0.67 → 0.67 | 0.76 → **0.81** |
| follow-up | 11 | 0.55 → **0.82** | 0.71 → **0.91** |
| pricing | 3 | 0.33 → **0.67** | 0.61 → **0.83** |
| **overall** | 46 | **0.80 → 0.89** | **0.87 → 0.94** |

hit@8 and recall stay 1.00. Re-ranking only reorders what stage 1 found, so it can never lose a chunk that was in
the top 8 before unless it pushes it below 8, and that did not happen once. **6 questions changed rank, all for the
better, and none got worse.**

### 10.2 The six changed questions

| question (search query) | right chunk's rank before → after |
|---|---|
| `fu-onsen-tattoo`: "...Shibuya have an onsen? Is that okay if I have tattoos?" | 8 → **1** |
| `fu-spa-hours`: "Which hotel has a spa? What time does it open?" | 3 → **1** (before, the **Shibuya** onsen was 1st, the wrong hotel) |
| `fu-transfer-cost`: "Can I get a ride from Heathrow...? How much does that cost?" | 3 → **1** (before, the cancellation and smoking policies were on top) |
| `price-mayfair-rooms`: "How much are your rooms per night?" | 3 → **1** (before, the **pet policy** was 2nd) |
| `disc-pets`: "Which of your hotels allow dogs?" | 3 → 2 |
| `disc-spa`: "Which hotel has a spa?" | 4 → 3 (still not first: the hotel profile was put on top) |

In three of these, the winning chunk *starts* with "Breakfast is served...". It is the Mayfair FAQ chunk, which also
contains the Heathrow transfer and spa hours. That is a good illustration of section 4: its embedding is a blurry
average of three topics, while the cross-encoder reads the whole text against the question and finds the matching
sentence.

### 10.3 A bonus finding: fewer chunks may now be enough

The same measurement at different depths (free, no LLM):

| chunks sent | hit, embeddings only | hit, with re-ranking |
|---|---|---|
| 3 | 0.96 | **1.00** |
| 4 | 0.98 | **1.00** |
| 8 | 1.00 | 1.00 |

With re-ranking, every labelled answer is already in the **top 3**, so we tested sending fewer chunks on live Gemini
(the 46 knowledge-base questions, re-ranking on, whole chunks):

| chunks sent | exact checks | tokens per question |
|---|---|---|
| 8 (current) | 46/46 | 3,683 |
| 4 | 46/46 | 3,494 (-5%) |

**Decision: keep 8.** Four chunks were enough for every *test* question, but the test world has only 3 hotels. The
app database has **10 hotels** and 16 pet-policy chunks. A question like "Which hotels allow dogs?" needs one chunk
*per hotel*: with 4 chunks Gemini could see at most 4 hotels' policies, and it would answer confidently while leaving the
rest out. A 5% token saving is not worth that. The tests cannot show this risk, which is why it is written down here
(and as experiment #12 in `EXPERIMENTS.md`).

The lesson: *a metric only covers what the test data contains.* "All 46 passed" did not cover "more hotels than chunks".

### 10.4 Cost

* **Time:** stage 2 adds ~10 ms per candidate on this laptop, so about 0.2 to 0.5 s per question with ~17 candidates per hotel.
  For comparison, a Gemini reply takes 2.5 to 6.5 s.
* **Money/quota:** none. Runs locally.
* **Memory/disk:** ~80 MB model file plus roughly the same in RAM once loaded.
* **First request after a fresh deploy:** waits for the one-time download.

---

## 11. How to reproduce every number

All free (no Gemini, no judge). Docker's database must be running (`docker compose up -d db`), and, as always, never run
two of these at the same time (they share the test database).

```powershell
# the comparison table of section 9 (downloads each model once, ~1.4 GB in total)
python -m evals.retrieval_variants --rerank

# the per-category report of section 10.1 + the regression gate
python -m pytest evals/test_retrieval.py -s

# the same with re-ranking switched off (the "before" numbers)
$env:RERANK_ENABLED="false"; python -m pytest evals/test_retrieval.py -s; Remove-Item Env:RERANK_ENABLED
# (two gate tests fail in this mode, as they should: they compare against the re-ranked baseline; the report is what you want)

# the unit tests
python -m pytest tests/test_rerank.py -v
```

**What the tests check** (`tests/test_rerank.py`, a fake model is used, so no download is needed):
* chunks are reordered by the cross-encoder score, not the vector score, and cut to `top_k`
* the original `similarity_score` is kept and `rerank_score` is between 0 and 1
* the model reads hotel name + title + text
* if the model fails to load or crashes, the vector order is returned
* empty question or no candidates does not call the model
* `search_chunks` fetches the wide pool (30) and returns `top_k`; with `rerank=False` the model is never called
* one test with the real model: "When is breakfast served?" ranks the breakfast chunk above the pool chunk (skipped if
  the model cannot be downloaded)

**Regression gate** (`evals/test_retrieval.py`): overall hit, **hit@1**, MRR and recall must stay within 0.03 of
`evals/baselines/retrieval.json` (now the re-ranked numbers), and overall hit@1 must be at least 0.85. If someone
disables or breaks re-ranking, this fails.

---

## 12. How to use, configure or turn it off

It is **on by default**. Settings (in `.env`, read at app start):

| setting | default | meaning |
|---|---|---|
| `RERANK_ENABLED` | `true` | `false` = embeddings only, exactly the old behaviour |
| `RERANK_MODEL` | `Xenova/ms-marco-MiniLM-L-6-v2` | any re-ranker fastembed supports (list them with the snippet below) |
| `RERANK_CANDIDATES` | `20` | how many chunks stage 1 hands to stage 2. Higher means a better chance of including the answer, but slower |
| `RERANK_MAX_CHARS` | `600` | how much of each chunk the re-ranker reads (title first). Long chunks otherwise pad the whole batch and slow it down; on the real database 600 was faster **and** more accurate than no cap |

```powershell
# which re-rankers can be used
python -c "from fastembed.rerank.cross_encoder import TextCrossEncoder as T; [print(m['model'], m['size_in_GB'], 'GB') for m in T.list_supported_models()]"
```

**After changing code or settings in Docker:** rebuild and restart the app, `docker compose up -d --build`. The first chat
afterwards downloads the model if the cache volume does not have it yet.

**Seeing it work:**
* `POST /hotels/{hotel_id}/documents/search` returns both `similarity_score` and `rerank_score` for each chunk.
* In Phoenix, the `knowledge_retrieval` span lists each chunk with `vector=... rerank=...`.
* In the app log, a line `Re-ranker ... could not be loaded; using vector order` means stage 2 is being skipped.

**Switching model safely:** change `RERANK_MODEL`, run `python -m evals.retrieval_variants --rerank` and
`python -m pytest evals/test_retrieval.py` and keep it only if the numbers are at least as good. If the new model is
genuinely better, save its numbers as the new baseline (`python -m evals.save_baseline retrieval`), and add a row to
`evals/baselines/EXPERIMENTS.md`.

---

## 13. Limits, and what is still open

* **Gemini's answers: measured once, on the 46 knowledge-base questions only.** With re-ranking and whole chunks:
  46/46 exact checks (they also passed before re-ranking, so this shows *no harm*. The benefit shows in the ranking
  metrics, not in these pass/fail checks). One run is a sample, because the model is random. Not yet run: the full
  89-question set and `--repeat 3` (`python -m evals.runner --repeat 3`).
* **The test set is small** (46 labelled questions, 3 hotels, 31 chunks). One question is ~2 percentage points. Model
  differences of one question (section 9) are noise.
* **Pool size is untested at scale.** With ~17 chunks per hotel, every pool held everything. With hotels that upload many
  documents, the right chunk could rank below 30 in stage 1, and then no re-ranker can rescue it. Re-measure with real
  documents before trusting the default.
* **Fewer chunks (10.3) was tested and rejected** for cross-hotel questions. To revisit, first add a seed world with
  more hotels than chunks sent, and a test question that needs all of them.
* **English only.** For guests writing in other languages, a multilingual re-ranker exists
  (`jinaai/jina-reranker-v2-base-multilingual`, 1.1 GB). The embedding model is English too.
* **It can misjudge** (section 5.4: "welcomes dogs" for "pets allowed"). Stage 1 still hands over several chunks and
  Gemini sees all 8. That redundancy is deliberate.
* **CPU cost scales with the pool.** On a busy server, many simultaneous chats compete for CPU. If that ever matters, lower
  `RERANK_CANDIDATES` (15 lost nothing on the test set).
* **Fixed, found while writing this guide: Gemini saw only the first 350 characters of each chunk.**
  `build_knowledge_base_context` cut every chunk at 350 characters, although chunks are built to ~500 (up to ~560 with
  overlap) and chunks synced from the database are not split at all. Measured on the app database: 36 of 46
  uploaded-document chunks were cut (20% of their text never reached Gemini), 12 policies (one is 1,181 characters), and
  all 10 review chunks (67% of review text lost). Re-ranking made it worse, because the re-ranker reads the **whole**
  chunk and could pick it for a sentence Gemini was then not shown. The test database has no chunk over 350 characters,
  so no evaluation could notice. Now the whole chunk is sent (line breaks flattened to spaces), and the citation preview
  stays 200 characters. Proven by `tests/test_chat_context.py::test_the_whole_chunk_reaches_the_prompt_not_just_its_start`,
  which uses a 500+ character chunk, since the seed data has none.

---

## 14. Glossary of new words

**Bi-encoder.** A model that encodes each text separately into a vector, and texts are compared by vector closeness. Our
embedding model. Fast because the stored texts' vectors are computed in advance.

**Cross-encoder.** A model that reads two texts together in one pass and outputs one score for the pair. Accurate, but
nothing can be precomputed. Our re-ranker.

**Re-ranking.** Re-ordering a list of search candidates with a second, more careful scorer. "Two-stage retrieval" and
"retrieve, then re-rank" mean the same design.

**Candidate pool.** The chunks stage 1 hands to stage 2 (`RERANK_CANDIDATES`, 30).

**Transformer, token, attention.** A transformer is the kind of neural network both models are. Tokens are the word pieces
it reads. Attention is the mechanism that lets each token look at others in the same input, and it is the reason reading
two texts together beats reading them apart.

**Logit / sigmoid.** A logit is a raw unbounded score (positive means yes, negative means no). The sigmoid squashes it into
0..1: `1 / (1 + e^-x)`.

**MS MARCO.** A large Microsoft dataset of real search questions with human-marked relevant passages, used to train
our re-ranker.

**ONNX / onnxruntime.** A portable file format for trained models and a small engine that runs them on CPU without
PyTorch. fastembed uses it for both models.

**hit@1, MRR.** See section 3 and `05-concepts.md`.

---

## 15. FAQ

**Does re-ranking find chunks that search missed?** No. It only reorders the pool from stage 1. Finding is stage 1's job,
and ordering is stage 2's job. That is why the pool is wider (30) than what is sent (8).

**Why is the re-rank score so extreme (0.95 vs 0.08) when cosines are all ~0.6-0.7?** They measure different things on
different scales. Cosines of related texts cluster together, while a cross-encoder is trained to separate "answers"
from "does not answer" decisively. Compare scores within one method only, never across them.

**Can I compare `rerank_score` between two different questions?** Only roughly. It is meant for ordering chunks for
*one* question. It is not a calibrated probability, although very low scores (< 0.05) usually mean "not about this".

**Could we drop chunks below some re-rank score instead of always sending 8?** Possibly, and it would save tokens, but
section 5.4 shows the model sometimes scores a real answer low. That would need its own measurement.

**Does it slow down document uploads?** No. Uploads only compute embeddings, as before. The re-ranker runs only at
question time.

**What if the server has no internet?** The re-ranker cannot download, the failure is logged, and search falls back to
the old order. To run offline, copy a filled `fastembed_cache` folder or volume from a machine that has downloaded it.

**Why not GPU?** Not needed. ~10 ms per pair on CPU is fine at this scale, and the Docker image stays small.

**Where is the experiment recorded?** Row 10 of `evals/baselines/EXPERIMENTS.md`. It sits next to row 4 (keyword
re-ranking, rejected), and the contrast is explained in section 6.6.
