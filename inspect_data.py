import json
from pathlib import Path

file_path = Path("data/all_announcements_with_attachment_flag.json")

if not file_path.exists():
    raise FileNotFoundError(
        f"Dataset not found: {file_path}\n"
        "Check that the JSON file is inside the data folder."
    )

with file_path.open("r", encoding="utf-8") as file:
    announcements = json.load(file)

if not isinstance(announcements, list):
    raise ValueError("Expected the JSON file to contain a list of announcements.")

total = len(announcements)

with_content = sum(
    1 for a in announcements
    if isinstance(a, dict) and a.get("full_content")
)

with_title = sum(
    1 for a in announcements
    if isinstance(a, dict) and a.get("title")
)

with_attachment = sum(
    1 for a in announcements
    if isinstance(a, dict) and a.get("attachment_present") is True
)

print("=== LPU SmartNotice Dataset Check ===")
print(f"Total announcements: {total}")
print(f"Announcements with titles: {with_title}")
print(f"Announcements with full content: {with_content}")
print(f"Announcements marked with attachments: {with_attachment}")

if announcements:
    print("\nAvailable fields:")
    print(list(announcements[0].keys()))