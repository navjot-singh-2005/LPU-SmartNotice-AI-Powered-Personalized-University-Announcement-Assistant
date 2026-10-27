# Architecture Decisions & Tradeoffs — LPU SmartNotice

## 1. Grounded RAG vs Fine-Tuning LLM
- **Decision:** Use Grounded RAG with a persistent vector database instead of fine-tuning Gemini.
- **Rationale:** University announcements update daily. Fine-tuning an LLM on historical notices is expensive, slow, and cannot incorporate new announcements published today. RAG provides instant incremental indexing and strict citation provenance.

## 2. Rule-Based Personalization vs ML Learning-to-Rank (LTR)
- **Decision:** Implement a transparent rule-based scoring model for Version 1.0.
- **Rationale:** Rule-based models are easily explainable during university project vivas (students can see exactly why a notice received an 85% priority score). User feedback is logged to SQLite (`student_feedback` table) to enable training ML models in future versions.

## 3. Attachment Content Availability Policy
- **Decision:** Explicitly mark `attachment_content_available=False` for all historical notices.
- **Rationale:** The raw dataset contains attachment flags (`attachment_present=True`) and attachment file names, but no binary PDF/XLS files were provided. Pretending that attachment contents are known causes hallucinated exam rules. The system explicitly alerts users when key evidence resides inside an unavailable attachment.

## 4. Framework Minimization
- **Decision:** Avoid LangChain, LlamaIndex, React, or MCP frameworks.
- **Rationale:** Keeps the codebase clean, readable, modular, and easily explainable for beginners and technical reviewers.

---
*Return to [Root README](../README.md)*
