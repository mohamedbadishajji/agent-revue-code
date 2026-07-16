import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.filters import filter_files, is_relevant

print("=== Test REVUE-5 : Filtrage intelligent des fichiers ===\n")

# Simulation de fichiers d'une PR
fake_diff_files = [
    {"file_path": "app/main.py", "language": "python", "patch": "...", "token_count": 100},
    {"file_path": "README.md", "language": "unknown", "patch": "...", "token_count": 50},
    {"file_path": "package-lock.json", "language": "unknown", "patch": "...", "token_count": 500},
    {"file_path": "app/github_client.py", "language": "python", "patch": "...", "token_count": 80},
    {"file_path": "logo.png", "language": "unknown", "patch": "...", "token_count": 10},
    {"file_path": "test_main.py", "language": "python", "patch": "...", "token_count": 60},
    {"file_path": "app/utils.js", "language": "javascript", "patch": "...", "token_count": 90},
    {"file_path": "yarn.lock", "language": "unknown", "patch": "...", "token_count": 200},
]

print("📁 Fichiers dans la PR :")
for f in fake_diff_files:
    print(f"   - {f['file_path']}")

print("\n1️⃣ Filtrage SANS les fichiers de test :")
filtered = filter_files(fake_diff_files, include_tests=False)
print(f"\nFichiers retenus pour analyse :")
for f in filtered:
    print(f"   ✅ {f['file_path']}")

print("\n2️⃣ Filtrage AVEC les fichiers de test :")
filtered_with_tests = filter_files(fake_diff_files, include_tests=True)
print(f"\nFichiers retenus pour analyse :")
for f in filtered_with_tests:
    print(f"   ✅ {f['file_path']}")
