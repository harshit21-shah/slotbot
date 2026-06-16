# CLAUDE.md — AI Agent Operating Guide for SlotBot

Read this fully before touching any file in this repo.

## 1. What Is SlotBot

SlotBot is a real-time voice AI receptionist for Indian clinics. It handles
inbound phone calls via Twilio, transcribes speech in real-time via Deepgram,
runs a LangGraph conversation state machine, generates responses via Groq
(Llama 3.3), converts text to speech via Sarvam AI (Hindi/Hinglish) or
ElevenLabs (English), and books appointments via Cal.com API.

**Core invariants:**
1. End-to-end latency must stay under 800ms (STT → LLM → TTS). Any code
   change that adds blocking I/O to the hot path must be benchmarked.
2. Barge-in detection is non-optional. If a caller speaks while the agent
   is speaking, the agent MUST stop and process the interruption.
3. The agent must NEVER book a slot that is already taken. Double-booking
   is worse than failing to book.
4. If confidence drops below threshold on any utterance, the agent asks
   for clarification — it does not guess and proceed.

## 2. Repo Map

```
slotbot/
├── CLAUDE.md
├── README.md
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── CONVERSATION_DESIGN.md
│   ├── AGENTS.md
│   ├── LATENCY.md
│   ├── EVALUATION.md
│   ├── TECH_STACK.md
│   ├── API_SPEC.md
│   ├── DATABASE_SCHEMA.md
│   ├── SECURITY.md
│   └── DEPLOYMENT.md
├── services/
│   ├── telephony/          # Twilio webhook handlers, WebSocket server
│   ├── stt/                # Deepgram streaming client
│   ├── tts/                # Sarvam AI + ElevenLabs TTS clients
│   ├── agents/             # LangGraph conversation state machine
│   │   ├── states/         # one file per conversation state
│   │   ├── prompts/        # versioned prompt files
│   │   └── tools/          # tool definitions (calendar, SMS)
│   ├── calendar/           # Cal.com API client
│   ├── sms/                # Twilio SMS confirmation
│   ├── api/                # FastAPI app (webhooks + REST)
│   └── eval/               # conversation eval harness
├── data/
│   ├── clinics.db          # SQLite: clinic profiles, bookings, logs
│   └── call_logs/          # audio + transcript archives (gitignored)
├── tests/
│   ├── unit/
│   ├── integration/
│   └── eval/               # simulated call transcripts
├── scripts/
│   ├── simulate_call.py    # replay a transcript through the state machine
│   └── latency_bench.py    # measure pipeline latency percentiles
├── infra/
│   └── ngrok.yml           # local tunnel config for Twilio dev
├── pyproject.toml
├── render.yaml
├── Makefile
└── .env.example
```

## 3. Critical Architecture Rules

- **Hot path:** Twilio WebSocket → Deepgram STT → LangGraph → Groq → Sarvam TTS → Twilio.
  Nothing blocking goes in this path. All DB writes, SMS sends, calendar
  bookings happen async (after the agent has already started speaking the
  confirmation).
- **State machine is the source of truth.** Never let a Twilio webhook
  handler contain conversation logic — it passes audio to the state machine
  and returns audio. Business logic lives in `services/agents/states/`.
- **All prompts versioned.** Every system prompt lives in
  `services/agents/prompts/<state_name>_v<N>.txt`. Agent code references
  prompt version explicitly. Never inline prompt strings.
- **No double-booking guard bypass.** `services/calendar/client.py` must
  always call `check_availability()` before `create_booking()`, even if the
  caller already said they want a specific slot and it was available 30 seconds
  ago. Slots can be taken between turns.

## 4. Coding Standards

- Python 3.12, `mypy --strict`, `ruff` + `black` (line length 100).
- All async — `asyncio` everywhere in the hot path. No `time.sleep()`.
- All LLM calls through `services/agents/llm_client.py`.
- Conventional Commits: `feat:`, `fix:`, `perf:`, `eval:`, `docs:`.
- Latency-sensitive changes require a `perf:` commit with benchmark numbers.

## 5. Local Dev Setup

```bash
cp .env.example .env.local
# Add: TWILIO_*, DEEPGRAM_API_KEY, GROQ_API_KEY, SARVAM_API_KEY, CALCOM_API_KEY

make install
make migrate
make seed-clinic    # seeds a demo clinic profile
make tunnel         # ngrok tunnel → paste URL into Twilio console
make run            # FastAPI on :8000
make simulate       # replay sample call transcript (no Twilio needed)
```

## 6. Definition of Done

- [ ] `make lint && make typecheck && make test` pass
- [ ] Latency benchmark (`make bench`) shows p95 < 800ms on hot path
- [ ] New state has eval transcript in `tests/eval/transcripts/`
- [ ] Task completion rate (`make eval-calls`) shows no regression
- [ ] PR description references task ID from TASKS.md