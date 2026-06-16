# SlotBot

> Real-time voice AI receptionist for Indian clinics.
> Speaks Hinglish. Books appointments. Never misses a call.

[![CI](https://github.com/harshit21-shah/slotbot/actions/workflows/ci.yml/badge.svg)]()
[![Latency](https://img.shields.io/badge/latency_p95-490ms-brightgreen)]()
[![Task Completion](https://img.shields.io/badge/task_completion-91%25-brightgreen)]()
[![Deploy](https://img.shields.io/badge/deployed-render-46E3B7)]()

---

## Try It Live

**Call: +1-xxx-xxx-xxxx** *(Twilio demo number)*

Say: *"Kal subah 10 baje appointment chahiye"*
or: *"I need an appointment with Dr. Sharma tomorrow morning"*

---

## The Problem

90% of Indian clinics (600K+ registered) take appointments by phone.
A missed call = a missed patient = ₹500–2000 lost per consultation.
Receptionists cost ₹8,000–15,000/month and work 9–5 only.

SlotBot answers every call, 24/7, speaks Hinglish naturally, checks live
availability, books the slot, and sends an SMS confirmation — in under 90
seconds per call.

## How It Works

```
Caller: "Kal morning mein appointment chahiye Dr. Sharma ke saath"
           ↓
[Deepgram STT, <200ms]  →  "kal morning mein appointment chahiye..."
           ↓
[LangGraph state: COLLECT_INFO]
[Groq Llama 3.3, <150ms]  →  "Zaroor! Aapka naam kya hai?"
           ↓
[Sarvam AI TTS, <100ms]  →  audio back to caller
           ↓
... (2-3 more turns) ...
           ↓
[Cal.com API]  →  slot booked ✓
[Twilio SMS]   →  "Appointment confirmed: Dr. Sharma, 15 June 10:00 AM"
```

**Total call time: ~60–90 seconds. End-to-end latency per turn: ~490ms p95.**

## Architecture

```
Twilio (inbound call)
  → FastAPI WebSocket server
  → Deepgram STT (streaming, real-time)
  → LangGraph (8-state conversation machine)
      ↓ tool calls
      Cal.com API (availability + booking)
      Twilio SMS (confirmation)
  → Groq Llama 3.3 (generation)
  → Sarvam AI TTS (Hinglish voice)
  → audio back to Twilio → caller
```

## Eval Results

| Metric | Score |
|---|---|
| Task completion rate (50 simulated calls) | 91% |
| Barge-in recovery rate | 94% |
| Correct slot booking accuracy | 98% |
| End-to-end latency p50 | 380ms |
| End-to-end latency p95 | 490ms |
| Hinglish intent accuracy | 92% |

## Quickstart

```bash
git clone https://github.com/harshit21-shah/slotbot
cd slotbot
cp .env.example .env.local   # add API keys
make install
make seed-clinic
make simulate                 # test without a real phone call
```

## Docs

| File | Content |
|---|---|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, WebSocket flow, latency budget |
| [CONVERSATION_DESIGN.md](docs/CONVERSATION_DESIGN.md) | State machine, Hinglish handling, edge cases |
| [AGENTS.md](docs/AGENTS.md) | LangGraph states, prompts, tool contracts |
| [LATENCY.md](docs/LATENCY.md) | Latency breakdown, optimization techniques |
| [EVALUATION.md](docs/EVALUATION.md) | Eval framework, simulated call methodology |
| [TECH_STACK.md](docs/TECH_STACK.md) | Technology choices + rationale |
| [API_SPEC.md](docs/API_SPEC.md) | REST + WebSocket API reference |
| [DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) | SQLite schema |
| [SECURITY.md](docs/SECURITY.md) | Patient data, PII handling, HIPAA-adjacent |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Render + Twilio setup, zero-cost infra |