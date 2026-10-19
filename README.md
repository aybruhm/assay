# Assay

Assay is a financial planning assistant. You describe your situation, and it answers with costed figures. The figures are calculated by tested Python code using versioned YAML rule packs. The language model does not do the arithmetic.

Rule packs are versioned YAML files of tax thresholds and rates. Each value cites the official page it came from.

Questions it can answer today:

- What do I take home now?
- What do I take home if I pay more into my pension?
- For a company director, how does salary compare with dividends?
- I have a PAYE salary. How much can my company pay me in dividends, and what
  tax is due?
- What do the same savings come to in an ISA against a general account?
- What is my income tax on salary, pension, rental and other income?
- How much student loan will I repay?
- What is the basic rate, the personal allowance, or another rule value?

The language model reads the conversation, chooses a tool, and writes the
explanation. The calculation tools are deterministic calculators. The model
never does arithmetic and never supplies a tax rate. A validator checks that
every number in the explanation matches a tool result before anything is
delivered. Each run is written to an audit log [(see provenance)](https://github.com/aybruhm/provenance).

Rule packs currently cover the United Kingdom and Nigeria, the two tax systems
I can check against official sources.

## The problem, and who has it

General-purpose AI assistants are bad with money: they invent numbers, apply
outdated or wrong-country tax rules, and drift into giving advice. The people
who feel this are everyday earners who want to know what they will actually
take home after tax and pension, and who want to check every figure instead of
taking an assistant's word for it.

## What goes wrong, and what Assay does about it

| Failure | Response |
| --- | --- |
| The model invents a number | Models do not calculate. They call a calculator that produces the figures |
| The model applies the wrong year's rates | Rates and thresholds are data in YAML rule packs, each value carrying a source URL |
| A figure cannot be checked | Every figure in the report names the result id it came from |
| The text turns into a recommendation | The report describes figures and trade-offs. A review step for the wording is not built yet |

If the model cannot answer, the run returns no figures and states the reason.
It does not guess.

## How a run works

The graph is an agent loop, not a fixed list of questions.

```mermaid
flowchart TD
    Start([start]) --> intake[intake: extract the country and known facts]
    intake -->|country missing| ask[ask_user: pause and ask]
    intake -->|country known| prepare[prepare: load the rule pack]
    prepare --> agent[agent: choose a tool or answer]
    agent -->|tool call| tools[tools: run a calculator or research tool]
    tools --> agent
    agent -->|missing input| ask
    ask --> agent
    agent -->|enough results| narrate[narrate: explain the figures]
    narrate --> validate[validate: check every figure]
    narrate -->|rule pack changed| fail
    validate -->|passed| deliver[deliver: write the audit record, end]
    validate -->|figures wrong, retry| narrate
    validate -->|too many retries| fail[fail_closed: end with no figures]
    prepare -->|unsupported country or date| fail
    deliver -->|audit write failed| fail
```

- **Intake** extracts the country and any facts the user stated. Country and
  planning date select the rule pack.
- **Prepare** loads the pack and fails closed when the country or date is not
  supported.
- **Agent** reads the conversation, the profile, the tool catalog and the
  results so far. It either calls tools, asks for a missing input, or says it
  has enough results.
- **Tools** run calculators or trusted-source research. A calculator result
  carries its name, version, inputs and rule ids. A research result carries its
  title, URL and fetch time.
- **Narrate** writes the answer from the tool results. Every figure is copied
  with a citation marker.
- **Validate** recomputes every displayed figure and rejects wrong numbers,
  unknown ids or uncited figures. After three attempts the run ends with no
- **Deliver** writes the audit record. No audit record, no delivery.

The model can call more than one tool. For example, it can compute take-home
pay for an existing salary and then use that salary in a dividend calculation.

## Tools

| Tool | What it does |
| --- | --- |
| `take_home` | Income tax, National Insurance and net pay for a salary |
| `income_tax` | Income tax and net income for salary, pension, rental and other non-dividend income |
| `pension` | Take-home pay with a pension contribution that reduces taxable pay |
| `student_loan` | Annual student loan repayment for Plan 1, Plan 2, Plan 4, Plan 5 or Postgraduate |
| `director_pay` | Salary and dividend mix compared with the same company cost paid as salary |
| `dividend_capacity` | Dividend available from company profit and reserves, dividend tax, and net dividend |
| `isa_vs_general` | After-tax growth of the same savings in an ISA and a general account |
| `lookup_rule` | A rate or threshold with its effective date and official source |
| `search_trusted_sources` | Titles, URLs and snippets from allowlisted trusted pages |
| `fetch_source` | The cleaned text of one allowlisted trusted page |

Calculator tools read the rule pack for the run's country and planning date.
Research tools read allowlisted pages. The model sees a catalog of tool names
and arguments. The tool executor validates the arguments against a Pydantic
model before it runs the tool.

## Architecture overview

The main parts:

- **The graph** (`src/planner/graph/`) is the runtime: intake, the agent loop,
  validation, delivery and checkpoints.
- **The tools** (`src/planner/tools/`) map tool calls to calculators, rule
  packs and trusted-source research. The agent node never imports a
  calculator.
- **The rule packs** (`rules/gb/*.yaml`, `rules/ng/*.yaml`) are data, not code.
  A reviewer can check any value against its source URL without reading code.

| Port | Adapters |
| --- | --- |
| `ModelPort`: `extract_profile`, `decide`, `narrate` | `LangChainModel` (a real model) and `ScriptedModel` (fixed answers for tests) |
| `ResearchPort`: `search`, `fetch` | `HttpResearch` (trusted sources only) and `FakeResearch` (for tests) |
| `AuditSink`: `record_batch` | `ProvenanceSink` (the audit gateway) and `InMemorySink` (for tests) |

Money is a plain `int` at a fixed scale of 10⁴ (£142,382.3234 is
`1423823234`). No floats, and every rounding step is explicit and named.
Countries are packages behind one small contract plus one line in a registry.
The United Kingdom (`GB`) provides the calculator tools. Nigeria (`NG`)
provides `take_home`. Both countries support `lookup_rule`.

## Getting started

Requirements: Python 3.14, [uv](https://docs.astral.sh/uv/), and Docker.

```sh
uv sync --all-groups          # install dependencies
docker compose up -d db       # PostgreSQL for checkpoints
```

**Run the demo**: a run that gets killed mid-narration and resumes with the
same figures:

```sh
sh scripts/demo_resume.sh
```

**Run your own session** (with the scripted fake model, no API key):

```sh
export PLANNER_DB_URL=postgresql://planner:planner@localhost:5432/planner
PLANNER_FAKE_MODEL=1 PLANNER_FAKE_SINK=1 \
  uv run python -m planner.cli run my-thread "I earn 45,000 a year in England" --date 2026-10-01
uv run python -m planner.cli history my-thread
uv run python -m planner.cli resume my-thread
```

The last command prints the report and the cited figures. `run` appends the
message to the thread, so the saved conversation and profile carry forward. Use
`resume` to continue a run that paused or crashed.

**With a real model**, set `PLANNER_MODEL` instead of `PLANNER_FAKE_MODEL`
(e.g. `PLANNER_MODEL=anthropic:claude-sonnet-4`).

When the agent needs a fact, the CLI prints its question and asks for the
missing fields.

### Configuration

Copy the template and fill in your values. The CLI loads `.env` from the repo
root at startup, and variables set in your shell take precedence.

```sh
cp .env.template .env
```

Three variables have no default. A run fails when one is missing:

| Variable | What it does |
| --- | --- |
| `PLANNER_DB_URL` | PostgreSQL connection string for checkpoints |
| `PLANNER_MODEL` | LangChain model name for the real model adapter |
| `PROVENANCE_GATEWAY_URL` | Provenance audit gateway |

The fake adapters replace two of them. Set `PLANNER_FAKE_MODEL` instead of
`PLANNER_MODEL` to run without an API key, and `PLANNER_FAKE_SINK` instead of
`PROVENANCE_GATEWAY_URL` to keep audit records in memory.

The rest are optional:

| Variable | Default | What it does |
| --- | --- | --- |
| `PLANNER_FAKE_MODEL` | unset | Any non-empty value uses the scripted in-memory model |
| `PLANNER_FAKE_SINK` | unset | Any non-empty value writes audit records to memory |
| `PLANNER_FAKE_RESEARCH` | unset | Any non-empty value uses the in-memory research adapter |
| `PLANNER_RESEARCH_TIMEOUT` | `10` | Timeout in seconds for research requests |
| `PLANNER_RESEARCH_USER_AGENT` | `Assay/0.1 (trusted source research)` | User agent sent when fetching trusted pages |
| `PLANNER_RULES_DIR` | `rules/` in the repo | Directory the rule packs load from |
| `PLANNER_CRASH_AT` | unset | Kill the process as the named graph node starts. Used by the resume demo |
| `PROVENANCE_AGENT_ID` | `planner` | Agent identity sent to the audit gateway |
| `PROVENANCE_API_KEY` | unset | API key for the audit gateway |
| `PHOENIX_PROJECT_NAME` | `assay` | Phoenix project that receives the traces |
| `PHOENIX_COLLECTOR_ENDPOINT` | `http://localhost:6006` | Phoenix collector base URL |
| `PHOENIX_API_KEY` | unset | API key for a hosted Phoenix collector |

The CLI calls `configure_tracing()` on every command. It loads `.env`, then
registers a Phoenix tracer with auto-instrumentation. The Phoenix SDK reads
`PHOENIX_COLLECTOR_ENDPOINT` and `PHOENIX_API_KEY` itself, so this project does
not pass them explicitly. With no endpoint set, traces go to
`http://localhost:6006`.

## Checking the work

```sh
uv run pytest src/planner/tests   # unit and integration tests (PostgreSQL required for integration)
uv run mypy src/planner           # strict type checking
uv run lint-imports               # the trust-boundary import contracts
```
