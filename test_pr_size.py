import sys
sys.stdout.reconfigure(line_buffering=True)
from app.analyzer import check_pr_size, limit_files_for_large_pr

print("=== Test REVUE-48 : Gestion des PRs volumineuses ===\n")

# Simuler une grosse PR avec 15 fichiers et beaucoup de lignes
fake_files = []
for i in range(15):
    lines_count = 80 if i < 5 else 20  # Les 5 premiers fichiers ont plus de lignes
    fake_files.append({
        "file_path": f"module_{i}.py",
        "language": "python",
        "patch": "fake patch content",
        "added_lines": [{"line_number": j, "content": f"line {j}"} for j in range(lines_count)]
    })

total_lines = sum(len(f["added_lines"]) for f in fake_files)
print(f"📋 PR simulée : {len(fake_files)} fichiers, {total_lines} lignes au total\n")

print("1️⃣ Vérification de la taille...")
size_info = check_pr_size(fake_files)
print(f"   Total lignes : {size_info['total_lines']}")
print(f"   Limite max : {size_info['max_allowed']}")
print(f"   PR volumineuse ? {size_info['is_large']}")

if size_info["is_large"]:
    print("\n2️⃣ Limitation des fichiers...")
    limited_files, ignored_count = limit_files_for_large_pr(fake_files)
    print(f"   Fichiers analysés : {len(limited_files)}")
    print(f"   Fichiers ignorés : {ignored_count}")
    print(f"\n   Fichiers retenus (les plus impactés) :")
    for f in limited_files:
        print(f"     - {f['file_path']} ({len(f['added_lines'])} lignes)")