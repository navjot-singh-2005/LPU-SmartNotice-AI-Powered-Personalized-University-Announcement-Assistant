// LPU SmartNotice Frontend Application Logic

let activeStudentId = "STU-101";
let demoStudents = [];
let currentPage = 1;
let previousTabId = "feedTab";
let currentActiveNoticeId = null;

document.addEventListener("DOMContentLoaded", () => {
    loadStudents();
    loadHealthDashboard();
    loadUmsStatus();

    // Support deep-linking to notices via URL hash: #/notice/{id}
    window.addEventListener("hashchange", handleHashRouting);
    if (window.location.hash.startsWith("#/notice/")) {
        handleHashRouting();
    }
});

function handleHashRouting() {
    const hash = window.location.hash;
    if (hash.startsWith("#/notice/")) {
        const noticeId = decodeURIComponent(hash.replace("#/notice/", "").trim());
        if (noticeId) {
            viewAnnouncement(noticeId);
        }
    }
}

function toggleMobileSidebar(force) {
    const sidebar = document.querySelector(".sidebar");
    const overlay = document.getElementById("sidebarOverlay");
    if (!sidebar) return;
    const shouldOpen = force !== undefined ? force : !sidebar.classList.contains("open");
    if (shouldOpen) {
        sidebar.classList.add("open");
        if (overlay) overlay.classList.add("active");
    } else {
        sidebar.classList.remove("open");
        if (overlay) overlay.classList.remove("active");
    }
}

function switchTab(tabId, evt) {
    toggleMobileSidebar(false);
    if (tabId !== "noticeDetailTab") {
        previousTabId = tabId;
        if (window.location.hash.startsWith("#/notice/")) {
            history.pushState(null, "", window.location.pathname + window.location.search);
        }
    }

    document.querySelectorAll(".tab-content").forEach(el => el.classList.remove("active"));
    document.querySelectorAll(".nav-item").forEach(el => el.classList.remove("active"));

    const target = document.getElementById(tabId);
    if (target) target.classList.add("active");
    if (evt && evt.currentTarget) evt.currentTarget.classList.add("active");

    if (tabId === "feedTab") loadPersonalizedFeed();
    if (tabId === "timetableTab") loadAffectedClasses();
    if (tabId === "healthTab") loadHealthDashboard();
}

function returnFromNoticeDetail() {
    switchTab(previousTabId || "feedTab");
    window.scrollTo({ top: 0, behavior: "smooth" });
}

function copyCurrentNoticeLink() {
    if (!currentActiveNoticeId) return;
    const url = window.location.origin + window.location.pathname + "#/notice/" + encodeURIComponent(currentActiveNoticeId);
    navigator.clipboard.writeText(url).then(() => {
        const btn = document.getElementById("btnCopyNoticeLink");
        if (btn) {
            const original = btn.innerHTML;
            btn.innerHTML = "<span>✅</span> Copied Direct Link!";
            setTimeout(() => { btn.innerHTML = original; }, 2500);
        }
    }).catch(() => {
        prompt("Direct notice URL:", url);
    });
}

async function loadStudents(preferredId) {
    try {
        const res = await fetch("/api/v1/students");
        if (!res.ok) throw new Error("Failed to load students");
        demoStudents = await res.json();

        const select = document.getElementById("studentSelector");
        select.innerHTML = "";
        demoStudents.forEach(stu => {
            const opt = document.createElement("option");
            opt.value = stu.student_id;
            opt.textContent = `${stu.name} (${stu.program})`;
            select.appendChild(opt);
        });

        if (demoStudents.length > 0) {
            if (preferredId && demoStudents.some(s => s.student_id === preferredId)) {
                activeStudentId = preferredId;
            } else if (!demoStudents.some(s => s.student_id === activeStudentId)) {
                activeStudentId = demoStudents[0].student_id;
            }
            select.value = activeStudentId;
            updateStudentCard();
            loadPersonalizedFeed();
        }
    } catch (e) {
        console.error("Error loading student profiles:", e);
    }
}

function onStudentChange() {
    activeStudentId = document.getElementById("studentSelector").value;
    updateStudentCard();
    loadPersonalizedFeed();
}

