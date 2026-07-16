import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.pr_metadata import get_pr_metadata

metadata = get_pr_metadata("mohamedbadishajji/test_agent_revue", 1)

print("=== Métadonnées de la PR ===")
for cle, valeur in metadata.items():
    print(f"{cle} : {valeur}")
