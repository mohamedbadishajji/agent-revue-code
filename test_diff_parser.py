from app.diff_parser import extract_diff, parse_diff, chunk_diff

print("=== Test REVUE-4 : Extraction et parsing du diff ===\n")

# Étape 1 : Extraire le diff
print("1️⃣ Extraction du diff...")
diff_files = extract_diff("mohamedbadishajji/test_agent_revue", 3)

print(f"\n📁 Fichiers trouvés : {len(diff_files)}")
for f in diff_files:
    print(f"  - {f['file_path']} ({f['language']}) — {f['additions']} additions")

# Étape 2 : Parser le diff
print("\n2️⃣ Parsing du diff...")
parsed_files = parse_diff(diff_files)

for f in parsed_files:
    print(f"\n📄 Fichier : {f['file_path']}")
    print(f"   Tokens estimés : {f['token_count']}")
    print(f"   Lignes ajoutées :")
    for line in f['added_lines']:
        print(f"     ligne {line['line_number']} (position {line['patch_position']}) : {line['content']}")

# Étape 3 : Chunking
print("\n3️⃣ Chunking du diff...")
chunks = chunk_diff(parsed_files)
print(f"   Nombre de chunks : {len(chunks)}")