function updateStudentCard() {
    const student = demoStudents.find(s => s.student_id === activeStudentId);
    if (student) {
        const emailLine = student.email ? `<div style="font-size:11.5px; color:#94a3b8; margin-top:2px;">📧 ${escapeHtml(student.email)}</div>` : '';
        const sectionText = student.section ? ` • Sec: ${escapeHtml(student.section)}` : '';
        const careerText = student.career_goal ? `<div style="font-size:11.5px; color:#a5b4fc; margin-top:3px;">🎯 Goal: ${escapeHtml(student.career_goal)}</div>` : '';
        const interestsList = (student.interests && student.interests.length > 0) ? student.interests.join(", ") : "None specified";

        document.getElementById("studentDetails").innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                <div>
                    <strong>Year ${student.year} | Sem ${student.semester}${sectionText}</strong>
                    ${emailLine}
                </div>
                <button type="button" class="btn-student-action" onclick="openEditStudentModal('${student.student_id}')" title="Edit this profile">✏️ Edit</button>
            </div>
            <div style="margin-top:6px; font-size:12px; color:var(--text-secondary); line-height:1.4;">
                <div>Dept: <span style="color:#cbd5e1;">${escapeHtml(student.department)}</span></div>
                <div>Interests: <span style="color:#cbd5e1;">${escapeHtml(interestsList)}</span></div>
                ${careerText}
            </div>
        `;
    }
}

function parseTimeToMinutesJS(timeStr) {
    if (!timeStr) return null;
    let s = timeStr.trim().toUpperCase();
    let isPM = s.includes("PM");
    let isAM = s.includes("AM");
    s = s.replace("AM", "").replace("PM", "").trim();
    const parts = s.split(":");
    if (parts.length < 2) return null;
    let h = parseInt(parts[0], 10);
    let m = parseInt(parts[1], 10);
    if (isNaN(h) || isNaN(m)) return null;
    if (isPM && h < 12) h += 12;
    if (isAM && h === 12) h = 0;
    return h * 60 + m;
}

function timesOverlapJS(s1, e1, s2, e2) {
    return Math.max(s1, s2) < Math.min(e1, e2);
}

function updateModalTimetableCount() {
    const container = document.getElementById("timetableRowsContainer");
    const countBadge = document.getElementById("ttModalCountBadge");
    if (!container || !countBadge) return;
    const count = container.querySelectorAll(".timetable-row-item").length;
    countBadge.textContent = `${count} ${count === 1 ? 'class' : 'classes'}`;
}

function addTimetableRow(entry = null) {
    const container = document.getElementById("timetableRowsContainer");
    if (!container) return;

    const rowId = 'tt-row-' + Math.random().toString(36).substring(2, 9);
    const day = entry ? (entry.day_or_date || 'Monday') : 'Monday';
    const start = entry ? (entry.start_time || '09:00 AM') : '09:00 AM';
    const end = entry ? (entry.end_time || '10:00 AM') : '10:00 AM';
    const code = entry ? (entry.course_code || '') : '';
    const name = entry ? (entry.course_name || '') : '';
    const room = entry ? (entry.room || '') : '';
    const building = entry ? (entry.building || 'Block 34') : 'Block 34';
    const faculty = entry ? (entry.faculty || '') : '';
    const section = entry ? (entry.section || '') : '';
    const effDate = entry ? (entry.effective_date || '') : '';
    const entryId = entry ? (entry.entry_id || '') : '';

    const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
    const dayOptions = days.map(d => `<option value="${d}" ${d.toLowerCase() === day.toLowerCase() ? 'selected' : ''}>${d}</option>`).join("");

    const rowEl = document.createElement("div");
    rowEl.className = "timetable-row-item";
    rowEl.id = rowId;
    rowEl.dataset.entryId = entryId;
    rowEl.innerHTML = `
        <div style="display: grid; grid-template-columns: 115px 95px 95px 95px 1fr 85px 36px; gap: 6px; align-items: center;">
            <select class="tt-day tt-input-field" onchange="validateModalTimetableConflicts()">${dayOptions}</select>
            <input type="text" class="tt-start tt-input-field" required placeholder="09:00 AM" value="${escapeHtml(start)}" oninput="validateModalTimetableConflicts()">
            <input type="text" class="tt-end tt-input-field" required placeholder="10:00 AM" value="${escapeHtml(end)}" oninput="validateModalTimetableConflicts()">
            <input type="text" class="tt-code tt-input-field" required placeholder="e.g. CSE301" value="${escapeHtml(code)}">
            <input type="text" class="tt-name tt-input-field" required placeholder="e.g. Data Structures" value="${escapeHtml(name)}">
            <input type="text" class="tt-room tt-input-field" required placeholder="e.g. 34-105" value="${escapeHtml(room)}">
            <button type="button" class="btn-remove-tt" onclick="removeTimetableRow(this)" title="Remove class">🗑️</button>
        </div>
        <div style="display: grid; grid-template-columns: 100px 1fr 100px 130px; gap: 6px; margin-top: 6px;">
            <input type="text" class="tt-building tt-input-field" placeholder="Building (e.g. Block 34)" value="${escapeHtml(building)}" style="font-size: 11px;">
            <input type="text" class="tt-faculty tt-input-field" placeholder="Instructor / Faculty (optional)" value="${escapeHtml(faculty)}" style="font-size: 11px;">
            <input type="text" class="tt-sec tt-input-field" placeholder="Section (optional)" value="${escapeHtml(section)}" style="font-size: 11px;">
            <input type="text" class="tt-eff tt-input-field" placeholder="Effective Date (optional)" value="${escapeHtml(effDate)}" style="font-size: 11px;">
        </div>
    `;

    container.appendChild(rowEl);
    updateModalTimetableCount();
    validateModalTimetableConflicts();
}

function removeTimetableRow(btn) {
    const row = btn.closest(".timetable-row-item");
    if (row) {
        row.remove();
        updateModalTimetableCount();
        validateModalTimetableConflicts();
    }
}

function validateModalTimetableConflicts() {
    const alertBox = document.getElementById("modalTimetableConflictAlert");
    const container = document.getElementById("timetableRowsContainer");
    if (!container || !alertBox) return true;

    const rows = container.querySelectorAll(".timetable-row-item");
    rows.forEach(r => r.classList.remove("tt-row-conflict"));
    alertBox.style.display = "none";
    alertBox.innerHTML = "";

    const entries = [];
    for (const r of rows) {
        const day = r.querySelector(".tt-day")?.value?.trim() || "";
        const start = r.querySelector(".tt-start")?.value?.trim() || "";
        const end = r.querySelector(".tt-end")?.value?.trim() || "";
        const code = r.querySelector(".tt-code")?.value?.trim() || "";
        const sMin = parseTimeToMinutesJS(start);
        const eMin = parseTimeToMinutesJS(end);

        if (start && end && sMin !== null && eMin !== null && sMin >= eMin) {
            r.classList.add("tt-row-conflict");
            alertBox.style.display = "block";
            alertBox.innerHTML = `⚠️ Start time (${escapeHtml(start)}) must be earlier than end time (${escapeHtml(end)}) for class ${escapeHtml(code || 'row')}.`;
            return false;
        }

        entries.push({ rowEl: r, day, start, end, code, sMin, eMin });
    }

    // Check pairwise overlap on same day — warn but allow saving
    let hasOverlap = false;
    for (let i = 0; i < entries.length; i++) {
        const e1 = entries[i];
        if (e1.sMin === null || e1.eMin === null) continue;

        for (let j = i + 1; j < entries.length; j++) {
            const e2 = entries[j];
            if (e2.sMin === null || e2.eMin === null) continue;

            if (e1.day.toLowerCase() === e2.day.toLowerCase() && timesOverlapJS(e1.sMin, e1.eMin, e2.sMin, e2.eMin)) {
                e1.rowEl.classList.add("tt-row-conflict");
                e2.rowEl.classList.add("tt-row-conflict");
                alertBox.style.display = "block";
                alertBox.style.background = "rgba(251, 191, 36, 0.15)";
                alertBox.style.border = "1px solid rgba(251, 191, 36, 0.4)";
                alertBox.style.color = "#fbbf24";
                alertBox.innerHTML = `⚠️ <strong>Warning:</strong> Classes overlap on ${escapeHtml(e1.day)}! "${escapeHtml(e1.code || 'Class 1')}" (${escapeHtml(e1.start)} - ${escapeHtml(e1.end)}) overlaps with "${escapeHtml(e2.code || 'Class 2')}" (${escapeHtml(e2.start)} - ${escapeHtml(e2.end)}). Both will be saved and highlighted in <strong style="color:#ef4444">RED</strong> as a confirmed conflict.`;
                hasOverlap = true;
            }
        }
    }

    return hasOverlap ? "warning" : true;
}

function openAddStudentModal() {
    const modal = document.getElementById("studentModal");
    if (!modal) return;
    document.getElementById("studentModalTitle").textContent = "Add Student Profile";
    document.getElementById("studentModalIcon").textContent = "➕";
    document.getElementById("studentFormMode").value = "add";

    const idInput = document.getElementById("stuInputId");
    idInput.readOnly = false;
    idInput.style.opacity = "1";
    idInput.style.cursor = "auto";
    idInput.value = "";

    document.getElementById("stuInputName").value = "";
    document.getElementById("stuInputEmail").value = "";
    document.getElementById("stuInputSection").value = "";
    document.getElementById("stuInputProgram").value = "";
    document.getElementById("stuInputDepartment").value = "";
    document.getElementById("stuInputSchool").value = "";
    document.getElementById("stuInputYear").value = "1";
    document.getElementById("stuInputSemester").value = "1";
    document.getElementById("stuInputInterests").value = "";
    document.getElementById("stuInputCareer").value = "";

    const alertBox = document.getElementById("studentModalAlert");
    if (alertBox) {
        alertBox.style.display = "none";
        alertBox.innerHTML = "";
    }
    const conflictAlert = document.getElementById("modalTimetableConflictAlert");
    if (conflictAlert) {
        conflictAlert.style.display = "none";
        conflictAlert.innerHTML = "";
    }

    // Reset timetable rows and add 1 default row
    const ttContainer = document.getElementById("timetableRowsContainer");
    if (ttContainer) {
        ttContainer.innerHTML = "";
        addTimetableRow();
    }

    const btnText = document.getElementById("btnSaveStudentText");
    if (btnText) btnText.textContent = "Save Student Profile";
    const btn = document.getElementById("btnSaveStudent");
    if (btn) btn.disabled = false;

    modal.style.display = "flex";
}

async function openEditStudentModal(studentId) {
    const targetId = studentId || activeStudentId;
    const student = demoStudents.find(s => s.student_id === targetId);
    if (!student) {
        alert("Student profile not found.");
        return;
    }

    const modal = document.getElementById("studentModal");
    if (!modal) return;
    document.getElementById("studentModalTitle").textContent = `Edit Profile: ${student.name} (${student.student_id})`;
    document.getElementById("studentModalIcon").textContent = "✏️";
    document.getElementById("studentFormMode").value = "edit";

    const idInput = document.getElementById("stuInputId");
    idInput.value = student.student_id;
    idInput.readOnly = true;
    idInput.style.opacity = "0.7";
    idInput.style.cursor = "not-allowed";

    document.getElementById("stuInputName").value = student.name || "";
    document.getElementById("stuInputEmail").value = student.email || "";
    document.getElementById("stuInputSection").value = student.section || "";
    document.getElementById("stuInputProgram").value = student.program || "";
    document.getElementById("stuInputDepartment").value = student.department || "";
    document.getElementById("stuInputSchool").value = student.school || "";
    document.getElementById("stuInputYear").value = student.year || 1;
    document.getElementById("stuInputSemester").value = student.semester || 1;
    document.getElementById("stuInputInterests").value = (student.interests || []).join(", ");
    document.getElementById("stuInputCareer").value = student.career_goal || "";

    const alertBox = document.getElementById("studentModalAlert");
    if (alertBox) {
        alertBox.style.display = "none";
        alertBox.innerHTML = "";
    }
    const conflictAlert = document.getElementById("modalTimetableConflictAlert");
    if (conflictAlert) {
        conflictAlert.style.display = "none";
        conflictAlert.innerHTML = "";
    }

    // Load student's timetable entries
    const ttContainer = document.getElementById("timetableRowsContainer");
    if (ttContainer) {
        ttContainer.innerHTML = `<div style="font-size: 12px; color: var(--text-secondary); padding: 8px;">Loading saved timetable...</div>`;
        try {
            const res = await fetch(`/api/v1/students/${encodeURIComponent(targetId)}/timetable`);
            if (res.ok) {
                const entries = await res.json();
                ttContainer.innerHTML = "";
                if (entries && entries.length > 0) {
                    entries.forEach(e => addTimetableRow(e));
                } else {
                    addTimetableRow();
                }
            } else {
                ttContainer.innerHTML = "";
                addTimetableRow();
            }
        } catch (e) {
            ttContainer.innerHTML = "";
            addTimetableRow();
        }
    }

    const btnText = document.getElementById("btnSaveStudentText");
    if (btnText) btnText.textContent = "Save Changes";
    const btn = document.getElementById("btnSaveStudent");
    if (btn) btn.disabled = false;

    modal.style.display = "flex";
}

function closeStudentModal() {
    const modal = document.getElementById("studentModal");
    if (modal) modal.style.display = "none";
    const alertBox = document.getElementById("studentModalAlert");
    if (alertBox) {
        alertBox.style.display = "none";
        alertBox.innerHTML = "";
    }
    const conflictAlert = document.getElementById("modalTimetableConflictAlert");
    if (conflictAlert) {
        conflictAlert.style.display = "none";
        conflictAlert.innerHTML = "";
    }
}

async function handleStudentFormSubmit(e) {
    e.preventDefault();
    const mode = document.getElementById("studentFormMode").value;
    const id = document.getElementById("stuInputId").value.trim();
    const name = document.getElementById("stuInputName").value.trim();
    const email = document.getElementById("stuInputEmail").value.trim();
    const section = document.getElementById("stuInputSection").value.trim();
    const program = document.getElementById("stuInputProgram").value.trim();
    const department = document.getElementById("stuInputDepartment").value.trim();
    const school = document.getElementById("stuInputSchool").value.trim();
    const year = parseInt(document.getElementById("stuInputYear").value, 10);
    const semester = parseInt(document.getElementById("stuInputSemester").value, 10);
    const interestsRaw = document.getElementById("stuInputInterests").value;
    const career = document.getElementById("stuInputCareer").value.trim();

    const alertBox = document.getElementById("studentModalAlert");
    alertBox.style.display = "none";
    alertBox.innerHTML = "";

    // Client-side validation for student fields
    if (!id || !name || !program || !department || !school) {
        alertBox.style.display = "block";
        alertBox.style.background = "rgba(244, 63, 94, 0.15)";
        alertBox.style.border = "1px solid rgba(244, 63, 94, 0.4)";
        alertBox.style.color = "#fda4af";
        alertBox.innerHTML = "⚠️ Please fill in all required student fields marked with *.";
        return;
    }

    if (email && !/^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/.test(email)) {
        alertBox.style.display = "block";
        alertBox.style.background = "rgba(244, 63, 94, 0.15)";
        alertBox.style.border = "1px solid rgba(244, 63, 94, 0.4)";
        alertBox.style.color = "#fda4af";
        alertBox.innerHTML = "⚠️ Please enter a valid email address (e.g. name@lpu.in).";
        return;
    }

    // Collect and validate timetable rows
    const ttRows = document.querySelectorAll("#timetableRowsContainer .timetable-row-item");
    const timetablePayload = [];

    for (let i = 0; i < ttRows.length; i++) {
        const r = ttRows[i];
        const day = r.querySelector(".tt-day")?.value?.trim() || "";
        const start = r.querySelector(".tt-start")?.value?.trim() || "";
        const end = r.querySelector(".tt-end")?.value?.trim() || "";
        const code = r.querySelector(".tt-code")?.value?.trim() || "";
        const cname = r.querySelector(".tt-name")?.value?.trim() || "";
        const room = r.querySelector(".tt-room")?.value?.trim() || "";
        const building = r.querySelector(".tt-building")?.value?.trim() || "Block 34";
        const faculty = r.querySelector(".tt-faculty")?.value?.trim() || null;
        const sec = r.querySelector(".tt-sec")?.value?.trim() || null;
        const effDate = r.querySelector(".tt-eff")?.value?.trim() || null;
        const entryId = r.dataset.entryId || null;

        // If completely empty row, ignore it
        if (!code && !cname && !room) continue;

        // If partially filled, validate
        if (!day || !start || !end || !code || !cname || !room) {
            alertBox.style.display = "block";
            alertBox.style.background = "rgba(244, 63, 94, 0.15)";
            alertBox.style.border = "1px solid rgba(244, 63, 94, 0.4)";
            alertBox.style.color = "#fda4af";
            alertBox.innerHTML = `⚠️ Timetable row #${i + 1}: Please provide Day, Start Time, End Time, Course Code, Subject Name, and Room.`;
            return;
        }

        const sMin = parseTimeToMinutesJS(start);
        const eMin = parseTimeToMinutesJS(end);
        if (sMin === null || eMin === null) {
            alertBox.style.display = "block";
            alertBox.style.background = "rgba(244, 63, 94, 0.15)";
            alertBox.style.border = "1px solid rgba(244, 63, 94, 0.4)";
            alertBox.style.color = "#fda4af";
            alertBox.innerHTML = `⚠️ Timetable row #${i + 1} (${escapeHtml(code)}): Invalid time format. Please use formats like "09:00 AM" or "09:00".`;
            return;
        }

        if (sMin >= eMin) {
            alertBox.style.display = "block";
            alertBox.style.background = "rgba(244, 63, 94, 0.15)";
            alertBox.style.border = "1px solid rgba(244, 63, 94, 0.4)";
            alertBox.style.color = "#fda4af";
            alertBox.innerHTML = `⚠️ Timetable row #${i + 1} (${escapeHtml(code)}): Start time (${escapeHtml(start)}) must be earlier than end time (${escapeHtml(end)}).`;
            return;
        }

        timetablePayload.push({
            entry_id: entryId,
            day_or_date: day,
            start_time: start,
            end_time: end,
            course_code: code,
            course_name: cname,
            room: room,
            building: building,
            faculty: faculty,
            section: sec,
            effective_date: effDate
        });
    }

    // Check for internal conflicts before saving (false = invalid time, "warning" = overlap allowed)
    const conflictCheck = validateModalTimetableConflicts();
    if (conflictCheck === false) {
        alertBox.style.display = "block";
        alertBox.style.background = "rgba(244, 63, 94, 0.15)";
        alertBox.style.border = "1px solid rgba(244, 63, 94, 0.4)";
        alertBox.style.color = "#fda4af";
        alertBox.innerHTML = "🚨 Please fix the invalid time range highlighted below before saving.";
        return;
    }

    const interests = interestsRaw.split(",").map(s => s.trim()).filter(Boolean);

    const payload = {
        name,
        email: email || null,
        section: section || null,
        program,
        department,
        school,
        year,
        semester,
        interests,
        career_goal: career || null,
        timetable: timetablePayload
    };

    const btn = document.getElementById("btnSaveStudent");
    const btnText = document.getElementById("btnSaveStudentText");
    btn.disabled = true;
    btnText.textContent = mode === "add" ? "Creating Profile..." : "Saving Changes...";

    try {
        let res;
        if (mode === "add") {
            payload.student_id = id;
            res = await fetch("/api/v1/students", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
        } else {
            res = await fetch(`/api/v1/students/${encodeURIComponent(id)}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
        }

        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || `Server returned status ${res.status}`);
        }

        // Success state
        alertBox.style.display = "block";
        alertBox.style.background = "rgba(16, 185, 129, 0.15)";
        alertBox.style.border = "1px solid rgba(16, 185, 129, 0.4)";
        alertBox.style.color = "#6ee7b7";
        alertBox.innerHTML = `✅ Successfully ${mode === "add" ? "created" : "updated"} student profile <strong>${escapeHtml(data.name)}</strong> (${escapeHtml(data.student_id)}) with ${timetablePayload.length} timetable ${timetablePayload.length === 1 ? 'class' : 'classes'}!`;

        setTimeout(async () => {
            closeStudentModal();
            await loadStudents(data.student_id);
            if (activeStudentId === data.student_id) {
                loadAffectedClasses();
            }
        }, 800);

    } catch (err) {
        alertBox.style.display = "block";
        alertBox.style.background = "rgba(244, 63, 94, 0.15)";
        alertBox.style.border = "1px solid rgba(244, 63, 94, 0.4)";
        alertBox.style.color = "#fda4af";
        alertBox.innerHTML = `⚠️ ${escapeHtml(err.message)}`;
        btn.disabled = false;
        btnText.textContent = mode === "add" ? "Save Student Profile" : "Save Changes";
    }
}

let currentFeedApplicability = "ALL";

function setFeedApplicability(tier, evt) {
    currentFeedApplicability = tier;
    document.querySelectorAll("#feedTierFilters .pill-btn").forEach(btn => btn.classList.remove("active"));
    if (evt && evt.currentTarget) evt.currentTarget.classList.add("active");
    loadPersonalizedFeed(1);
}

async function loadPersonalizedFeed(page = 1) {
    currentPage = page;
    const feedContainer = document.getElementById("feedList");
    feedContainer.innerHTML = `<div class="loading-spinner">Loading personalized feed for ${activeStudentId}...</div>`;

    const cat = document.getElementById("feedCategoryFilter") ? document.getElementById("feedCategoryFilter").value : "";
    let url = `/api/v1/feed/${activeStudentId}/feed?page=${page}&page_size=6`;
    if (cat) url += `&category=${encodeURIComponent(cat)}`;
    if (currentFeedApplicability && currentFeedApplicability !== "ALL") {
        url += `&applicability=${encodeURIComponent(currentFeedApplicability)}`;
    }

    try {
        const res = await fetch(url);
        const data = await res.json();

        // Update tier counts badges if returned
        if (data.tier_counts) {
            const tc = data.tier_counts;
            const bAll = document.getElementById("badgeAll");
            const bApp = document.getElementById("badgeApplicable");
            const bRel = document.getElementById("badgeRelevant");
            const bUrg = document.getElementById("badgeUrgent");
            const bDln = document.getElementById("badgeDeadlines");
            const bGen = document.getElementById("badgeGeneral");

            if (bAll) bAll.textContent = data.total_items !== undefined ? data.total_items : (data.total || "--");
            if (bApp) bApp.textContent = tc.DEFINITELY_APPLICABLE || 0;
            if (bRel) bRel.textContent = tc.POTENTIALLY_RELEVANT || 0;
            if (bUrg) bUrg.textContent = tc.URGENT || 0;
            if (bDln) bDln.textContent = tc.UPCOMING_DEADLINES || 0;
            if (bGen) bGen.textContent = tc.GENERAL_NOTICE || 0;
        }

        if (!data.feed || data.feed.length === 0) {
            feedContainer.innerHTML = `<div class="empty-state">No personalized announcements found for this filter combination.</div>`;
            return;
        }

        feedContainer.innerHTML = data.feed.map(item => renderNoticeCard(item, true)).join("");
        renderPagination(data.page, data.total_pages, "loadPersonalizedFeed");
    } catch (e) {
        feedContainer.innerHTML = `<div class="error-state">Error loading feed: ${e.message}</div>`;
    }
}

function getCleanSnippet(text, maxLen = 190) {
    if (!text) return "";
    let clean = text.replace(/\|/g, " ").replace(/\s+/g, " ").trim();
    if (clean.length <= maxLen) return clean;
    const sub = clean.substring(0, maxLen);
    const lastSpace = sub.lastIndexOf(" ");
    return (lastSpace > 120 ? sub.substring(0, lastSpace) : sub) + "...";
}

function renderNoticeCard(item, showRelevance = false) {
    const urgencyClass = `badge-${(item.urgency || item.metadata?.urgency || 'LOW').toLowerCase()}`;
    const attachWarning = item.attachment_present ?
        `<div class="attachment-warning">📎 Attachment Referenced: ${item.attachment_names ? item.attachment_names.join(", ") : 'Attachment File'} (Note: Actual file contents are hosted on UMS)</div>` : '';

    const explanation = showRelevance && item.explanation ?
        `<div class="explanation-banner">🎯 Priority Score: ${(item.personal_priority_score * 100).toFixed(0)}% • ${item.explanation}</div>` : '';

    const isUms = item.source && item.source.startsWith('ums');
    const umsBadge = isUms ?
        `<span class="badge badge-ums-live">🏛️ UMS Live</span>` : '';
    
    const isComplete = item.is_detail_complete !== false;
    const completeBadge = !isComplete ?
        `<span class="badge badge-preview-only" title="Brief summary preview from portal">⚠️ Brief Preview</span>` : '';

    const attachBadge = item.attachment_present ?
        `<span class="badge badge-attachment">📎 Attachment</span>` : '';

    const umsLink = item.source_url ?
        `<a href="${item.source_url}" target="_blank" onclick="event.stopPropagation()" style="color:var(--accent-color); font-size:12px; margin-left:8px;">Open in UMS ↗</a>` : '';

    // Applicability Tier Badge
    let tierBadge = '';
    if (item.applicability_tier) {
        switch (item.applicability_tier) {
            case "DEFINITELY_APPLICABLE":
                tierBadge = `<span class="badge badge-applicable">🎯 Applicable</span>`;
                break;
            case "POTENTIALLY_RELEVANT":
                tierBadge = `<span class="badge badge-relevant">💡 Relevant</span>`;
                break;
            case "GENERAL_NOTICE":
                tierBadge = `<span class="badge badge-general">📢 General</span>`;
                break;
            case "NOT_APPLICABLE":
                tierBadge = `<span class="badge badge-low">🚫 Excluded</span>`;
                break;
            case "UNCERTAIN":
                tierBadge = `<span class="badge badge-high">❓ Uncertain</span>`;
                break;
        }
    }

    // Deadline Badge
    let deadlineBadge = '';
    if (item.deadline_date) {
        if (item.is_deadline_expired) {
            deadlineBadge = `<span class="badge badge-deadline-expired">⛔ Deadline Expired: ${item.deadline_date}</span>`;
        } else {
            const daysText = item.days_remaining !== null && item.days_remaining !== undefined ? ` (${item.days_remaining}d left)` : '';
            deadlineBadge = `<span class="badge badge-deadline-active">⏳ Due: ${item.deadline_date}${daysText}</span>`;
        }
    }

    // Audience chip if available
    const audience = item.target_audience || item.metadata?.target_audience;
    const audienceChip = audience && audience !== "All Students" ?
        `<div class="notice-audience-chip">👥 ${audience}</div>` : '';

    const previewSnippet = getCleanSnippet(item.full_content || item.document || '');

    return `
        <div class="notice-card" onclick="viewAnnouncement('${item.announcement_id}')">
            <div class="card-header">
                <div class="notice-title">${item.title}</div>
                <div class="badge-group">
                    ${umsBadge}
                    ${completeBadge}
                    ${tierBadge}
                    ${deadlineBadge}
                    ${attachBadge}
                    <span class="badge ${urgencyClass}">${item.urgency || item.metadata?.urgency || 'NOTICE'}</span>
                    <span class="badge badge-low">${item.category || item.metadata?.category || 'GENERAL'}</span>
                </div>
            </div>
            ${audienceChip}
            ${explanation}
            ${attachWarning}
            <div class="notice-snippet">${previewSnippet}</div>
            <div class="card-footer">
                <span>📅 Published: ${item.publication_date} | Ref: ${item.reference_number || 'N/A'}${umsLink}</span>
                <div style="display:flex; align-items:center; gap:8px;">
                    <button class="btn-read-notice" onclick="event.stopPropagation(); viewAnnouncement('${item.announcement_id}')">📖 Read Full Notice</button>
                    ${showRelevance ? `
                        <button class="feedback-btn" onclick="event.stopPropagation(); submitFeedback('${item.announcement_id}', true)">👍</button>
                        <button class="feedback-btn" onclick="event.stopPropagation(); submitFeedback('${item.announcement_id}', false)">👎</button>
                    ` : ''}
                </div>
            </div>
        </div>
    `;
}

// ==========================================================================
// Grounded RAG Chatbot State & Handlers
// ==========================================================================
let chatHistory = [];
let isChatSubmitting = false;

function formatAssistantAnswer(text) {
    if (!text) return "";
    let html = text
        // Bold formatting
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        // Source citation inline clickable badges
        .replace(/\[Source ID:\s*([^\]]+)\]/g, (match, id) => {
            const cleanId = id.trim();
            return `<button class="inline-citation" onclick="viewAnnouncement('${cleanId}')" title="Click to view announcement ${cleanId}">📄 ${cleanId}</button>`;
        })
        // Bullet points
        .replace(/^\s*[\*\-]\s+(.*)$/gm, '<li>$1</li>')
        // Numbered list items
        .replace(/^\s*(\d+)\.\s+(.*)$/gm, '<li><strong>$1.</strong> $2</li>');

    // Group adjacent <li> items into a styled <ul>
    html = html.replace(/(<li>.*?<\/li>\s*)+/gs, (match) => `<ul class="chat-bullet-list">${match}</ul>`);
    // Preserve paragraphs and line breaks
    html = html.replace(/\n\n/g, '<br><br>');
    html = html.replace(/(?<!<\/li>)\n/g, '<br>');

    return html;
}

async function handleChatSubmit(e) {
    if (e && e.preventDefault) e.preventDefault();
    if (isChatSubmitting) return;

    const input = document.getElementById("chatInput");
    const sendBtn = document.getElementById("chatSendBtn");
    const query = input.value.trim();
    if (!query) return;

    const savedQuery = query;
    isChatSubmitting = true;
    if (sendBtn) {
        sendBtn.disabled = true;
        sendBtn.innerHTML = `Thinking... ⏳`;
    }
    input.disabled = true;

    // Render user message and clear input
    appendChatMessage("user", query);
    input.value = "";

    const chatContainer = document.getElementById("chatMessages");
    const loadingMsg = document.createElement("div");
    loadingMsg.className = "message assistant-message";
    loadingMsg.id = "chatLoading";
    loadingMsg.innerHTML = `
        <div class="avatar">🤖</div>
        <div class="message-body chat-loading-body">
            <span>Analyzing announcements and retrieving grounded evidence</span>
            <div class="loading-dots"><span>.</span><span>.</span><span>.</span></div>
        </div>
    `;
    chatContainer.appendChild(loadingMsg);
    chatContainer.scrollTop = chatContainer.scrollHeight;

    try {
        const payload = {
            query: savedQuery,
            student_id: activeStudentId,
            history: chatHistory.slice(-8),
            top_k: 5
        };

        const res = await fetch("/api/v1/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const errJson = await res.json().catch(() => ({}));
            const detailMsg = errJson.detail || `Server error (${res.status}: ${res.statusText})`;
            throw new Error(detailMsg);
        }

        const data = await res.json();
        const loadingElem = document.getElementById("chatLoading");
        if (loadingElem) loadingElem.remove();

        const formatted = formatAssistantAnswer(data.answer);
        let answerHtml = `<div class="chat-answer-content">${formatted}</div>`;

        if (data.attachment_warning) {
            answerHtml += `<div class="attachment-warning" style="margin-top:12px;">⚠️ ${data.attachment_warning}</div>`;
        }

        if (data.sources && data.sources.length > 0) {
            answerHtml += `<div class="chat-citations-header">📚 Grounded Sources & Citations (${data.sources.length}):</div>`;
            answerHtml += `<div class="chat-citations-list">`;
            data.sources.forEach(s => {
                const liveBadge = s.source === "live_ums" ? '<span class="badge badge-ums-live" style="margin-left:6px; font-size:10px;">🏛️ UMS Live</span>' : '';
                const umsUrlBtn = s.source_url ? `<a href="${s.source_url}" target="_blank" onclick="event.stopPropagation()" class="citation-external-link">↗ Portal</a>` : '';
                answerHtml += `
                    <div class="source-card-citation" onclick="viewAnnouncement('${s.announcement_id}')" style="cursor:pointer;" title="Click to view full notice">
                        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                            <div>
                                <strong>[Source ID: ${s.announcement_id}]</strong>${liveBadge} ${s.title} (${s.publication_date})
                            </div>
                            ${umsUrlBtn}
                        </div>
                        <div style="margin-top:4px; font-size:11px; color:var(--text-muted);">
                            Relevance: ${(s.similarity_score * 100).toFixed(1)}% | Evidence Completeness: <strong>${s.decision_completeness}</strong>
                        </div>
                    </div>
                `;
            });
            answerHtml += `</div>`;
        }

        appendChatMessage("assistant", answerHtml, true);

        // Record in conversation history for multi-turn follow-ups
        chatHistory.push({ role: "user", content: savedQuery });
        chatHistory.push({ role: "assistant", content: data.answer });
        if (chatHistory.length > 12) chatHistory = chatHistory.slice(-12);

    } catch (err) {
        const loadingElem = document.getElementById("chatLoading");
        if (loadingElem) loadingElem.remove();

        // Restore query so user doesn't lose text
        input.value = savedQuery;

        const errorHtml = `
            <div class="chat-error-card">
                <strong>⚠️ Failed to get response</strong>
                <p style="margin:4px 0 8px 0; font-size:13px; color:#fca5a5;">${err.message}</p>
                <button class="btn btn-secondary retry-chat-btn" onclick="retryChatQuery(${JSON.stringify(savedQuery).replace(/"/g, '&quot;')})">
                    🔄 Retry Query
                </button>
            </div>
        `;
        appendChatMessage("assistant", errorHtml, true);
    } finally {
        isChatSubmitting = false;
        input.disabled = false;
        if (sendBtn) {
            sendBtn.disabled = false;
            sendBtn.innerHTML = `Send 🚀`;
        }
        input.focus();
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
}

function retryChatQuery(queryText) {
    const input = document.getElementById("chatInput");
    input.value = queryText;
    handleChatSubmit(new Event("submit", { cancelable: true }));
}

function appendChatMessage(role, content, isHtml = false) {
    const chatContainer = document.getElementById("chatMessages");
    const msg = document.createElement("div");
    msg.className = `message ${role}-message`;
    const avatar = role === "assistant" ? "🤖" : "👨‍🎓";

    msg.innerHTML = `
        <div class="avatar">${avatar}</div>
        <div class="message-body">${isHtml ? content : `<p>${content}</p>`}</div>
    `;
    chatContainer.appendChild(msg);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function sendQuickChat(queryText) {
    const input = document.getElementById("chatInput");
    input.value = queryText;
    handleChatSubmit(new Event("submit", { cancelable: true }));
}

function clearChatHistory() {
    chatHistory = [];
    const chatContainer = document.getElementById("chatMessages");
    chatContainer.innerHTML = `
        <div class="message assistant-message">
            <div class="avatar">🤖</div>
            <div class="message-body">
                <p>Chat history cleared. How can I assist you with LPU announcements today?</p>
                <div class="sample-chips">
                    <button class="chip" onclick="sendQuickChat('When are 3rd year B.Tech exams starting?')">When are 3rd year B.Tech exams starting?</button>
                    <button class="chip" onclick="sendQuickChat('Are there placement drives for Software Engineers?')">Are there placement drives for Software Engineers?</button>
                    <button class="chip" onclick="sendQuickChat('What announcements affect Block 34?')">What announcements affect Block 34?</button>
                </div>
            </div>
        </div>
    `;
}

let currentSearchPage = 1;

async function executeSearch(page = 1) {
    currentSearchPage = page;
    const qInput = document.getElementById("searchInput");
    const q = qInput ? qInput.value.trim() : "";
    if (!q) {
        document.getElementById("searchResults").innerHTML = `<div class="empty-state">Please enter a search keyword or room number.</div>`;
        return;
    }

    const resContainer = document.getElementById("searchResults");
    resContainer.innerHTML = `<div class="loading-spinner">Searching announcements for "${q}"...</div>`;

    const cat = document.getElementById("searchCategorySelect") ? document.getElementById("searchCategorySelect").value : "";
    const urg = document.getElementById("searchUrgencySelect") ? document.getElementById("searchUrgencySelect").value : "";
    const sort = document.getElementById("searchSortSelect") ? document.getElementById("searchSortSelect").value : "relevance";
    const attOnly = document.getElementById("searchAttachmentOnly") ? document.getElementById("searchAttachmentOnly").checked : false;

    let url = `/api/v1/announcements/search?q=${encodeURIComponent(q)}&page=${page}&page_size=8&sort_by=${encodeURIComponent(sort)}`;
    if (cat) url += `&category=${encodeURIComponent(cat)}`;
    if (urg) url += `&urgency=${encodeURIComponent(urg)}`;
    if (attOnly) url += `&attachment_only=true`;

    try {
        const res = await fetch(url);
        const data = await res.json();

        if (!data.results || data.results.length === 0) {
            resContainer.innerHTML = `<div class="empty-state">No announcements matched your search criteria. Try different keywords.</div>`;
            document.getElementById("searchPagination").innerHTML = "";
            return;
        }

        resContainer.innerHTML = data.results.map(item => renderNoticeCard(item, false)).join("");
        renderPagination(data.page, data.total_pages, "executeSearch", "searchPagination");
    } catch (e) {
        resContainer.innerHTML = `<div class="error-state">Search error: ${e.message}</div>`;
    }
}

function resetSearchFilters() {
    const sInput = document.getElementById("searchInput");
    if (sInput) sInput.value = "";
    const cat = document.getElementById("searchCategorySelect");
    if (cat) cat.value = "";
    const urg = document.getElementById("searchUrgencySelect");
    if (urg) urg.value = "";
    const sort = document.getElementById("searchSortSelect");
    if (sort) sort.value = "relevance";
    const att = document.getElementById("searchAttachmentOnly");
    if (att) att.checked = false;

    document.getElementById("searchResults").innerHTML = `<div class="empty-state">Enter a query above to search announcements.</div>`;
    document.getElementById("searchPagination").innerHTML = "";
}

let cachedTimetableImpacts = [];
let currentTimetableFilter = "ALL";

function filterTimetable(filterType, evt) {
    currentTimetableFilter = filterType;
    document.querySelectorAll("#timetableFilters .pill-btn").forEach(btn => btn.classList.remove("active"));
    if (evt && evt.currentTarget) evt.currentTarget.classList.add("active");
    renderFilteredTimetable();
}

function renderFilteredTimetable() {
    const container = document.getElementById("timetableList");
    let filtered = cachedTimetableImpacts;

    if (currentTimetableFilter === "RED" || currentTimetableFilter === "AFFECTED") {
        filtered = cachedTimetableImpacts.filter(i => i.indicator_color === "RED");
    } else if (currentTimetableFilter === "AMBER" || currentTimetableFilter === "ATTACHMENT") {
        filtered = cachedTimetableImpacts.filter(i => i.indicator_color === "AMBER" && i.status !== "EXEMPTED");
    } else if (currentTimetableFilter === "EXEMPTED") {
        filtered = cachedTimetableImpacts.filter(i => i.status === "EXEMPTED");
    } else if (currentTimetableFilter === "GREEN" || currentTimetableFilter === "CLEAR") {
        filtered = cachedTimetableImpacts.filter(i => i.indicator_color === "GREEN");
    }

    if (!filtered || filtered.length === 0) {
        container.innerHTML = `<div class="empty-state">No timetable entries matching "${currentTimetableFilter}".</div>`;
        return;
    }

    container.innerHTML = filtered.map(imp => {
        let borderColor = '#10b981'; // Green
        let statusBadgeHtml = '<span class="badge badge-indicator-green">✅ GREEN — No Conflict</span>';

        if (imp.indicator_color === "RED" || imp.status === "RED_CONFLICT" || imp.status === "CONFIRMED_MATCH") {
            borderColor = '#ef4444'; // Red
            statusBadgeHtml = '<span class="badge badge-indicator-red">🚨 RED — Conflict</span>';
        } else if (imp.status === "EXEMPTED") {
            borderColor = '#38bdf8'; // Blue
            statusBadgeHtml = '<span class="badge badge-indicator-exempted">🛡️ Room Exempted</span>';
        } else if (imp.indicator_color === "AMBER" || imp.status === "ATTACHMENT_DEPENDENT" || imp.status === "POTENTIAL_IMPACT") {
            borderColor = '#f59e0b'; // Amber
            statusBadgeHtml = '<span class="badge badge-indicator-amber">⚠️ AMBER — Needs Verification</span>';
        }

        const impactTypeTag = imp.impact_type && imp.impact_type !== "NONE" ?
            `<span class="badge" style="background:rgba(255,255,255,0.08); font-size:11px; margin-left:6px;">${escapeHtml(imp.impact_type)}</span>` : '';

        const replacementBox = imp.replacement_room ?
            `<div style="margin-top:8px; padding:6px 12px; background:rgba(16, 185, 129, 0.12); border:1px solid rgba(16, 185, 129, 0.35); border-radius:6px; font-size:12px; color:#6ee7b7; display:inline-flex; align-items:center; gap:6px;">
                <span>🔄 Replacement Venue:</span> <strong>Room ${escapeHtml(imp.replacement_room)}</strong>
            </div>` : '';

        const conflictingClassBox = imp.conflicting_entry_title ?
            `<div style="margin-top:8px; padding:6px 12px; background:rgba(239, 68, 68, 0.12); border:1px solid rgba(239, 68, 68, 0.35); border-radius:6px; font-size:12px; color:#fca5a5; display:inline-flex; align-items:center; gap:6px;">
                <span>⚠️ Overlapping Class:</span> <strong>${escapeHtml(imp.conflicting_entry_title)}</strong>
            </div>` : '';

        const noticeLink = imp.announcement_title && imp.announcement_id ?
            `<div style="font-size:12px; color:var(--accent-color); margin-top:8px; cursor:pointer; font-weight:500; display:inline-flex; align-items:center; gap:4px;" onclick="viewAnnouncement('${escapeHtml(imp.announcement_id)}')">
                <span>📄 Supporting Notice:</span> <span style="text-decoration:underline;">"${escapeHtml(imp.announcement_title)}" ↗</span>
            </div>` : '';

        const evidenceBox = imp.evidence_text ?
            `<div style="font-size:12px; color:var(--text-secondary); margin-top:5px;">🔍 Evidence: <em>${escapeHtml(imp.evidence_text)}</em></div>` : '';

        return `
            <div class="notice-card" style="border-left:4px solid ${borderColor}">
                <div class="card-header">
                    <div>
                        <strong>Class: ${escapeHtml(imp.entry.course_code)} — ${escapeHtml(imp.entry.course_name)}</strong><br>
                        <span style="font-size:12px; color:var(--text-secondary);">Room: ${escapeHtml(imp.entry.room)} | Date: ${escapeHtml(imp.entry.day_or_date)} (${escapeHtml(imp.entry.start_time)} - ${escapeHtml(imp.entry.end_time)}) | Building: ${escapeHtml(imp.entry.building || 'Block 34')}</span>
                    </div>
                    <div style="display:flex; align-items:center; gap:4px;">
                        ${impactTypeTag}
                        ${statusBadgeHtml}
                    </div>
                </div>
                <div style="font-size:13px; color:var(--text-primary); margin-top:8px;">${escapeHtml(imp.explanation)}</div>
                ${replacementBox}
                ${conflictingClassBox}
                ${evidenceBox}
                ${noticeLink}
            </div>
        `;
    }).join("");
}

async function loadAffectedClasses() {
    const container = document.getElementById("timetableList");
    container.innerHTML = `<div class="loading-spinner">Checking room & timetable conflict analysis for ${activeStudentId}...</div>`;

    try {
        const res = await fetch(`/api/v1/feed/${encodeURIComponent(activeStudentId)}/affected-classes`);
        const data = await res.json();
        cachedTimetableImpacts = data.impacts || [];

        // Calculate counts
        const allCount = cachedTimetableImpacts.length;
        const redCount = (typeof data.red_count === "number") ? data.red_count : cachedTimetableImpacts.filter(i => i.indicator_color === "RED").length;
        const amberCount = (typeof data.amber_count === "number") ? data.amber_count : cachedTimetableImpacts.filter(i => i.indicator_color === "AMBER" && i.status !== "EXEMPTED").length;
        const exCount = (typeof data.exempted_count === "number") ? data.exempted_count : cachedTimetableImpacts.filter(i => i.status === "EXEMPTED").length;
        const greenCount = (typeof data.green_count === "number") ? data.green_count : cachedTimetableImpacts.filter(i => i.indicator_color === "GREEN").length;

        const elAll = document.getElementById("ttCountAll");
        const elRed = document.getElementById("ttCountRed");
        const elAmber = document.getElementById("ttCountAmber");
        const elEx = document.getElementById("ttCountExempted");
        const elGreen = document.getElementById("ttCountGreen");

        // Fallbacks for older element IDs
        const elAff = document.getElementById("ttCountAffected");
        const elAtt = document.getElementById("ttCountAttachment");
        const elClr = document.getElementById("ttCountClear");

        if (elAll) elAll.textContent = allCount;
        if (elRed) elRed.textContent = redCount;
        if (elAmber) elAmber.textContent = amberCount;
        if (elEx) elEx.textContent = exCount;
        if (elGreen) elGreen.textContent = greenCount;

        if (elAff) elAff.textContent = redCount;
        if (elAtt) elAtt.textContent = amberCount;
        if (elClr) elClr.textContent = greenCount;

        renderFilteredTimetable();
    } catch (e) {
        container.innerHTML = `<div class="error-state">Error analyzing timetable: ${escapeHtml(e.message)}</div>`;
    }
}


async function triggerCacheReload() {
    try {
        const res = await fetch("/api/v1/health/cache-refresh", { method: "POST" });
        const data = await res.json();
        alert(`⚡ ${data.message || "Cache reloaded successfully!"}`);
        loadHealthDashboard();
    } catch (e) {
        alert("Failed to reload cache: " + e.message);
    }
}

async function loadHealthDashboard() {
    try {
        const res = await fetch("/api/v1/health");
        const data = await res.json();

        // Update Subsystem chips
        if (data.subsystems) {
            const sqText = document.getElementById("sqliteStatusText");
            const chText = document.getElementById("chromaStatusText");
            const gmText = document.getElementById("geminiStatusText");

            if (sqText) {
                sqText.textContent = data.subsystems.sqlite === "healthy" ? "Connected 🟢" : "Error 🔴";
                sqText.style.color = data.subsystems.sqlite === "healthy" ? "#34d399" : "#f87171";
            }
            if (chText) {
                chText.textContent = data.subsystems.chromadb === "healthy" ? "Indexed 🟢" : "Degraded 🟡";
                chText.style.color = data.subsystems.chromadb === "healthy" ? "#34d399" : "#fbbf24";
            }
            if (gmText) {
                gmText.textContent = data.subsystems.gemini_api === "configured" ? "Online 🟢" : "Offline Vectors 🟡";
                gmText.style.color = data.subsystems.gemini_api === "configured" ? "#38bdf8" : "#fbbf24";
            }
        }

        const elTotal = document.getElementById("metricTotal");
        const elFull = document.getElementById("metricFull");
        const elPartial = document.getElementById("metricPartial");
        const elAttachments = document.getElementById("metricAttachments");
        const elIndexed = document.getElementById("metricIndexed");
        const elLastSync = document.getElementById("metricLastSync");

        if (elTotal) elTotal.textContent = (data.dataset_summary && data.dataset_summary.total_records) || 0;
        if (elFull) {
            const fullCount = (data.sqlite_stats && data.sqlite_stats.full_notices_count !== undefined)
                ? data.sqlite_stats.full_notices_count
                : ((data.dataset_summary && data.dataset_summary.total_records) || 0);
            elFull.textContent = fullCount;
        }
        if (elPartial) {
            const partialCount = (data.sqlite_stats && data.sqlite_stats.partial_notices_count !== undefined)
                ? data.sqlite_stats.partial_notices_count
                : 0;
            elPartial.textContent = partialCount;
        }
        if (elAttachments) elAttachments.textContent = (data.dataset_summary && data.dataset_summary.with_attachments) || 0;
        if (elIndexed) elIndexed.textContent = (data.vector_index_summary && data.vector_index_summary.total_indexed_documents) || 0;
        if (elLastSync) {
            if (data.sqlite_stats && data.sqlite_stats.last_sync && data.sqlite_stats.last_sync.started_at) {
                const s = data.sqlite_stats.last_sync;
                const timeStr = new Date(s.started_at).toLocaleTimeString();
                elLastSync.textContent = `${s.status} (${timeStr})`;
                elLastSync.title = s.message || s.status;
            } else {
                elLastSync.textContent = "Standby";
            }
        }

        document.getElementById("datasetReportPre").textContent = JSON.stringify(data.dataset_summary, null, 2);
        document.getElementById("indexStatusPre").textContent = JSON.stringify(data.vector_index_summary, null, 2);

        // Fetch UMS Sync history
        loadUmsHistory();
    } catch (e) {
        console.error("Error loading dashboard metrics:", e);
    }
}

async function loadUmsStatus() {
    try {
        const res = await fetch("/api/v1/ums/status");
        if (!res.ok) return;
        const data = await res.json();
        
        const badge = document.getElementById("umsStatusBadge");
        const lastSync = document.getElementById("umsLastSyncText");
        if (!badge || !lastSync) return;

        badge.className = "ums-status-badge";
        if (data.connector_mode === "mock") {
            badge.classList.add("mock");
            badge.textContent = "Mock Mode";
        } else if (data.status === "LIVE_CONNECTED" || (data.connection_check && data.connection_check.connected)) {
            badge.classList.add("connected");
            badge.textContent = "Official Live Feed Active 🟢";
        } else if (data.status === "AUTH_REQUIRED") {
            badge.classList.add("auth_required");
            badge.textContent = "Auth Required";
        } else {
            badge.classList.add("error");
            badge.textContent = (data.connection_check && data.connection_check.status) || "Offline";
        }

        if (data.connector_mode === "live") {
            const radioLive = document.getElementById("modeRadioLive");
            if (radioLive) radioLive.checked = true;
        } else {
            const radioMock = document.getElementById("modeRadioMock");
            if (radioMock) radioMock.checked = true;
        }

        if (data.last_sync && data.last_sync.completed_at) {
            const dateStr = new Date(data.last_sync.completed_at).toLocaleTimeString();
            lastSync.textContent = `Last Synced: ${dateStr} (${data.last_sync.status})`;
        } else {
            lastSync.textContent = `Last Synced: Never`;
        }
    } catch (e) {
        console.error("Failed to load UMS status:", e);
    }
}

async function triggerUmsSync() {
    const btn = document.getElementById("umsSyncBtn");
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="loading-spin">⏳</span> Syncing notices...`;

    try {
        const res = await fetch("/api/v1/ums/sync?limit=20", {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });
        const result = await res.json();
        if (res.ok) {
            if (result.inserted_count > 0 || result.updated_count > 0) {
                btn.innerHTML = `✅ Synced (${result.inserted_count} new, ${result.updated_count} rev)`;
            } else if (result.skipped_count > 0) {
                btn.innerHTML = `⚡ Up to Date (${result.skipped_count} current)`;
            } else {
                btn.innerHTML = `ℹ️ ${result.status || "0 notices"}`;
            }
            setTimeout(() => {
                btn.innerHTML = originalText;
                btn.disabled = false;
            }, 3500);
            loadPersonalizedFeed();
            loadUmsStatus();
            loadHealthDashboard();
        } else {
            alert(`Sync notice: ${result.detail || "Unable to sync."}`);
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    } catch (e) {
        alert(`Sync error: ${e.message}`);
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

async function loadUmsHistory() {
    const container = document.getElementById("umsSyncHistoryContent");
    if (!container) return;

    try {
        const res = await fetch("/api/v1/ums/sync/history?limit=5");
        const history = await res.json();
        if (!history || history.length === 0) {
            container.innerHTML = `<p style="color:var(--text-secondary); font-size:13px;">No synchronization runs logged yet. Click 'Sync UMS Notices' to run initial sync.</p>`;
            return;
        }

        container.innerHTML = `
            <table class="sync-history-table">
                <thead>
                    <tr>
                        <th>Sync ID</th>
                        <th>Started At</th>
                        <th>Status</th>
                        <th>Fetched</th>
                        <th>New</th>
                        <th>Updated</th>
                        <th>Skipped</th>
                        <th>Result</th>
                        <th>Triggered By</th>
                    </tr>
                </thead>
                <tbody>
                    ${history.map(h => `
                        <tr>
                            <td><code>${h.sync_id}</code></td>
                            <td>${new Date(h.started_at).toLocaleTimeString()}</td>
                            <td><span class="badge ${h.status === 'SUCCESS' ? 'badge-medium' : (h.status === 'UP_TO_DATE' ? 'badge-low' : 'badge-critical')}">${h.status}</span></td>
                            <td>${h.fetched_count}</td>
                            <td><strong style="color:var(--accent-color);">${h.inserted_count}</strong></td>
                            <td>${h.updated_count}</td>
                            <td>${h.skipped_count}</td>
                            <td style="font-size:11px; max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${h.message || ''}">${h.message || (h.error_message ? 'Error: ' + h.error_message : 'Completed')}</td>
                            <td>${h.triggered_by}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        `;
    } catch (e) {
        container.innerHTML = `<p style="color:var(--text-secondary);">Error loading sync history: ${e.message}</p>`;
    }
}

function escapeHtml(unsafe) {
    if (!unsafe) return "";
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function formatNoticeContent(raw) {
    if (!raw) return "<p>No content provided.</p>";

    // Work on raw text safely
    let text = raw;

    // Convert Markdown tables: | Col 1 | Col 2 |
    text = text.replace(/((?:\|[^\n]+\|\r?\n)+)/g, (tableBlock) => {
        const rows = tableBlock.trim().split(/\r?\n/).filter(r => r.includes("|"));
        if (rows.length < 2) return tableBlock;

        let html = '<div class="detail-table-wrapper"><table class="detail-table">';
        let isHeader = true;

        for (let i = 0; i < rows.length; i++) {
            const row = rows[i].trim();
            if (/^\|[\s\-:]+\|\s*$/.test(row) || /^\|(?:\s*[:-]+[-:]\s*\|)+$/.test(row)) {
                isHeader = false;
                continue;
            }
            const cells = row.split("|").slice(1, -1).map(c => escapeHtml(c.trim()));
            if (isHeader && i === 0) {
                html += "<thead><tr>" + cells.map(c => `<th>${c}</th>`).join("") + "</tr></thead><tbody>";
            } else {
                html += "<tr>" + cells.map(c => `<td>${c}</td>`).join("") + "</tr>";
            }
        }
        html += "</tbody></table></div>";
        return html;
    });

    // Convert headings
    text = text.replace(/^###\s+(.+)$/gm, '<h4 class="notice-section-heading">$1</h4>');
    text = text.replace(/^##\s+(.+)$/gm, '<h4 class="notice-section-heading" style="font-size:17px; color:#60a5fa;">$1</h4>');

    // Convert bold
    text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Convert bullet lists
    text = text.replace(/^[•\*\-]\s+(.+)$/gm, '<li>$1</li>');
    text = text.replace(/((?:<li>.*?<\/li>\s*)+)/gs, '<ul class="detail-bullet-list">$1</ul>');

    // Convert paragraphs
    const blocks = text.split(/\n\n+/);
    const formattedBlocks = blocks.map(block => {
        const trimmed = block.trim();
        if (!trimmed) return "";
        if (trimmed.startsWith("<div") || trimmed.startsWith("<h4") || trimmed.startsWith("<ul") || trimmed.startsWith("<table")) {
            return trimmed;
        }
        return `<p>${trimmed.replace(/\n/g, '<br>')}</p>`;
    });

    return formattedBlocks.filter(Boolean).join("\n");
}

async function viewAnnouncement(id, openAsModal = false) {
    try {
        currentActiveNoticeId = id;

        // Update URL hash without triggering duplicate hashchange
        if (window.location.hash !== `#/notice/${encodeURIComponent(id)}`) {
            history.pushState(null, "", `#/notice/${encodeURIComponent(id)}`);
        }

        const res = await fetch(`/api/v1/announcements/${id}`);
        if (!res.ok) throw new Error("Could not load notice details (" + res.status + ")");
        const ann = await res.json();

        const isUms = ann.source && ann.source.startsWith("ums");
        const urgency = ann.metadata?.urgency || 'LOW';
        const urgencyClass = `badge-${urgency.toLowerCase()}`;
        const isComplete = ann.is_detail_complete !== false;

        let statusBannerHtml = "";
        if (!isComplete) {
            statusBannerHtml = `
                <div class="detail-alert-box alert-incomplete">
                    <div>
                        <strong>⚠️ Notice Preview Only:</strong> This announcement currently contains a brief summary. Complete circular details can be fetched directly from UMS.
                        ${ann.detail_fetch_error ? `<br><small style="opacity:0.85;">Source note: ${escapeHtml(ann.detail_fetch_error)}</small>` : ''}
                    </div>
                    <button class="btn-refresh-detail" id="btnRefreshModal_${ann.announcement_id}" onclick="refreshNoticeDetails('${ann.announcement_id}')">
                        🔄 Fetch Complete Notice Now
                    </button>
                </div>
            `;
        }

        const deadlineText = ann.metadata?.deadline || (ann.deadline_date ? ann.deadline_date : 'Not Specified');
        const audienceText = ann.metadata?.target_audience || 'All Students';
        const actionText = ann.metadata?.action_type || 'Informational / General';
        const roomsText = (ann.metadata?.rooms_affected && ann.metadata.rooms_affected.length > 0)
            ? ann.metadata.rooms_affected.join(', ')
            : 'Campus / General Venue';

        let attachmentsHtml = "";
        if (ann.attachment_present) {
            const fileList = (ann.attachment_names && ann.attachment_names.length > 0)
                ? ann.attachment_names.map(name => `<li style="margin-bottom:6px;">📄 <strong>${escapeHtml(name)}</strong></li>`).join("")
                : '<li>📄 Official Attached Document</li>';

            attachmentsHtml = `
                <div style="background:rgba(168, 85, 247, 0.08); border:1px solid rgba(168, 85, 247, 0.25); border-radius:var(--radius-md); padding:16px 20px; margin-top:20px;">
                    <div style="font-weight:700; color:#c084fc; margin-bottom:8px; display:flex; align-items:center; gap:8px;">
                        <span style="font-size:18px;">📎</span> Official Attached Files Referenced
                    </div>
                    <ul style="margin:0 0 10px 20px; font-size:13px; color:#e2e8f0; line-height:1.6;">
                        ${fileList}
                    </ul>
                    <p style="font-size:12px; color:var(--text-secondary); margin:0;">
                        🔒 <em>Note: Attachment files are hosted securely within the official LPU UMS Portal. Log into <a href="https://ums.lpu.in/lpuums/" target="_blank" style="color:var(--accent-color);">ums.lpu.in</a> with student credentials to download original files.</em>
                    </p>
                </div>
            `;
        }

        let aiInsightsHtml = "";
        const summaryContent = ann.summary || ann.metadata?.summary;
        if (summaryContent) {
            aiInsightsHtml = `
                <details class="detail-ai-box">
                    <summary>🤖 View AI Summary &amp; Key Takeaways</summary>
                    <div style="margin-top:10px; line-height:1.6; color:#cbd5e1;">
                        <p style="margin:0;">${escapeHtml(summaryContent)}</p>
                    </div>
                </details>
            `;
        }

        const formattedBody = formatNoticeContent(ann.full_content);

        const noticeMarkup = `
            <div class="detail-modal-header">
                <h1 class="detail-modal-title" style="font-size: 22px; font-weight: 700; margin-bottom: 12px; line-height: 1.4;">${escapeHtml(ann.title)}</h1>
                <div class="detail-modal-meta-row" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
                    <div class="badge-group">
                        ${isUms ? '<span class="badge badge-ums-live">🏛️ UMS Live</span>' : '<span class="badge badge-low">Archive</span>'}
                        <span class="badge ${urgencyClass}">${ann.metadata?.urgency || 'NOTICE'}</span>
                        <span class="badge badge-low">${ann.metadata?.category || 'GENERAL'}</span>
                        ${ann.attachment_present ? '<span class="badge badge-attachment">📎 With Attachment</span>' : ''}
                        ${!isComplete ? '<span class="badge badge-preview-only">⚠️ Preview Only</span>' : '<span class="badge badge-medium">✅ Complete Circular</span>'}
                    </div>
                    <div style="font-size:12px; color:var(--text-secondary);">
                        📅 Published: <strong style="color:var(--text-primary);">${ann.publication_date}</strong> • Ref: <code>${escapeHtml(ann.reference_number || 'N/A')}</code>
                        ${ann.source_url ? ` • <a href="${ann.source_url}" target="_blank" style="color:var(--accent-color);">Open Official Portal ↗</a>` : ''}
                    </div>
                </div>
            </div>

            ${statusBannerHtml}

            <div class="detail-meta-grid">
                <div class="detail-meta-item">
                    <span class="meta-label">⏳ Deadline / Key Date</span>
                    <span class="meta-val" style="color:#fbbf24;">${escapeHtml(deadlineText)}</span>
                </div>
                <div class="detail-meta-item">
                    <span class="meta-label">👥 Target Audience / Program</span>
                    <span class="meta-val">${escapeHtml(audienceText)}</span>
                </div>
                <div class="detail-meta-item">
                    <span class="meta-label">⚡ Required Action</span>
                    <span class="meta-val" style="color:#38bdf8;">${escapeHtml(actionText)}</span>
                </div>
                <div class="detail-meta-item">
                    <span class="meta-label">📍 Venue / Room Affected</span>
                    <span class="meta-val">${escapeHtml(roomsText)}</span>
                </div>
            </div>

            <div style="margin-top: 20px;">
                <div style="font-size:12px; text-transform:uppercase; letter-spacing:0.5px; color:var(--text-muted); font-weight:700; margin-bottom:8px;">
                    📜 Complete Original Announcement Content:
                </div>
                <div class="detail-content-box notice-full-reader">
                    ${formattedBody}
                </div>
            </div>

            ${aiInsightsHtml}

            ${attachmentsHtml}

            <div style="display:flex; justify-content:space-between; align-items:center; padding-top:16px; margin-top:24px; border-top:1px solid var(--border-color); font-size:12px; color:var(--text-muted); flex-wrap:wrap; gap:10px;">
                <span>System ID: <code>${ann.announcement_id}</code> • Source: <strong style="color:var(--text-primary);">${ann.source || 'LPU UMS'}</strong></span>
                <div style="display:flex; gap:8px;">
                    <button class="btn btn-secondary" onclick="copyCurrentNoticeLink()">🔗 Copy Link</button>
                    <button class="btn btn-primary" onclick="returnFromNoticeDetail()">← Back to Notices</button>
                </div>
            </div>
        `;

        // Update dedicated page view
        const detailContainer = document.getElementById("noticeDetailViewContainer");
        if (detailContainer) {
            detailContainer.innerHTML = noticeMarkup;
        }

        // Configure external UMS portal button in dedicated header
        const extUmsBtn = document.getElementById("btnExternalUmsLink");
        if (extUmsBtn) {
            if (ann.source_url) {
                extUmsBtn.href = ann.source_url;
                extUmsBtn.style.display = "inline-flex";
            } else {
                extUmsBtn.style.display = "none";
            }
        }

        // Also update modal in case modal mode is requested
        const modalBody = document.getElementById("modalBody");
        if (modalBody) {
            modalBody.innerHTML = noticeMarkup;
        }

        if (openAsModal) {
            const modalContainer = document.querySelector("#announcementModal .modal-content");
            if (modalContainer) modalContainer.className = "modal-content notice-detail-modal";
            document.getElementById("announcementModal").style.display = "flex";
        } else {
            // Close any existing modal
            const modal = document.getElementById("announcementModal");
            if (modal) modal.style.display = "none";

            // Switch to dedicated tab
            document.querySelectorAll(".tab-content").forEach(el => el.classList.remove("active"));
            document.querySelectorAll(".nav-item").forEach(el => el.classList.remove("active"));
            const detailTab = document.getElementById("noticeDetailTab");
            if (detailTab) detailTab.classList.add("active");
            toggleMobileSidebar(false);

            window.scrollTo({ top: 0, behavior: "smooth" });
        }
    } catch (e) {
        alert("Failed to load announcement details: " + e.message);
    }
}

async function refreshNoticeDetails(id) {
    const btn = document.getElementById(`btnRefreshModal_${id}`);
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="loading-spin">⏳</span> Fetching details...`;
    }
    try {
        const res = await fetch(`/api/v1/announcements/${id}/refresh-details`, { method: "POST" });
        const result = await res.json();
        if (res.ok) {
            await viewAnnouncement(id);
            if (typeof loadPersonalizedFeed === "function") loadPersonalizedFeed(currentPage);
        } else {
            alert(`Could not fetch details: ${result.detail || "Source unavailable."}`);
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = `🔄 Retry Fetch`;
            }
        }
    } catch (e) {
        alert(`Error fetching notice details: ${e.message}`);
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `🔄 Retry Fetch`;
        }
    }
}

async function triggerNoticeBackfill() {
    const limitSelect = document.getElementById("backfillLimitSelect");
    const limit = limitSelect ? parseInt(limitSelect.value, 10) : 50;
    const btn = document.getElementById("btnRunBackfill");
    const statusOutput = document.getElementById("backfillStatusOutput");

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="loading-spin">⏳</span> Scanning &amp; Backfilling...`;
    }
    if (statusOutput) {
        statusOutput.style.display = "block";
        statusOutput.style.background = "rgba(56, 189, 248, 0.1)";
        statusOutput.style.borderColor = "rgba(56, 189, 248, 0.3)";
        statusOutput.style.color = "#38bdf8";
        statusOutput.innerHTML = `Scanning up to ${limit} notices with missing/short details and querying authorized source details...`;
    }

    try {
        const res = await fetch(`/api/v1/ums/backfill?limit=${limit}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });
        const data = await res.json();
        if (res.ok) {
            if (statusOutput) {
                statusOutput.style.background = "rgba(16, 185, 129, 0.1)";
                statusOutput.style.borderColor = "rgba(16, 185, 129, 0.3)";
                statusOutput.style.color = "#34d399";
                statusOutput.innerHTML = `
                    ✅ <strong>Backfill Completed:</strong> Scanned ${data.scanned_count} notice(s). 
                    Enriched <strong>${data.enriched_count}</strong> records with complete circular text. 
                    Skipped: ${data.skipped_count}, Errors: ${data.error_count}.
                `;
            }
            loadHealthDashboard();
            if (typeof loadPersonalizedFeed === "function") loadPersonalizedFeed(1);
        } else {
            if (statusOutput) {
                statusOutput.style.background = "rgba(239, 68, 68, 0.1)";
                statusOutput.style.borderColor = "rgba(239, 68, 68, 0.3)";
                statusOutput.style.color = "#f87171";
                statusOutput.innerHTML = `⚠️ Backfill failed: ${data.detail || JSON.stringify(data)}`;
            }
        }
    } catch (e) {
        if (statusOutput) {
            statusOutput.style.background = "rgba(239, 68, 68, 0.1)";
            statusOutput.style.borderColor = "rgba(239, 68, 68, 0.3)";
            statusOutput.style.color = "#f87171";
            statusOutput.innerHTML = `⚠️ Backfill network error: ${e.message}`;
        }
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<span>⚡</span> Run Safe Backfill`;
        }
    }
}

function closeModal() {
    document.getElementById("announcementModal").style.display = "none";
}

async function submitFeedback(announcementId, isRelevant) {
    try {
        await fetch("/api/v1/feedback", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                student_id: activeStudentId,
                announcement_id: announcementId,
                is_relevant: isRelevant
            })
        });
        alert(isRelevant ? "Marked as Relevant 👍" : "Marked as Not Relevant 👎");
    } catch (e) {
        console.error("Feedback error:", e);
    }
}

