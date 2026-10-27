# Room & Timetable Impact Service — LPU SmartNotice

## 1. Overview
Announcements regarding venue changes, mid-term exam room seating, or class suspensions directly impact a student's daily timetable. The `RoomImpactService` compares announcement room/date metadata against scheduled student classes.

## 2. Room String Normalization
University notices format room numbers inconsistently (e.g. `34-105`, `Block 34, Room 105`, `Block-34, 105`).

The service normalizes all formats into standard `Block-Room` keys:
- `Block 34, Room 105` $\rightarrow$ `34-105`
- `Rooms 34-101 to 34-110` $\rightarrow$ `['34-101', '34-102', '34-103', '34-104', '34-105', ..., '34-110']`

## 3. Impact Status Taxonomy
| Status | Condition | Example Output |
| :--- | :--- | :--- |
| `CONFIRMED_MATCH` | Announcement specifically mentions student's exact room and contains impact words (`cancelled`, `exam`, `relocated`). | *"Confirmed match: Exam scheduled in Room 34-105 affecting CSE301."* |
| `POTENTIAL_IMPACT` | Announcement references the student's building/block or room range. | *"Potential impact: Block 34 classes suspended during exam hours."* |
| `NO_MATCH` | No room or building overlap detected. | *"No room overlap detected for class in 32-201."* |
| `UNCERTAIN_DATA` | Announcement text is ambiguous regarding specific rooms. | *"Insufficient room details to determine impact."* |

---
*Return to [Root README](../README.md)*
