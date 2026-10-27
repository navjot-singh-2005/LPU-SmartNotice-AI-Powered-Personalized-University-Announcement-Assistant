import re
from typing import List, Dict, Any, Optional, Tuple
from app.models.student import TimetableEntry, ClassImpactResult
from app.models.announcement import RawAnnouncement, ExtractedAnnouncementMetadata
from app.core.logging_config import logger
from app.core.database import get_db_connection

def parse_time_to_minutes(time_str: str) -> Optional[int]:
    """Parse time string e.g. '09:00 AM', '9:30am', '14:30', '10:00' to minutes from midnight."""
    if not time_str or not time_str.strip():
        return None
    s = time_str.strip().upper()
    m_ampm = re.match(r"^(\d{1,2}):(\d{2})\s*(AM|PM)?$", s)
    if m_ampm:
        h = int(m_ampm.group(1))
        m = int(m_ampm.group(2))
        ampm = m_ampm.group(3)
        if ampm == "PM" and h < 12:
            h += 12
        elif ampm == "AM" and h == 12:
            h = 0
        return h * 60 + m
    m_h = re.match(r"^(\d{1,2})\s*(AM|PM)$", s)
    if m_h:
        h = int(m_h.group(1))
        ampm = m_h.group(2)
        if ampm == "PM" and h < 12:
            h += 12
        elif ampm == "AM" and h == 12:
            h = 0
        return h * 60
    return None

def times_overlap(start1_min: int, end1_min: int, start2_min: int, end2_min: int) -> bool:
    """Return True if two intervals overlap for a strictly non-zero duration."""
    return max(start1_min, start2_min) < min(end1_min, end2_min)

