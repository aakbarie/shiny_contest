# Shiny App Generator

A working tool that turns a CSV file and a natural-language description into an executable Shiny for Python application, using a local LLM for code generation, AST-based security validation before any code is written to disk, and a small observability layer for health and metrics. Built as a Shiny contest entry; kept production-shaped because the operational-intelligence work I do day to day requires that the artifacts I demo behave like things I would actually deploy.

## What it does

You upload a CSV. You describe the dashboard you want. The application:

1. Validates the upload — file size, MIME type, extension, and CSV structure.
2. Validates your description — length bounds, prompt-injection patterns.
3. Sends a structured prompt to a locally-hosted LLM (`deepseek-coder-v2` via Ollama) with the column schema and a small data sample.
4. Extracts the Python code from the LLM response and strips comment-only lines.
5. Runs the generated code through an AST-based security validator that flags dangerous imports and function calls.
6. Writes the validated code to disk with a safe filename and exposes it for download.

A health endpoint at `/health` reports uptime, model availability, and rolling generation metrics (success rate, average generation time). Every request gets a tracked ID through structured logging so the full pipeline can be traced end to end.

## Why this is interesting

Three design choices distinguish this from the standard "LLM-writes-code" demo:

**Local LLM inference, no external API calls.** The tool runs against Ollama hosted on the same machine. Nothing leaves the box. For environments where the data being analyzed cannot transit a third-party API (regulated healthcare, finance, anything PHI- or PII-bearing), this is the difference between "interesting demo" and "deployable pattern." I do my day job in regulated healthcare, so this was the constraint I built around.

**Code security validation as a first-class step, not a postscript.** Every line the LLM produces is parsed into an AST, walked, and checked against an explicit blocklist of dangerous imports (`os.system`, `subprocess.Popen`, `eval`, `exec`, etc.) and call patterns. If the validator flags anything, the code never gets written to disk. The validation step is logged independently and counted as a metric. This treats LLM-generated code the way you'd treat any other untrusted input: validate before use, not after.

**The whole thing is observable.** Health endpoint, structured request-scoped logging with context IDs, metrics for generation success rate and latency, graceful degradation if Ollama is unreachable. Most LLM demos skip this entirely. For anything that's going to run unattended, it's the layer you need to know whether the system is actually working.

## Architecture

```
┌──────────────┐    ┌────────────────┐    ┌─────────────┐
│  Shiny UI    │───▶│  FileValidator │───▶│  CSV loaded │
│  (file +     │    │  + InputVali-  │    │  + columns  │
│  prompt)     │    │  dator         │    │  sampled    │
└──────────────┘    └────────────────┘    └─────────────┘
                                                  │
                                                  ▼
                                          ┌─────────────┐
                                          │  LangChain  │
                                          │  + Ollama   │
                                          │  (local)    │
                                          └─────────────┘
                                                  │
                                                  ▼
                                          ┌─────────────┐
                                          │  Code       │
                                          │  extracted  │
                                          │  & cleaned  │
                                          └─────────────┘
                                                  │
                                                  ▼
                                          ┌─────────────┐
                                          │ CodeSecuri- │
                                          │ tyValidator │
                                          │ (AST walk)  │
                                          └─────────────┘
                                              │     │
                                       safe ──┘     └── unsafe
                                              │           │
                                              ▼           ▼
                                       ┌──────────┐  ┌──────────┐
                                       │  Write   │  │  Reject  │
                                       │  to disk │  │  + log   │
                                       │  + offer │  └──────────┘
                                       │ download │
                                       └──────────┘
```

A separate `/health` endpoint reads from the `health_checker` and `metrics_collector` modules and is independent of the main request path, so it stays responsive even when generation is mid-flight.

## Requirements

- Python 3.9+
- [Ollama](https://ollama.com/) running locally with the `deepseek-coder-v2` model pulled
- Conda or `pip` for environment management
- Roughly 8 GB of available RAM for the LLM (more is better)

## Quick start

```bash
# Clone
git clone https://github.com/aakbarie/shiny_contest.git
cd shiny_contest

# Environment (Conda)
conda env create --name shiny_app_env --file=environment.yml
conda activate shiny_app_env

# Or with pip
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Pull the LLM (in another terminal)
ollama pull deepseek-coder-v2

# Configure
cp .env.example .env
# Edit .env to set OLLAMA_BASE_URL, LLM_MODEL, APP_PORT, etc.

# Run
python app.py
```

The app starts on `http://localhost:8050` by default. Visit `/health` to confirm the LLM is reachable.

## Usage

1. **Upload a CSV.** Anything under the configured size limit (default 50 MB), with parseable structure. The validator will reject malformed files with a specific error before the LLM ever runs.
2. **Describe the dashboard.** Be specific about what you want to see — e.g., "Bar chart of revenue by region with a date range filter, plus a summary table of top 10 customers." Vague prompts produce vague apps.
3. **Toggle PyGWalker.** If you want an interactive exploratory view in addition to the generated dashboard, leave the checkbox on.
4. **Generate.** First run takes 30–90 seconds depending on hardware. The status panel shows progress; the success message reports total generation time.
5. **Download.** The generated app is a single `.py` file. Run it with `python <filename>.py` to launch the generated dashboard.

## Project structure

```
shiny_contest/
├── app.py              # Main Shiny application + server logic
├── config.py           # Environment-aware configuration
├── utils/              # Validators, security, logging, monitoring
│   ├── validators.py
│   ├── security.py
│   ├── logging.py
│   └── monitoring.py
├── requirements.txt
├── environment.yml
├── .env.example
└── README.md
```

## Known limitations

A real list, not the conventional empty one:

- **Generation quality depends on prompt specificity.** The LLM does better with a clear, structured description than with one-line prompts. A "Make me a sales dashboard" prompt produces a generic result; a description that names the chart types, fields to filter on, and aggregations produces something usable.
- **The AST validator catches the obvious dangerous patterns, not all of them.** It's a meaningful first line of defense, not a guarantee. I would not run generated code from untrusted prompts in a privileged environment without an additional sandbox layer (containerization, separate user, restricted filesystem).
- **Local-only by design.** The architecture assumes Ollama on `localhost`. If you want this to use a different inference backend, you'll need to swap the LangChain initialization in `app.py` and update the health checker.
- **Single-tenant.** No authentication, no per-user rate limiting, no session isolation. This was built as a contest entry and a working example of the pattern, not as a multi-user product.
- **Generated code is not auto-tested.** The validator confirms the code is structurally safe; it does not confirm the code does what the user asked for. Users have to run the output and verify.

## Why I built this

Most of my production work is internal and behind enterprise firewalls. This repo is a public artifact that shows the pattern I use elsewhere — local-inference LLM workflows with input validation, code-level security checks, and observability built in from the start — applied to a problem (Shiny app generation) where the output is itself something a non-technical user can pick up and run. The pattern generalizes. The same primitives that validate and execute LLM-generated Shiny apps can validate and execute LLM-generated SQL, transformations, report templates, or any other code-as-output workflow.

## License

MIT. See [LICENSE](./LICENSE).

## Contact

Akbar Akbari Esfahani · [LinkedIn](https://www.linkedin.com/in/akbar-akbari-esfahani/) · akbar.esfahani@email.com