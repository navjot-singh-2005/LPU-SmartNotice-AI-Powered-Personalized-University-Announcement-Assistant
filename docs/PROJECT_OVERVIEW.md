# Project Overview — LPU SmartNotice

## 1. Abstract
Lovely Professional University (LPU) publishes thousands of university announcements annually across academic schedules, placement drives, examination seatings, fee deadlines, hostel notices, and cultural events. Due to the high volume, students frequently experience information overload, missing critical deadlines or attending incorrect venues.

**LPU SmartNotice** is an AI-powered personalized university announcement assistant that structures historical announcements, ranks notices based on student academic profiles, identifies room/timetable conflicts, and provides a grounded RAG chatbot to answer natural-language queries.

## 2. Research Objective
Investigate whether semantic understanding, structured information extraction, and rule-based personalized ranking can reduce irrelevant university announcements shown to students while preserving urgent, mandatory, and actionable notices.

## 3. Core Capabilities
- **Historical Search:** Hybrid semantic and exact keyword retrieval across 7,350+ notices.
- **AI Fact Extraction:** Gemini-powered extraction of categories, deadlines, rooms, target programs, and urgency levels.
- **Attachment Awareness:** Explicit tracking of referenced attachments whose internal contents are unavailable.
- **Grounded Q&A:** Grounded RAG chatbot providing cited evidence while explicitly communicating uncertainty.
- **Personalized Ranking:** Profile-based relevance scoring with global safety overrides for urgent notices.
- **Timetable Conflict Detection:** Room normalization and schedule collision analysis.

## 4. System Boundaries & Constraints
- The dataset operates on local historical records without needing live credentials or internal university database connections.
- Raw dataset files are treated as immutable source truth.
- Attachment files (PDFs/spreadsheets) are flagged as external attachments; missing contents trigger clear evidence incompleteness warnings rather than hallucinated text.

---
*Return to [Root README](../README.md)*
