# 06. Structured RAG: what it is, why we need it, how it works here

Read this after `01-the-story.md`. It answers three questions: **what is structured RAG, was our code doing it, and how do we do it
now** (with exactly what was verified and what was not).

---

## 1. What structured RAG is

**Ordinary ("unstructured") RAG** finds *text* by meaning: documents are cut into chunks, each chunk becomes a list of numbers
(an embedding), and the chunks closest to the question go into the prompt. That is perfect for "what is the pet policy?".

It is the wrong tool when the answer is a **fact in a table**:

| Question | Why similarity search cannot do it |
|---|---|
| "Is the Skyline Suite free 3-5 November?" | needs date arithmetic over bookings and room inventory |
| "Cheapest room that sleeps 4" | needs filtering and sorting by numbers |
| "Which hotel is rated highest?" | needs an average over *all* reviews |
| "Average price in Tokyo", "how many hotels?" | needs aggregation; language models are unreliable at counting and averaging |

**Structured RAG** = at question time, **query the database** (rows, filters, aggregates) and let the model write the answer from
those exact rows. "Retrieval" here means *a database query*, not *a nearest-neighbour search*.

```
unstructured RAG:  question -> embed -> nearest text chunks ------------------------> model writes answer
structured RAG:    question -> model picks a query -> database returns exact rows --> model writes answer
```

Real systems usually use **both**, and so do we: documents (FAQs, policies) through vector search, numbers and availability
through database queries.

---

## 2. Was our code doing it before? (honest answer: only the weakest form)

Before this work, every question got the **entire hotel catalog and the guest's bookings pasted into the prompt**. This is
"context stuffing": structured data is *present*, but nothing is *retrieved* for the question. Consequences we found:

* **No availability answers**: booking data for dates was never in the prompt. The website could do it (the room-types
  endpoint computes free rooms per date range), the chatbot could not.
* **No real filtering, ranking, counting or averaging**: the model had to do arithmetic on pasted text.
* **Amenities were missing** from the catalog text.
* **The shown "rating" was wrong**: it was the mean of only the latest 3 reviews, presented as the hotel's rating.
* **It cannot scale**: 3 hotels fit in a prompt, 300 do not.
* **"Today" was not in the prompt**, so "next Friday" could not be resolved.

(`structured_rag_service.py`, which you had written as text-to-SQL, was never called by the chat code. It is explained in
section 4.)

---

## 3. How it works now

### 3.1 The flow

```
guest question
  -> Gemini receives: the question, the usual context, TODAY'S DATE, and a menu of 4 tools
       |-- no lookup needed (policy, FAQ, opinion)  -> answers immediately            1 Gemini request
       '-- lookup needed -> asks for a tool with arguments, e.g.
              check_availability(hotel_name="Shibuya", room_type_name="Skyline Suite",
                                 checkin_date="2026-11-03", checkout_date="2026-11-05")
              -> our code validates the arguments
              -> runs a pre-written, parameterized query (max 10 rows)
              -> the rows go back to Gemini -> it writes the answer                    2 Gemini requests
```

The model chooses **which question to ask the database**. Our code decides **how the database is asked**. The model never writes SQL.

### 3.2 The four tools

| Tool | Answers questions like | Key arguments |
|---|---|---|
| `search_hotels` | "highest rated hotel", "hotels in Japan", "hotels with a spa", "hotels allowing pets" | city, country, amenity, policy_keyword, min_rating, sort_by (rating/price/name), limit. Returns **true average rating**, review count, lowest price, amenities |
| `search_room_types` | "rooms under $500", "cheapest room for 4", "suites at the Aspen Lodge" | hotel_name, min/max_price, min_guests, amenity, sort_by, limit |
| `check_availability` | "is the Skyline Suite free 3-5 Nov?", "any room next Friday?" | checkin_date and checkout_date (required), hotel_name, room_type_name, rooms, guests. Returns free rooms, price, estimated total |
| `catalog_stats` | "how many hotels?", "average price in Tokyo", "average rating per hotel" | metric (hotel_count, room_type_count, avg_price, min_price, max_price, avg_rating), group_by (city, country, hotel, all) |

### 3.3 Where each piece lives

| Piece | File |
|---|---|
| Tool menu shown to the model, argument validation, the queries | `app/services/structured_rag_service.py` |
| Free-room calculation (shared with the website endpoint) | `room_type_availability()` in `app/services/room_type_service.py` |
| Asking Gemini, running the tools, sending results back, up to 3 rounds | `call_gemini_cloud_api(..., tools=, tool_runner=)` in `app/services/llm_service.py` |
| Wiring into the chat: today's date, tool-use rules, saving and citing lookups | `_generate_reply` in `app/services/chat_service.py` |
| Test world with rooms and reviews | `evals/seed.py` |

### 3.4 The safety rules (each has a test)

