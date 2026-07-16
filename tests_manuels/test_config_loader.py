import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sys
sys.stdout.reconfigure(line_buffering=True)
from app.config_loader import load_repo_config, get_default_config, is_path_ignored

print("=== Test REVUE-44 : Configuration par repository ===\n")

repo_name = input("Nom du repo : ")

print("\n1️⃣ Chargement de la configuration...")
config = load_repo_config(repo_name)

print(f"\n📋 Configuration chargée :")
for key, value in config.items():
    print(f"   {key} : {value}")

print("\n2️⃣ Test du filtrage des chemins ignorés...")
test_paths = [
    "app/main.py",
    "migrations/0001_initial.py",
    "vendor/library.py"
]

for path in test_paths:
    ignored = is_path_ignored(path, config["ignored_paths"])
    status = "🚫 IGNORÉ" if ignored else "✅ Analysé"
    print(f"   {path} → {status}")

print("\n3️⃣ Test configuration par défaut (repo sans config)...")
default = get_default_config()
print(f"   severity_threshold : {default['severity_threshold']}")
print(f"   include_tests : {default['include_tests']}")