function renderPagination(page, totalPages, fetchFuncStr) {
    const container = document.getElementById("feedPagination");
    if (totalPages <= 1) {
        container.innerHTML = "";
        return;
    }
    container.innerHTML = `
        <button class="btn btn-secondary" ${page === 1 ? 'disabled' : ''} onclick="${fetchFuncStr}(${page - 1})">Previous</button>
        <span style="font-size:13px; color:var(--text-secondary);">Page ${page} of ${totalPages}</span>
        <button class="btn btn-secondary" ${page === totalPages ? 'disabled' : ''} onclick="${fetchFuncStr}(${page + 1})">Next</button>
    `;
}

function openUmsSetupModal() {
    document.getElementById("umsSetupModal").style.display = "flex";
}

function closeUmsSetupModal() {
    document.getElementById("umsSetupModal").style.display = "none";
}

function switchSetupTab(tabId) {
    const pTab = document.getElementById("setupTabPaste");
    const bTab = document.getElementById("setupTabBrowser");
    const cTab = document.getElementById("setupTabCookie");
    if (pTab) pTab.style.display = tabId === 'pasteTab' ? 'block' : 'none';
    if (bTab) bTab.style.display = tabId === 'browserTab' ? 'block' : 'none';
    if (cTab) cTab.style.display = tabId === 'cookieTab' ? 'block' : 'none';

    const bp = document.getElementById("tabBtnPaste");
    const bb = document.getElementById("tabBtnBrowser");
    const bc = document.getElementById("tabBtnCookie");
    if (bp) bp.className = 'nav-item ' + (tabId === 'pasteTab' ? 'active' : '');
    if (bb) bb.className = 'nav-item ' + (tabId === 'browserTab' ? 'active' : '');
    if (bc) bc.className = 'nav-item ' + (tabId === 'cookieTab' ? 'active' : '');
}

