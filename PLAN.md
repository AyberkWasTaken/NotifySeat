# NotifySeat - Project Architecture & Implementation Plan

**Prepared for:** Ayberk  
**Project Name:** NotifySeat  
**Target:** Local-First Transport Seat Availability & Cancellation Notifier  

---

## 1. Web Research & Competitor Analysis Summary

### State of Existing Tools
1. **TCDD Bots (`tcdd-bilet-bulucu`, `train-ticket-checker`, etc.):**
   - *Status:* Mostly single-purpose Python scripts or simple static pages created between 2021-2024.
   - *Issues / Rotten State:* Many are abandoned or broken due to TCDD backend URL/payload migrations (`api-yebsp.tcddtasimacilik.gov.tr`). Most only support basic SMTP email (often hardcoded Outlook/Gmail) or Telegram.
2. **Flight Ticket Bots (THY, Pegasus, SunExpress):**
   - *Status:* Fragmented scrapers or expensive cloud SaaS tools (Google Flights, Skyscanner price alerts) that do **not** check for granular seat cancellations or specific seat inventory in real time.
3. **Bus Ticket Bots (Obilet, etc.):**
   - *Status:* No maintained open-source cancellation tracker exists.

### NotifySeat Differentiators & Value Proposition
- **Unified Multi-Transport:** Monitors TCDD trains (YHT, Mainline), Flights (THY, Pegasus, SunExpress), and Intercity Buses.
- **100% Local-First:** Runs entirely on Ayberk's local computer. No cloud servers, no recurring subscription costs, complete privacy.
- **Multi-Channel Alerts:** Telegram Bot, Discord Webhooks, Email (SMTP), Desktop notifications (with system sound buzzer), SMS (Twilio/Netgsm), and custom Webhooks.
- **Dual Interface:** Full-featured interactive CLI + modern embedded Local Web GUI Dashboard with live seat monitor, audio chimes, and instant test tools.
- **Anti-Ban & Jitter Engine:** Smart polling with randomized intervals and human-like request headers to avoid rate limits.

---

## 2. Implementation Milestones

- [x] **Milestone 1: Web Research & Architectural Specification**
- [ ] **Milestone 2: Core Data Models, Database & Configuration Management**
- [ ] **Milestone 3: Multi-Channel Notification Engine**
- [ ] **Milestone 4: Transport Providers (TCDD, Flight, Bus, Simulation)**
- [ ] **Milestone 5: Background Scheduler & State Change Detector**
- [ ] **Milestone 6: Rich Interactive CLI Application**
- [ ] **Milestone 7: Modern Local Web GUI Dashboard & REST API**
- [ ] **Milestone 8: Test Suite, Verification & Working Demo**
- [ ] **Milestone 9: Documentation & Usage Guides**
