# Pattern catalog

Drawn from Wikipedia's "Signs of AI writing" (WikiProject AI Cleanup) and tropes.fyi, plus tics specific to agent replies. One instance of a pattern is often fine. Clusters and repeats are the problem.

Each entry has what it looks like and what to do instead. Many include a less-plain / plain pair where the fix shape isn't obvious from the rule.

## Contents

- Content
- Words
- Sentence shapes
- Formatting
- Agent replies

## Content

### Inflated significance
Looks like: "marks a pivotal moment", "a testament to", "reflects broader trends", "sets the stage for".
Instead: state the fact. If the significance is real, show it with a consequence or a number.
less-plain: "This refactor marks a pivotal moment for the codebase."
plain: "This refactor cut 400 lines and let us delete the adapter."

### Superficial -ing analysis
Looks like: "The team shipped the fix, highlighting its commitment to reliability." Also underscoring, showcasing, reflecting, emphasizing, ensuring, contributing to.
Instead: end the sentence at the fact. If the analysis matters, give it its own sentence with a real claim.
less-plain: "The team shipped the fix, highlighting its commitment to reliability."
plain: "The team shipped the fix."

### Vague attribution
Looks like: "Experts argue", "Industry reports suggest", "Many developers find".
Instead: name the source or drop the attribution and own the claim.

### Stakes inflation
Looks like: "will fundamentally reshape how we build software", "the next era of".
Instead: describe the actual effect at its actual size.

### The challenges formula
Looks like: "Despite these challenges, the project continues to thrive."
Instead: list the real problems and stop, or say what is being done about them.
less-plain: "Despite these challenges, the migration continues to progress."
plain: "The migration is blocked on three schema conflicts. Two are owned, one is unassigned."

### Asserted obviousness
Looks like: "The reality is simple", "Make no mistake", "The truth is".
Instead: give the evidence and let it be obvious.
less-plain: "The truth is, this query won't scale."
plain: "This query does a full table scan on every call. At 10k rows it's 200ms."

### Invented concept labels
Looks like: "the supervision paradox", "the acceleration trap", used as if they were established terms.
Instead: describe the mechanism in plain words.
less-plain: "We hit the supervision paradox."
plain: "The agents spend more time waiting on approval than the task saves."

### Repetition and recaps
Looks like: one point restated several ways, every section ending with a summary of itself, "In summary" at the end.
Instead: make the point once, in the place it belongs.
less-plain: "In summary, the fix is to add the null check, which addresses the null-check issue."
plain: (delete the summary — the fix is already stated above)

### Comparative framing in options
Looks like: "most flexible", "unlike the others", "works at both ends", "every other column uses one" — when presenting options to someone else for them to pick.
Instead: describe each option on its own terms. Let the reader rank.
less-plain: "Option B is the most flexible — unlike A, it works at both ends."
plain: "Option B accepts strings and numbers. Option A accepts only strings."

### Abstract noun gesturing
Looks like: "the small end", "the ceiling", "the floor/ceiling combo", "both ends".
Instead: name the specific value or row. If an abstract noun can be replaced with the concrete example, replace it.
less-plain: "At the small end, latency drops."
plain: "For rows ≤ 100 MW, latency drops."

## Words

### Generated vocabulary
delve, leverage, robust, seamless, crucial, pivotal, landscape, tapestry, foster, elevate, streamline, empower, unlock, holistic, comprehensive, nuanced, realm, journey, intricate, enhance, harness, paradigm, synergy, vibrant, meticulous, testament, underscore, showcase, myriad, plethora, embark.
Instead: rewrite around the concrete thing. A synonym swap keeps the problem.
less-plain: "We'll leverage the cache to enhance performance."
plain: "The cache cuts the hot path from 200ms to 15ms."

### Magic adverbs and intensifiers
quietly, deeply, fundamentally, remarkably, arguably, truly, incredibly, genuinely, absolutely, certainly.
Instead: delete. If the sentence feels weak without it, the sentence needs a better fact.
less-plain: "This fundamentally changes how the parser works."
plain: "The parser now tokenizes before stripping comments, not after."

### Copula avoidance
Looks like: "serves as the entry point", "stands as", "functions as", "boasts".
Instead: "is the entry point", "has".
less-plain: "`main.py` serves as the entry point."
plain: "`main.py` is the entry point."

### Filler transitions
Moreover, Furthermore, Additionally, Importantly, Interestingly, Notably, "It's worth noting that".
Instead: delete and let the sentence stand. If two ideas need connecting, use "and", "but", or "so".

### Stock idioms
smoking gun, perfect storm, move the needle, double-edged sword, tip of the iceberg, at the end of the day, low-hanging fruit, game changer.
Instead: say the literal thing.

## Sentence shapes

### Negative parallelism
Looks like: "It's not a bug, it's a design flaw." "This isn't just a refactor." "Not because X, but because Y." "The question isn't X. The question is Y."
Instead: say what it is.
less-plain: "This isn't just a refactor — it's a redesign."
plain: "This is a redesign: the data model changes."