function loadSampleLiveNotice() {
    const sample = `Title: End Term Examination & Practical Evaluation Schedule Autumn 2026
Reference Number: LPU/10.2/EXAM/2026/0149
Date: 16-10-2026
Full Content:
All 2nd and 3rd Year B.Tech Computer Science and Engineering students are hereby notified that the Autumn 2026 End Term Practical Examinations will be conducted from 10th November to 20th November 2026.
The laboratory venue for course CSE301 (Data Structures) will be Block 34, Computer Lab 34-204 and 34-205.
Students must report 15 minutes prior to session commencement and bring university ID cards.
Attachment: End_Term_Practical_DateSheet_2026.pdf`;
    const input = document.getElementById("pastedNoticeInput");
    if (input) input.value = sample;
}

async function submitPastedNotice() {
    const input = document.getElementById("pastedNoticeInput");
    const text = input ? input.value.trim() : "";
    if (!text) {
        alert("Please paste announcement text, table rows, or HTML from UMS.");
        return;
    }

    const btn = document.getElementById("pasteIngestBtn");
    const originalText = btn ? btn.innerHTML : "Ingest";
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="loading-spin">⏳</span> Ingesting into SmartNotice...`;
    }

    try {
        const res = await fetch("/api/v1/ums/import", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ raw_text: text })
        });
        const result = await res.json();
        if (res.ok) {
            let msg = "";
            if (result.inserted_count > 0) {
                msg = `🎉 Success! Ingested ${result.inserted_count} new real-time announcement(s) into SmartNotice!`;
            } else if (result.skipped_count > 0) {
                msg = `⚡ All ${result.skipped_count} announcement(s) are already up to date in SmartNotice!`;
            } else if (result.updated_count > 0) {
                msg = `🔄 Updated ${result.updated_count} revised announcement(s)!`;
            } else {
                msg = `ℹ️ ${result.message || "Ingested notices."}`;
            }
            alert(msg);
            if (input) input.value = "";
            closeUmsSetupModal();
            loadPersonalizedFeed();
            loadUmsStatus();
            loadHealthDashboard();
        } else {
            alert(`Import failed: ${result.detail || JSON.stringify(result)}`);
        }
    } catch (e) {
        alert("Error ingesting notices: " + e.message);
    } finally {
        if (btn) {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    }
}

function copyConsoleSnippet() {
    const text = document.getElementById("consoleSnippet").innerText;
    navigator.clipboard.writeText(text).then(() => {
        alert("📋 Copied 1-click sync snippet!\n\nNow open your ums.lpu.in tab, press F12 -> Console, paste and hit Enter.");
    }).catch(err => {
        alert("Clipboard copy failed: " + err);
    });
}

async function submitManualCookie() {
    const cookieInput = document.getElementById("manualCookieInput");
    const cookie = cookieInput ? cookieInput.value.trim() : "";
    const modeLive = document.getElementById("modeRadioLive");
    const mode = (modeLive && modeLive.checked) ? "live" : "mock";

    const payload = { mode: mode };
    if (cookie) {
        payload.cookie = cookie;
    }

    try {
        const res = await fetch("/api/v1/ums/import", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const result = await res.json();
        if (res.ok) {
            let msg = "";
            if (result.inserted_count > 0) {
                msg = `🎉 Settings saved! Synced ${result.inserted_count} new announcement(s) into SmartNotice!`;
            } else if (result.skipped_count > 0) {
                msg = `⚡ Settings saved! All ${result.skipped_count} announcements are already up to date!`;
            } else if (result.updated_count > 0) {
                msg = `🔄 Settings saved! Updated ${result.updated_count} revised announcement(s)!`;
            } else {
                msg = `ℹ️ Settings saved: ${result.message || "Ready."}`;
            }
            alert(msg);
            closeUmsSetupModal();
            loadPersonalizedFeed();
            loadUmsStatus();
            loadHealthDashboard();
        } else {
            alert(`Portal notice: ${result.detail || JSON.stringify(result)}`);
        }
    } catch (e) {
        alert("Failed to update settings: " + e.message);
    }
}


