# SlotBot

> Real-time voice AI receptionist for Indian clinics.
> Speaks Hinglish. Books appointments. Never misses a call.

[![CI](https://github.com/harshit21-shah/slotbot/actions/workflows/ci.yml/badge.svg)](https://github.com/harshit21-shah/slotbot/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12-blue)]()
[![Tests](https://img.shields.io/badge/unit_tests-74_passing-brightgreen)]()

---

## Try It Live

**Call: +1-xxx-xxx-xxxx** *(Twilio demo number — configure in `.env.local`)*

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
[Groq / Anthropic LLM]  →  "Zaroor! Aapka naam kya hai?"
           ↓
[Sarvam AI TTS, <100ms]  →  audio back to caller
           ↓
... (2-3 more turns) ...
           ↓
[Cal.com API]  →  slot booked ✓
[Twilio SMS]   →  "Appointment confirmed: Dr. Sharma, 15 June 10:00 AM"
```

**Target call time: ~60–90 seconds. Target end-to-end latency per turn: ~490ms p95.**

## Architecture

```
Twilio (inbound call)
  → FastAPI WebSocket server
  → Deepgram STT (streaming, real-time)
  → LangGraph (8-state conversation machine)
      ↓ tool calls
      Cal.com API (availability + booking)
      Twilio SMS (confirmation)
  → Groq / Anthropic LLM (generation)
  → Sarvam AI TTS (Hinglish voice)
  → audio back to Twilio → caller
```

## Design Targets

*Benchmark goals from the PRD — run `scripts/simulate_call.py` and `scripts/latency_bench.py` locally to measure.*

| Metric | Target |
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
| [Architechture.md](Architechture.md) | System design, WebSocket flow, latency budget |
| [Design.md](Design.md) | State machine, Hinglish handling, edge cases |
| [PRD.md](PRD.md) | Product vision, goals, user personas |
| [claude.md](claude.md) | Agent conventions and dev notes |
| [render.yaml](render.yaml) | Render deployment config |
