import os
from datetime import datetime, timedelta

def get_file_age_days(file_path):
    if os.path.exists(file_path):
        mtime = os.path.getmtime(file_path)
        age = datetime.now() - datetime.fromtimestamp(mtime)
        return age.days
    return 999  # missing file = high priority

def score_file_staleness(age_days):
    return min(age_days * 0.8, 100)  # higher age = higher priority, capped

def calculate_priority():
    files_to_check = [
        "README.md",
        "Master_Index_Auto.md",
        "Master_Index.md",
        "Physics_Spine.md",
        "holosim/core.py"
    ]
    priorities = []
    for f in files_to_check:
        age = get_file_age_days(f)
        score = score_file_staleness(age)
        priorities.append((f, round(score, 1), age))
    
    priorities.sort(key=lambda x: x[1], reverse=True)
    return priorities

if __name__ == "__main__":
    print("HOLO Priority Scorer v0.1")
    print(calculate_priority())
    print("Run date:", datetime.now().strftime("%Y-%m-%d"))