### Countdown
Looks like: "Not one. Not two. Seventeen failures."
Instead: say the number.
less-plain: "Not one. Not two. Seventeen failures."
plain: "Seventeen tests failed."

### Self-answered question
Looks like: "The result? A 40% drop." "The catch? It only works on Linux."
Instead: state the fact without the setup.
less-plain: "The catch? It only works on Linux."
plain: "It only works on Linux."

### Setup phrases
Looks like: "Here's the thing:", "Here's the kicker", "Here's where it gets interesting", "What most people miss".
Instead: delete the setup and keep the point.
less-plain: "Here's the thing: the migration already ran."
plain: "The migration already ran."

### Reflexive threes and anaphora
Looks like: "fast, reliable, and scalable" when only one was demonstrated; three sentences in a row starting "They could".
Instead: use the number of items that exist. Vary openings or merge the sentences.
less-plain: "The service is fast, reliable, and scalable."
plain: "The service holds 2k RPS at p99 under 50ms."

### False ranges
Looks like: "from authentication to deployment to observability".
Instead: list the things, or name the one that matters.
less-plain: "The platform covers everything from authentication to deployment to observability."
plain: "The platform does authentication and deployment. Observability is a separate service."

### Teacher voice
Looks like: "Let's break this down", "Let's dive in", "Think of it as a highway for data", "Imagine a world where".
Instead: explain directly. Use an analogy only when it is clearer than the plain explanation.
less-plain: "Let's break this down. Think of the queue as a highway for messages."
plain: "The queue holds messages until a consumer reads them. Writes block when it's full."

### Tailing negations and fragment paragraphs
Looks like: "The options come from the selected item, no guessing." A paragraph that is just "Openly."
Instead: write the full clause, or cut it.
less-plain: "The options come from the selected item, no guessing."
plain: "The options come from the selected item."

## Formatting

### Dashes
Em dashes, spaced en dashes, and double hyphens used as dashes.
Instead: a period, comma, colon, or parentheses.

### Bold-first bullets
Looks like: "- **Performance**: Lazy loads expensive resources".
Instead: plain bullets, or prose if the items aren't really parallel.
less-plain: "- **Performance**: Lazy loads expensive resources"
plain: "- Lazy-loads expensive resources"

### Listicle in disguise
Looks like: "The first issue is... The second issue is... The third issue is..."
Instead: a real list, or prose that connects the points by cause or order.
less-plain: "The first issue is the null handling. The second is the race. The third is the missing index."
plain: "Three issues: null handling, a race in the writer, and a missing index on `user_id`."

### Inline label prefixes
Looks like: "Pro: ships today. Con: locks us to Postgres." inside paragraph prose. Also "Fix: X. Note: Y." in a flowing sentence.
Instead: a real list if the items are parallel keyed, or prose without the labels.
less-plain: "Pro: ships today. Con: locks us to Postgres."
plain: "Ships today, but locks us to Postgres."

### Decorative characters
Unicode arrows, curly quotes, checkmark and rocket emoji.
Instead: plain ASCII. "->" if an arrow is truly needed.

### Structure on short content
Headers on a three-paragraph reply, bold on whole sentences.
Instead: plain paragraphs.
less-plain: a three-paragraph reply broken up with "## Context", "## Fix", "## Next"
plain: three paragraphs in a row

## Agent replies

### Openers
"Great question!", "You're absolutely right!", "Perfect!", restating the request.
Instead: start with the answer or the action.
less-plain: "Great question! You're asking about the retry logic — let me explain."
plain: "The retry logic uses exponential backoff with a 2s floor."

### Narration
"Now let me", "I'll go ahead and", "Let me take a look". Also content narration and vague summary verbs: "my original", "handles the case cleanly", "covers", "deals with".
Instead: do it, then report what happened. For content, point at the specific thing instead of gesturing at it.
less-plain: "The function handles the case cleanly."
plain: "The function returns `null` when `rows` is empty."

### Victory summaries
"I've successfully implemented", "production-ready", "all tests pass" without having run them, checkmark lists.
Instead: say what changed, what you ran, and what you didn't verify.
less-plain: "Successfully implemented and production-ready — all tests pass."
plain: "Added the null check in `fetch_rows`. Ran `pytest tests/fetch_test.py`: 12 pass. Didn't touch integration tests."

### Closers
"Hope this helps", "Let me know if you have questions", "Feel free to", "Happy to help".
Instead: end on the last useful fact or a specific next step.
less-plain: "Hope this helps! Let me know if you have questions."
plain: "Next step: run the migration on staging."

### Compliment sandwich in reviews
"This is a solid start, but...", "Great work overall! One small thing...".
Instead: state the issue and the fix. Praise only what is specifically good, and say why.
less-plain: "Great work overall! One small thing — the error handling could be stronger."
plain: "`fetch_user` swallows `IntegrityError`. Let it bubble; the caller already catches it."