1. **Read-only, public catalog data only**: hotels, room types, prices, ratings, availability counts. No guests, bookings or
   e-mails. (A guest's own reservations remain in the prompt, scoped to that guest, as before.)
2. **Whitelisted, type-checked, range-limited arguments.** Unknown arguments are ignored; bad ones return an error the model can
   explain; the model never sees a Python exception.
3. **Bound parameters only.** Text from the model reaches the database as a parameter, with `%` and `_` escaped, so
   `x'; DROP TABLE hotels;--` is just a name that matches nothing.
4. **Capped results** (10 rows), **no past dates**, **stays of at most 30 nights**, **at most 5 rooms**.
5. **Scoped to the chat**: if the chat widget belongs to one hotel, every tool is limited to that hotel.
6. **Failures are isolated**: each tool runs in a database SAVEPOINT, so a failed lookup cannot discard the guest's pending message.
7. **Everything is recorded**: lookups are saved in the chat history column `tool_calls_json`, cited as "Live data: ..." (listed
   first), shown as `tool_*` steps in Phoenix, and returned with their exact results in the `debug` payload.

---

## 4. Text-to-SQL (your original file) versus tools

|  | Text-to-SQL (`structured_rag_service.py` as it was) | Tools (what we built) |
|---|---|---|
| What the model produces | a SQL statement | a tool name plus typed arguments |
| Safety | regex guardrails over free text, hard to prove safe | arguments validated, queries fixed and parameterized |
| Scoping to a guest/hotel | injected into the SQL text | built into each query |
| Flexibility | any question the schema allows | the questions the tools cover |
| Consistency with the website | none | availability uses the *same* function as the website |

The file name `structured_rag_service.py` is reused, but its content is new. The old text-to-SQL version is still in git history:
`git checkout 85e5245 -- hms/app/services/structured_rag_service.py` would overwrite the new file, so if you ever want to compare,
use `git show 85e5245:hms/app/services/structured_rag_service.py` instead.

If you later want free-form questions the tools do not cover ("how many bookings did we get in June?" for staff), the sensible
route is a *separate, staff-only* text-to-SQL path using a read-only database role, a few allow-listed views and a statement
timeout, evaluated with the same framework. We did not build that.

---

## 5. What was verified

**Offline (343 tests pass, no AI quota needed):**
* 52 tests of the tools against hand-computed answers from the seed (sold-out suite, partial availability, checkout day not a
  night, Tokyo average $565, overall rating 4.33, price filters, rooftop amenity across hotel- and room-level, hostile text,
  scoping, no guest data in results, argument limits).
* 12 tests of the Gemini loop with a scripted fake Gemini (one round trip; several calls at once; a model that never stops
  asking; a crashing tool; fallback models; the key travels in a header).
* 8 tests of the whole chat path (what is saved, cited, traced and scoped; a failed lookup keeps the guest's message).
* 22 more dataset tests (new fields, the tool checker).

**Live Gemini, structured category (17 questions): 14/17 exact checks.**
Good: it resolved "next Friday" to 6-7 November from today's date; carried the hotel and room type across a follow-up; handled a
past date through the tool's refusal; sold-out and price answers matched the database.
The 3 misses were *routing*, not wrong answers: (1) for "average price in Tokyo" it summed a room list itself instead of calling
`catalog_stats`; (2) "which hotels have a rooftop facility" was answered from the pasted text with no lookup; (3) with no dates
given it called `check_availability` once, the tool refused, and then it asked for the dates.

**Cost of using it (measured on those 17):** 1.94 Gemini requests per question, about 7,600 tokens (vs ~2,400 without lookups),
median 6.5 s / worst 12.4 s (vs ~2.5 s). Questions without a lookup are unchanged.

---

## 6. What was NOT verified (and why)

The Gemini free **daily** quota ran out mid-experiment (500 requests/day for `gemini-3.5-flash-lite`, 20/day for the backup model;
reset about 16 hours later). Therefore:

* **Not measured:** the full 89-question regression with the tools attached (do policy/FAQ answers stay 100%, and do text questions
  avoid lookups?); the 6 new tool-abuse red-team attacks on live Gemini; judge scoring of structured answers.
* **Not shipped:** a stricter prompt, "v2", written to fix the three routing misses (use `catalog_stats` for any arithmetic; use a
  tool for "which hotels have X" even when the text seems to contain the answer; never call availability without both dates).
  Its test run died on the quota. Our rule is that a change stays only if the numbers support it, so it was reverted. It is a
  ready-to-run candidate (recipe R15 in `04-how-to.md`).
* Offline tests prove the code; only live runs show how well the model *chooses* tools.

---

## 7. How to continue (commands are in `04-how-to.md`, recipes R15-R17)

1. After the quota resets, run the regression: `python -m evals.runner --label structured-regression` and the red team.
2. Run the v2 prompt experiment on the structured category with `--repeat 3`; keep it only if the pass rate improves without
   hurting other categories.
3. When green, consider shrinking the pasted catalog (now partly redundant) to cut the ~2,400-token baseline.
4. Add tools when you need them (R17): a declaration, a handler, tests, golden questions.