def extract_replacement_room(text: str) -> Optional[str]:
    """Detect explicit replacement or relocated room from circular text."""
    patterns = [
        r"(?:relocated|shifted|moved|transferred)\s+(?:to|in)\s+(?:room\s*)?(\d{1,2}-\d{3})",
        r"(?:replacement|alternate|new)\s+(?:room|venue)\s*(?:is|:)?\s*(\d{1,2}-\d{3})",
        r"(?:instead\s+of\s+\d{1,2}-\d{3}[^,\.]*,\s*(?:please\s+report\s+to|report\s+to|in)\s+(?:room\s*)?(\d{1,2}-\d{3}))"
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None

def extract_time_range_from_text(text: str) -> Tuple[Optional[int], Optional[int]]:
    """Extract a time range from announcement text, e.g. 'from 9 am to 2 pm' -> (540, 840) minutes."""
    pat = r'(?:from\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:to|-|till|until)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm))'
    m = re.search(pat, text, re.IGNORECASE)
    if m:
        t1, t2 = m.group(1).strip(), m.group(2).strip()
        s = parse_time_to_minutes(t1)
        e = parse_time_to_minutes(t2)
        if s is not None and e is not None and s < e:
            return s, e
    return None, None

class RoomImpactService:
    """Analyzes room numbers, ranges, and timetable overlap for student class impact."""

    def normalize_room_string(self, room_str: str) -> List[str]:
        """Extract standard block-room strings e.g. '34-105' from various input formats."""
        if not room_str:
            return []

        # Find patterns like 34-105 or Block 34, 105 or 34-101 to 34-110
        pattern_dash = r"\b(\d{1,2})-(\d{3})\b"
        matches = re.findall(pattern_dash, room_str)
        if matches:
            return [f"{block}-{room}" for block, room in matches]

        # Find pattern like Block 34 Room 105
        pattern_block_room = r"block\s*(\d{1,2})[^\d]*room\s*(\d{3})"
        matches_br = re.findall(pattern_block_room, room_str.lower())
        if matches_br:
            return [f"{block}-{room}" for block, room in matches_br]

        return [room_str.strip()]

    def parse_room_range(self, range_str: str) -> List[str]:
        """Expand room ranges like '34-101 to 34-105' or '34-101 to 105' or 'Block 34 Rooms 101 to 110'."""
        if not range_str:
            return []

        # Pattern 1: 34-101 to 34-110  (full form)
        range_pattern = r"(\d{1,2})-(\d{3})\s*(?:to|-|through)\s*(\d{1,2})-(\d{3})"
        match = re.search(range_pattern, range_str.lower())
        if match:
            b1, r1, b2, r2 = match.groups()
            if b1 == b2:
                try:
                    start_num = int(r1)
                    end_num = int(r2)
                    if start_num <= end_num and (end_num - start_num) <= 50:
                        return [f"{b1}-{num:03d}" for num in range(start_num, end_num + 1)]
                except ValueError:
                    pass

        # Pattern 2: 34-101 to 110  (short form, same block implied)
        short_pattern = r"(\d{1,2})-(\d{3})\s*(?:to|-|through)\s*(\d{3})\b"
        match2 = re.search(short_pattern, range_str.lower())
        if match2:
            b1, r1, r2 = match2.groups()
            try:
                start_num = int(r1)
                end_num = int(r2)
                if start_num <= end_num and (end_num - start_num) <= 50:
                    return [f"{b1}-{num:03d}" for num in range(start_num, end_num + 1)]
            except ValueError:
                pass

        # Pattern 3: Block 34 Rooms 101 to 110
        block_rooms_pattern = r"block\s*(\d{1,2})\s*rooms?\s*(\d{3})\s*(?:to|-|through)\s*(\d{3})"
        match3 = re.search(block_rooms_pattern, range_str.lower())
        if match3:
            b1, r1, r2 = match3.groups()
            try:
                start_num = int(r1)
                end_num = int(r2)
                if start_num <= end_num and (end_num - start_num) <= 50:
                    return [f"{b1}-{num:03d}" for num in range(start_num, end_num + 1)]
            except ValueError:
                pass

        return self.normalize_room_string(range_str)

    def check_timetable_conflict(
        self,
        entry: TimetableEntry,
        announcement: RawAnnouncement,
        metadata: Optional[ExtractedAnnouncementMetadata] = None
    ) -> ClassImpactResult:
        """Check if an announcement impacts a specific timetable entry with Red/Amber/Green indicators.
        
        Handles 4 conflict categories:
          1. Room match with impact keywords (RED)
          2. Exam/event overlap at same room & time (RED)
          3. Room closure/venue change/exemption
          4. Course code or subject mentioned in cancellation/rescheduling notice (RED)
        
        Prevents false positives:
          - Block-level only triggers on broad impact (all rooms, entire block, power cut, maintenance)
          - Notice time range checked against class time (morning class not flagged by afternoon event)
        """
        ann_text = f"{announcement.title} {announcement.full_content}".lower()

        # Extract affected rooms from metadata or text regex
        affected_rooms: List[str] = []
        if metadata:
            affected_rooms.extend(metadata.affected_rooms)
            if metadata.room:
                affected_rooms.extend(self.normalize_room_string(metadata.room))
            if metadata.room_range:
                affected_rooms.extend(self.parse_room_range(metadata.room_range))
            if metadata.location:
                affected_rooms.extend(self.normalize_room_string(metadata.location))

        if not affected_rooms:
            # Fallback to regex over announcement text
            affected_rooms = self.normalize_room_string(ann_text)
            if "range" in ann_text or "to" in ann_text:
                affected_rooms.extend(self.parse_room_range(ann_text))

        entry_rooms = self.normalize_room_string(entry.room)
        entry_room_clean = entry_rooms[0] if entry_rooms else entry.room.strip()

        # Extract building/block from entry room
        entry_block = ""
        block_match = re.search(r"(\d{1,2})", entry_room_clean)
        if block_match:
            entry_block = block_match.group(1)

        # 1. Check Explicit Room Exemptions
        exempted_rooms: List[str] = []
        if metadata and metadata.exempted_rooms:
            for er in metadata.exempted_rooms:
                exempted_rooms.extend(self.normalize_room_string(er))

        except_patterns = [
            r"(?:except|excluding|exempted|exemption for)\s*(?:room|rooms)?\s*(\d{1,2}-\d{3})",
            r"(?:except|excluding|exempted)\s*(?:in|for)?\s*(?:block\s*\d{1,2}\s*)?(?:room\s*)?(\d{1,2}-\d{3})"
        ]
        for pat in except_patterns:
            matches_ex = re.findall(pat, ann_text)
            for m in matches_ex:
                exempted_rooms.extend(self.normalize_room_string(m))

        # Check replacement room
        replacement_room = extract_replacement_room(ann_text)

        # Determine impact type
        impact_type = "GENERAL_ALERT"
        conflict_type = "ROOM_RESTRICTION"
        if any(w in ann_text for w in ["cancelled", "canceled", "suspended", "holiday", "closed", "non-teaching", "suspension"]):
            impact_type = "SUSPENSION"
            conflict_type = "ROOM_CLOSURE"
        elif any(w in ann_text for w in ["relocated", "shifted", "venue change", "moved to", "new room", "venue shift"]):
            impact_type = "VENUE_CHANGE"
            conflict_type = "VENUE_CHANGE"
        elif any(w in ann_text for w in ["exam", "examination", "viva", "seating plan", "mid-term", "end-term"]):
            impact_type = "EXAM_DUTY"
            conflict_type = "EXAM_OVERLAP"
        elif any(w in ann_text for w in ["rescheduled", "postponed", "timing changed"]):
            impact_type = "RESCHEDULED"
            conflict_type = "RESCHEDULED"

        # Check for attachment-dependent room instructions
        att_phrases = ["refer attachment", "refer to attached", "attached list", "attached herewith", "see attachment", "attachment for rooms", "attached pdf", "attached excel", "check attached"]
        is_attachment_dependent = False
        if metadata and getattr(metadata, "is_attachment_dependent", False):
            is_attachment_dependent = True
        elif any(p in ann_text for p in att_phrases):
            is_attachment_dependent = True

        # Extract notice time range for time overlap checks
        notice_start_min, notice_end_min = extract_time_range_from_text(ann_text)
        entry_start_min = parse_time_to_minutes(entry.start_time)
        entry_end_min = parse_time_to_minutes(entry.end_time)

        # Helper: does the notice time (if specified) overlap with entry time?
        def notice_time_overlaps_entry() -> bool:
            if notice_start_min is None or notice_end_min is None:
                return True  # No time specified in notice → assume possible overlap
            if entry_start_min is None or entry_end_min is None:
                return True  # Can't parse entry time → assume possible overlap
            return times_overlap(entry_start_min, entry_end_min, notice_start_min, notice_end_min)

        # Check if room is explicitly exempted
        if any(ex.lower() == entry_room_clean.lower() for ex in exempted_rooms):
            return ClassImpactResult(
                entry=entry,
                affected=False,
                status="EXEMPTED",
                indicator_color="GREEN",
                conflict_type="ROOM_EXEMPTION",
                impact_type="NONE",
                announcement_id=announcement.announcement_id,
                announcement_title=announcement.title,
                evidence_text=f"Explicit exemption found matching Room {entry.room}",
                explanation=f"🛡️ Room Exempted: Room {entry.room} ({entry.course_code}) is explicitly exempted from this circular restriction."
            )

        # 2. Exact Room Match Check
        room_match = False
        for room in affected_rooms:
            if room.lower() == entry_room_clean.lower():
                room_match = True
                break

        # 3. Course Code / Subject Match (Category 4: cancellation/rescheduling by course)
        course_match = False
        if entry.course_code and len(entry.course_code) >= 3:
            if re.search(r'\b' + re.escape(entry.course_code.lower()) + r'\b', ann_text):
                course_match = True
        if not course_match and entry.course_name and len(entry.course_name) >= 4:
            if re.search(r'\b' + re.escape(entry.course_name.lower()) + r'\b', ann_text):
                course_match = True

        # 4. Block/Building Level Match — only for broad building-wide impacts
        block_match_flag = False
        broad_block_keywords = ["all rooms", "entire block", "classes suspended", "power cut", "maintenance in block",
                                "sanitization", "fumigation", "water supply", "electricity", "fire drill"]
        if entry_block and (f"block {entry_block}" in ann_text or f"block-{entry_block}" in ann_text):
            # Only flag building-level if the notice has broad impact language
            if any(kw in ann_text for kw in broad_block_keywords):
                block_match_flag = True
            elif is_attachment_dependent:
                block_match_flag = True
            # If the notice mentions a SPECIFIC different room in the same block (e.g. "venue: block 33-214"),
            # do NOT flag it as a building-level impact for room 33-301
            elif not affected_rooms or any(r.lower() == entry_room_clean.lower() for r in affected_rooms):
                block_match_flag = True

        # No match on any dimension → GREEN
        if not room_match and not block_match_flag and not course_match:
            return ClassImpactResult(
                entry=entry,
                affected=False,
                status="NO_MATCH",
                indicator_color="GREEN",
                conflict_type="NONE",
                impact_type="NONE",
                explanation=f"✅ No conflict detected: Room {entry.room} schedule verified clear."
            )

        # Course code match with cancellation/rescheduling keywords → RED
        cancel_keywords = ["cancelled", "canceled", "suspended", "rescheduled", "postponed", "exam", "examination"]
        if course_match and any(kw in ann_text for kw in cancel_keywords):
            if notice_time_overlaps_entry():
                return ClassImpactResult(
                    entry=entry,
                    affected=True,
                    status="CONFIRMED_MATCH",
                    indicator_color="RED",
                    conflict_type=conflict_type,
                    impact_type=impact_type,
                    announcement_id=announcement.announcement_id,
                    announcement_title=announcement.title,
                    replacement_room=replacement_room,
                    evidence_text=f"Course code match: {entry.course_code} mentioned in {impact_type} notice",
                    explanation=f"🚨 Confirmed Conflict: Announcement mentions course {entry.course_code} with {impact_type} impact."
                )

        # If block matches and notice states room details are in attachment → AMBER
        if block_match_flag and not room_match and is_attachment_dependent:
            return ClassImpactResult(
                entry=entry,
                affected=True,
                status="ATTACHMENT_DEPENDENT",
                indicator_color="AMBER",
                conflict_type="ATTACHMENT_DEPENDENT",
                impact_type=impact_type,
                announcement_id=announcement.announcement_id,
                announcement_title=announcement.title,
                evidence_text="Notice references attachment for detailed room schedule",
                explanation=f"⚠️ Needs Verification: Circular affects Block {entry_block}, but individual room schedules are in an unretrieved attachment. Please verify."
            )

        # Room match found, check impact
        impact_words = ["cancelled", "canceled", "suspended", "postponed", "relocated", "moved", "exam", "holiday",
                        "exempted", "closed", "rescheduled"]
        has_impact_word = any(w in ann_text for w in impact_words)

        if room_match:
            if has_impact_word and notice_time_overlaps_entry():
                repl_note = f" (Replacement Venue: Room {replacement_room})" if replacement_room else ""
                return ClassImpactResult(
                    entry=entry,
                    affected=True,
                    status="CONFIRMED_MATCH",
                    indicator_color="RED",
                    conflict_type=conflict_type,
                    impact_type=impact_type,
                    announcement_id=announcement.announcement_id,
                    announcement_title=announcement.title,
                    replacement_room=replacement_room,
                    evidence_text=f"Direct room match: Room {entry.room} with {impact_type} impact{repl_note}",
                    explanation=f"🚨 Confirmed Conflict: Announcement impacts Room {entry.room} ({entry.course_code}) [{impact_type}].{repl_note}"
                )
            else:
                return ClassImpactResult(
                    entry=entry,
                    affected=True,
                    status="POTENTIAL_IMPACT",
                    indicator_color="AMBER",
                    conflict_type="POTENTIAL_IMPACT",
                    impact_type=impact_type,
                    announcement_id=announcement.announcement_id,
                    announcement_title=announcement.title,
                    evidence_text=f"Notice references Room {entry.room}",
                    explanation=f"⚠️ Needs Verification: Notice references Room {entry.room}; check circular details to confirm applicability."
                )

        if block_match_flag:
            return ClassImpactResult(
                entry=entry,
                affected=True,
                status="POTENTIAL_IMPACT",
                indicator_color="AMBER",
                conflict_type="POTENTIAL_IMPACT",
                impact_type=impact_type,
                announcement_id=announcement.announcement_id,
                announcement_title=announcement.title,
                evidence_text=f"Notice affects Block {entry_block}",
                explanation=f"⚠️ Building Impact: Announcement affects Block {entry_block} where class {entry.course_code} ({entry.room}) is held."
            )

        # Course match without strong cancel keywords → AMBER
        if course_match:
            return ClassImpactResult(
                entry=entry,
                affected=True,
                status="POTENTIAL_IMPACT",
                indicator_color="AMBER",
                conflict_type="POTENTIAL_IMPACT",
                impact_type=impact_type,
                announcement_id=announcement.announcement_id,
                announcement_title=announcement.title,
                evidence_text=f"Course {entry.course_code} mentioned in notice",
                explanation=f"⚠️ Needs Verification: Notice references course {entry.course_code}; check circular details."
            )

        return ClassImpactResult(
            entry=entry,
            affected=False,
            status="UNCERTAIN_DATA",
            indicator_color="AMBER",
            conflict_type="NONE",
            impact_type="NONE",
            explanation="⚠️ Insufficient room or date details in announcement to determine class impact."
        )

    def get_sample_timetable(self, student_id: str) -> List[TimetableEntry]:
        """Generate sample synthetic timetable entries for testing/demo."""
        return [
            TimetableEntry(
                entry_id="TT-101",
                student_id=student_id,
                day_or_date="Monday",
                start_time="09:00 AM",
                end_time="10:00 AM",
                course_code="CSE301",
                course_name="Data Structures & Algorithms",
                room="34-105",
                building="Block 34",
                faculty="Dr. Sharma",
                section="K21AB",
                effective_date="2026-10-15"
            ),
            TimetableEntry(
                entry_id="TT-102",
                student_id=student_id,
                day_or_date="Monday",
                start_time="11:00 AM",
                end_time="12:00 PM",
                course_code="INT219",
                course_name="Front End Web Development",
                room="34-108",
                building="Block 34",
                faculty="Prof. Gupta",
                section="K21AB",
                effective_date="2026-10-15"
            ),
            TimetableEntry(
                entry_id="TT-103",
                student_id=student_id,
                day_or_date="Tuesday",
                start_time="02:00 PM",
                end_time="03:00 PM",
                course_code="CSE316",
                course_name="Operating Systems",
                room="34-204",
                building="Block 34",
                faculty="Dr. Verma",
                section="K21AB",
                effective_date="2026-10-16"
            ),
            TimetableEntry(
                entry_id="TT-104",
                student_id=student_id,
                day_or_date="Wednesday",
                start_time="10:00 AM",
                end_time="11:00 AM",
                course_code="MTH401",
                course_name="Discrete Mathematics",
                room="33-301",
                building="Block 33",
                faculty="Dr. Rao",
                section="K21AB",
                effective_date="2026-10-17"
            )
        ]

    def get_student_timetable(self, student_id: str) -> List[TimetableEntry]:
        """Fetch student timetable from persistent SQLite database, falling back to sample for STU-101."""
        from app.core.database import get_db_connection
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT entry_id, student_id, day_or_date, start_time, end_time,
                       course_code, course_name, room, building, faculty, section, effective_date
                FROM student_timetable
                WHERE student_id = ?
                ORDER BY day_or_date ASC, start_time ASC
            """, (student_id,))
            rows = c.fetchall()
            if rows:
                return [
                    TimetableEntry(
                        entry_id=r["entry_id"],
                        student_id=r["student_id"],
                        day_or_date=r["day_or_date"],
                        start_time=r["start_time"],
                        end_time=r["end_time"],
                        course_code=r["course_code"],
                        course_name=r["course_name"],
                        room=r["room"],
                        building=r["building"],
                        faculty=r["faculty"],
                        section=r["section"],
                        effective_date=r["effective_date"]
                    )
                    for r in rows
                ]
            if student_id == "STU-101":
                return self.get_sample_timetable("STU-101")
            return []
        finally:
            conn.close()

    def detect_internal_timetable_conflicts(self, entries: List[TimetableEntry]) -> Dict[str, Tuple[TimetableEntry, str]]:
        """Identify internal time overlaps between pairs of classes on the same day for a student."""
        conflicts: Dict[str, Tuple[TimetableEntry, str]] = {}
        n = len(entries)
        for i in range(n):
            e1 = entries[i]
            s1 = parse_time_to_minutes(e1.start_time)
            end1 = parse_time_to_minutes(e1.end_time)
            if s1 is None or end1 is None or s1 >= end1:
                continue

            for j in range(i + 1, n):
                e2 = entries[j]
                if e1.day_or_date.strip().lower() != e2.day_or_date.strip().lower():
                    continue

                s2 = parse_time_to_minutes(e2.start_time)
                end2 = parse_time_to_minutes(e2.end_time)
                if s2 is None or end2 is None or s2 >= end2:
                    continue

                if times_overlap(s1, end1, s2, end2):
                    msg1 = f"🚨 Overlaps with {e2.course_code} ({e2.course_name}) [{e2.start_time} - {e2.end_time}, Room {e2.room}]"
                    msg2 = f"🚨 Overlaps with {e1.course_code} ({e1.course_name}) [{e1.start_time} - {e1.end_time}, Room {e1.room}]"
                    conflicts[e1.entry_id] = (e2, msg1)
                    conflicts[e2.entry_id] = (e1, msg2)

        return conflicts

    def evaluate_student_timetable(
        self,
        student_id: str,
        announcements: List[RawAnnouncement],
        metadata_map: Optional[Dict[str, ExtractedAnnouncementMetadata]] = None
    ) -> List[ClassImpactResult]:
        """Comprehensive evaluation of student timetable: internal overlap check + university circular conflict detection."""
        entries = self.get_student_timetable(student_id)
        if not entries:
            return []

        # 1. Detect internal conflicts
        internal_conflicts = self.detect_internal_timetable_conflicts(entries)

        results: List[ClassImpactResult] = []

        for entry in entries:
            # Check internal conflict first
            if entry.entry_id in internal_conflicts:
                other_entry, exp = internal_conflicts[entry.entry_id]
                results.append(
                    ClassImpactResult(
                        entry=entry,
                        affected=True,
                        status="RED_CONFLICT",
                        indicator_color="RED",
                        conflict_type="INTERNAL_OVERLAP",
                        impact_type="SCHEDULE_OVERLAP",
                        conflicting_entry_id=other_entry.entry_id,
                        conflicting_entry_title=f"{other_entry.course_code} ({other_entry.start_time} - {other_entry.end_time}, Room {other_entry.room})",
                        explanation=f"🚨 Timetable Conflict: Class {entry.course_code} ({entry.start_time} - {entry.end_time}) on {entry.day_or_date} overlaps with {other_entry.course_code} ({other_entry.start_time} - {other_entry.end_time}, Room {other_entry.room})."
                    )
                )
                continue

            # Evaluate against announcements
            best_impact: Optional[ClassImpactResult] = None

            for ann in announcements:
                cached_meta = metadata_map.get(ann.announcement_id) if metadata_map else None
                imp = self.check_timetable_conflict(entry, ann, cached_meta)

                if imp.indicator_color == "RED":
                    # Confirmed RED conflict found - prioritize this
                    best_impact = imp
                    break
                elif imp.indicator_color == "AMBER":
                    if best_impact is None or best_impact.indicator_color == "GREEN":
                        best_impact = imp
                elif imp.status == "EXEMPTED":
                    if best_impact is None or best_impact.indicator_color == "GREEN":
                        best_impact = imp

            if best_impact is not None:
                results.append(best_impact)
            else:
                # Default GREEN: no conflict detected
                results.append(
                    ClassImpactResult(
                        entry=entry,
                        affected=False,
                        status="GREEN_CLEAR",
                        indicator_color="GREEN",
                        conflict_type="NONE",
                        impact_type="NONE",
                        explanation=f"✅ No conflict detected: Room {entry.room} and scheduled hours verified clear against active university circulars."
                    )
                )

        return results
