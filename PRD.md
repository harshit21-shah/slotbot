# PRD.md — Product Requirements Document

## 1. Vision

Every Indian clinic gets a tireless, Hinglish-speaking receptionist that
answers calls 24/7, books appointments instantly, and never double-books —
at a fraction of the cost of a human receptionist.

## 2. Target Users

| Persona | Description | Primary Pain |
|---|---|---|
| **Clinic Owner / Doctor** | Solo practitioner or small clinic (1–5 doctors), Pune/Mumbai/Delhi | Misses calls during consultation; receptionist costs ₹10K+/month |
| **Patient (Caller)** | Urban Indian, comfortable with Hinglish, calling to book/cancel/reschedule | Hates being on hold; frustrated when call goes unanswered |
| **Multi-Doctor Clinic Manager** | Manages appointment schedule for 3–10 doctors | Needs routing: "Which doctor?", specialty-based triage |

## 3. Core Problem

**For the clinic:** A solo doctor sees 20–40 patients/day at ₹500–2000/visit.
Missing 3–5 calls/day = ₹7,500–10,000 lost revenue daily. A receptionist costs
₹8,000–15,000/month and only works 9AM–6PM. SlotBot costs ~₹0 to run (API
costs negligible at clinic scale) and works 24/7.

**For the patient:** Calling a clinic and getting no answer, or being put on
hold, is a universal frustration. 40% of patients who can't reach a clinic
call a competitor. A fast, natural-sounding voice agent that books in under
90 seconds is better UX than most human receptionists.

**The Hinglish gap:** All existing voice AI (Alexa, Google Assistant, Siri)
struggles with code-switching. An Indian patient naturally says "Monday ko
11 baje appointment chahiye Doctor ke saath" — mixing Hindi grammar with
English proper nouns. No off-the-shelf solution handles this gracefully.

## 4. Goals

### V1 (MVP — 4 weeks)
- Inbound call handling via Twilio.
- Deepgram STT with Hindi+English model (code-switching support).
- LangGraph 8-state conversation machine (greeting → info collect → check
  availability → confirm → book → confirmation → goodbye + escalate/reschedule
  branches).
- Groq Llama 3.3 for response generation.
- Sarvam AI TTS for natural Hinglish voice output.
- Cal.com API for availability check + booking.
- Twilio SMS confirmation to patient.
- Single clinic profile (one doctor, fixed hours).
- Barge-in detection via Deepgram VAD.
- Simulated call eval: 50 transcripts, task completion rate metric.

### V2 (weeks 5–8)
- Multi-doctor routing ("Aap kaunse doctor se milna chahte hain?").
- Multi-tenant clinic profiles (one SlotBot instance, multiple clinic configs).
- Reschedule and cancellation flows.
- WhatsApp fallback escalation.
- Latency optimization: streaming TTS (chunk-by-chunk audio) for perceived
  latency improvement.

### Non-Goals (V1)
- No video calls.
- No symptom triage or medical advice.
- No EHR/EMR integration.
- Not a replacement for emergency triage — system always escalates
  "emergency" / "urgent" / "bahut dard" keywords immediately.

## 5. User Stories

1. As a patient, I call the clinic at 9PM and a voice agent answers, asks my
   name and preferred time, checks availability, confirms a slot, and sends
   me an SMS — all in Hinglish, in under 2 minutes.
2. As a patient, I interrupt the agent mid-sentence to change my preferred
   time, and the agent smoothly processes the correction without restarting
   the conversation.
3. As a patient saying "bahut emergency hai", the agent immediately offers
   to connect me to the emergency number or WhatsApp, rather than routing
   me through the booking flow.
4. As a clinic owner, my clinic profile (doctor name, hours, services,
   language preference) is configured once and the agent adapts its script.
5. As a patient, I receive an SMS: "Appointment confirmed: Dr. Sharma,
   Mon 16 June 11:00 AM. Reply CANCEL to cancel. — ABC Clinic"

## 6. Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-1 | Handle inbound Twilio call, stream audio via WebSocket | P0 |
| FR-2 | Real-time STT via Deepgram (Hindi+English, <250ms) | P0 |
| FR-3 | LangGraph 8-state conversation machine | P0 |
| FR-4 | Barge-in detection via VAD — stop TTS on interruption | P0 |
| FR-5 | Groq LLM response generation (<200ms) | P0 |
| FR-6 | Sarvam AI TTS → audio back to Twilio (<150ms) | P0 |
| FR-7 | Cal.com availability check + slot booking | P0 |
| FR-8 | Twilio SMS confirmation to patient | P0 |
| FR-9 | Emergency keyword detection → immediate escalation | P0 |
| FR-10 | Hinglish intent understanding (name, date, time, doctor) | P0 |
| FR-11 | Clarification loop (max 2 attempts, then escalate) | P0 |
| FR-12 | SQLite logging of all calls (transcript, outcome, latency) | P0 |
| FR-13 | Multi-doctor routing | P1 |
| FR-14 | Multi-tenant clinic profiles | P1 |
| FR-15 | Reschedule and cancellation flows | P1 |
| FR-16 | WhatsApp fallback escalation | P1 |

## 7. Non-Functional Requirements

- **Latency:** End-to-end (VAD end → audio playback start) < 800ms p95.
  Target: < 500ms p50.
- **Barge-in:** Agent stops speaking within 300ms of VAD detecting caller
  speech.
- **Booking accuracy:** 0 double-bookings. Slot availability re-checked
  immediately before `create_booking()` call.
- **Uptime:** 99%+ (Render free tier has cold starts — documented, handled
  with a warm-up ping).
- **PII handling:** Patient name and phone number logged but never sent to
  LLM providers. See SECURITY.md.

## 8. Success Metrics

| Metric | Target |
|---|---|
| Task completion rate (booking reached confirmation) | ≥ 88% |
| Barge-in recovery rate | ≥ 90% |
| Slot booking accuracy (no double-book) | 100% |
| Latency p95 (turn-level) | < 800ms |
| Hinglish intent accuracy (name/time/date extraction) | ≥ 88% |
| Emergency escalation accuracy | 100% |