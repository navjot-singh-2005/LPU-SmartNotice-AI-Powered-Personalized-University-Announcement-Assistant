# Personalization & Ranking Engine — LPU SmartNotice

## 1. Overview
Generic announcement feeds display all notices chronologically, forcing students to wade through hundreds of irrelevant posts. LPU SmartNotice implements a transparent, rule-based personalization engine before any machine learning.

## 2. Personal Priority Formula
Each announcement $A$ is scored for a student profile $S$ using a weighted linear model:

$$\text{Priority}(S, A) = w_1 Y + w_2 D + w_3 I + w_4 U + w_5 G$$

Where:
- $Y$ = Year match score ($1.0$ if student year $\in$ target_year, else $0.1$).
- $D$ = Department / Program match score ($1.0$ if program matches, else $0.2$).
- $I$ = Interest similarity score ($0.0$ to $1.0$ based on keyword overlap).
- $U$ = Urgency level score ($1.0$ for `CRITICAL`/`HIGH`, $0.6$ for `MEDIUM`, $0.3$ for `LOW`).
- $G$ = Global importance score ($1.0$ for `HIGH`, $0.6$ for `MEDIUM`, $0.3$ for `LOW`).

### Configurable Weights
- $w_1$ (Year): `0.25`
- $w_2$ (Dept/Program): `0.20`
- $w_3$ (Interests): `0.25`
- $w_4$ (Urgency): `0.15`
- $w_5$ (Global Importance): `0.15`

## 3. Global Safety Override Rules
Critical university-wide notices (e.g. natural emergency, fee deadline change, Chancellor address) must never be suppressed simply because interest similarity is low.

**Override Rule:** If `global_importance == HIGH` or `urgency == CRITICAL`, the personal priority score is guaranteed to be at least `0.85` ($85\%$).

## 4. Explanation Generation
Every item in the personalized feed includes a human-readable priority explanation badge (e.g., `"Priority: 92% • Targeted for Year 3 B.Tech CSE • Matches your interests (AI/ML)"`).

---
*Return to [Root README](../README.md)*
