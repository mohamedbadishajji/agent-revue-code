import os
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """Tu es un expert en revue de code et securite.
Tu analyses uniquement le diff fourni.

REGLES :
1. Signale les bugs evidents (division par zero, index out of range, null pointer)
2. Signale TOUJOURS les problemes de securite (mots de passe hardcodes, cles API dans le code, injections SQL)
3. Signale les erreurs de logique claires
4. Ne commente PAS le style ou le formatage
5. Sois direct et precis
6. Pour CHAQUE probleme, fournis le CODE EXACT de correction (pas juste une explication)

NIVEAUX DE SEVERITE :
- critical : faille de securite (mot de passe, cle API hardcodee)
- high : bug qui peut causer un crash
- medium : probleme de logique
- low : mauvaise pratique

FORMAT DE REPONSE (JSON uniquement, sans backticks, sans texte avant ou apres) :
{"issues": [{"line": <numero>, "severity": "<critical|high|medium|low>", "type": "<bug|security|performance|logic>", "description": "<description>", "suggestion": "<explication textuelle>", "fix_code": "<code exact de remplacement de cette ligne uniquement, sans markdown>"}], "summary": "<resume>"}

IMPORTANT pour fix_code :
- Doit etre le code EXACT qui remplace la ligne problematique
- Une seule ligne de code (ou plusieurs lignes separees par \\n si necessaire)
- Pas d explication, juste le code pret a etre applique
- Si impossible de generer un code de correction precis, laisser fix_code vide ""

Si aucun probleme : {"issues": [], "summary": "Code correct, aucun probleme detecte."}"""


SYSTEM_PROMPT_SMELLS = """Tu es un expert en qualite de code et clean code.
Tu analyses uniquement le diff fourni.

DETECTE UNIQUEMENT ces problemes de qualite :
1. Fonctions trop longues (plus de 20 lignes)
2. Code duplique ou copie-colle
3. Nommage incorrect (variables/fonctions avec noms trop courts ou non descriptifs)
4. Trop de parametres dans une fonction (plus de 4)
5. Magic numbers (nombres sans constante nommee)
6. Commentaires inutiles ou trompeurs
7. Fonction qui fait trop de choses a la fois

REGLES STRICTES :
1. Ne signale QUE les problemes de qualite - pas les bugs ni les vulnerabilites
2. Sois conservateur - signale uniquement les problemes evidents
3. Ne commente PAS le style de formatage (indentation, espaces)

FORMAT DE REPONSE (JSON uniquement, sans backticks, sans texte avant ou apres) :
{"smells": [{"line": <numero>, "type": "<long_function|duplicate_code|bad_naming|too_many_params|magic_number|useless_comment|does_too_much>", "description": "<description>", "suggestion": "<suggestion>"}], "quality_score": <score de 0 a 10>, "summary": "<resume>"}

Si aucun probleme : {"smells": [], "quality_score": 10, "summary": "Code de bonne qualite."}"""


SYSTEM_PROMPT_SECURITY = """Tu es un expert en cybersecurite et en analyse de code.
Tu analyses uniquement le diff fourni.

DETECTE TOUTES ces vulnerabilites de securite :

OWASP TOP 10 :
1. Injection (SQL, NoSQL, OS, LDAP, commande)
2. Authentification cassee (mots de passe faibles, sessions non expirees, credentials hardcodes)
3. Exposition de donnees sensibles (cles API, tokens, mots de passe, secrets)
4. Entites XML externes - XXE (parsing XML non securise)
5. Controle d acces casse (acces non autorise aux ressources)
6. Mauvaise configuration securite (debug en prod, permissions trop larges)
7. XSS - Cross-Site Scripting (injection de scripts dans le HTML)
8. Deserialisation non securisee (pickle.loads, eval, exec)
9. Composants vulnerables (bibliotheques obsoletes ou avec failles connues)
10. Logging insuffisant (absence de logs de securite)

VULNERABILITES SUPPLEMENTAIRES :
11. Path Traversal (acces aux fichiers systeme via ../)
12. Command Injection (os.system, subprocess avec input utilisateur)
13. SSRF - Server Side Request Forgery (requests.get avec URL utilisateur)
14. Cryptographie faible (md5, sha1 pour mots de passe, cles trop courtes)
15. Race Condition (acces concurrent non protege)
16. Open Redirect (redirection vers URL utilisateur non validee)
17. CSRF - Cross-Site Request Forgery (requetes forgees cross-site)
18. ReDoS - Regex Denial of Service (regex catastrophique)
19. Clickjacking (iframes malveillantes sans protection)
20. Buffer Overflow (depassement de memoire)
21. Hardcoded secrets (mots de passe, cles, tokens en dur dans le code)
22. Insecure random (utilisation de random() pour la securite)
23. Directory listing (exposition de la structure des fichiers)
24. Insecure deserialization (yaml.load sans Loader, json non valide)
25. Prototype pollution (JavaScript uniquement)

NIVEAUX DE SEVERITE CVSS :
- critical (CVSS 9.0-10.0) : Exploitation immediate possible, impact total
- high (CVSS 7.0-8.9) : Exploitation facile, impact important
- medium (CVSS 4.0-6.9) : Exploitation moderee, impact partiel
- low (CVSS 0.1-3.9) : Exploitation difficile, impact limite

REGLES STRICTES :
1. Signale TOUTES les vulnerabilites de securite detectees
2. Ne commente PAS les bugs fonctionnels ni les code smells
3. Indique le type de vulnerabilite OWASP ou CWE si possible
4. Sois precis sur l impact potentiel

FORMAT DE REPONSE (JSON uniquement, sans backticks, sans texte avant ou apres) :
{"vulnerabilities": [{"line": <numero>, "severity": "<critical|high|medium|low>", "type": "<type de vulnerabilite>", "owasp": "<categorie OWASP>", "description": "<description precise>", "impact": "<impact potentiel>", "suggestion": "<correction recommandee>"}], "risk_score": <score de 0 a 10>, "summary": "<resume securite>"}

Si aucune vulnerabilite : {"vulnerabilities": [], "risk_score": 0, "summary": "Aucune vulnerabilite detectee."}"""


def build_code_review_prompt(file_path: str, language: str, patch: str) -> str:
    return f"""Analyse ce diff de code {language} et detecte les bugs,
vulnerabilites de securite et problemes de logique.

Fichier : {file_path}
Langage : {language}

Diff :
{patch}

Reponds UNIQUEMENT en JSON selon le format demande. Sans backticks."""


def build_test_generation_prompt(file_path: str, language: str, added_lines: list) -> str:
    functions = "\n".join([line["content"] for line in added_lines
                          if "def " in line["content"] or "function " in line["content"]])

    return f"""Genere des tests unitaires pour les nouvelles fonctions detectees.

Fichier : {file_path}
Langage : {language}
Nouvelles fonctions :
{functions}

Reponds UNIQUEMENT avec le code de test en {language}, sans explication."""


def build_summary_prompt(all_issues: list, pr_title: str) -> str:
    issues_text = "\n".join([
        f"- [{issue['severity']}] {issue['description']}"
        for issue in all_issues
    ])

    return f"""Genere un resume professionnel de la revue de code pour cette PR.

Titre de la PR : {pr_title}
Problemes detectes :
{issues_text if issues_text else "Aucun probleme detecte"}

Reponds avec un resume en markdown de 3-5 lignes maximum."""


def build_code_smells_prompt(file_path: str, language: str, patch: str) -> str:
    return f"""Analyse ce diff de code {language} et detecte uniquement
les problemes de qualite et code smells.

Fichier : {file_path}
Langage : {language}

Diff :
{patch}

Reponds UNIQUEMENT en JSON selon le format demande. Sans backticks."""


def build_security_prompt(file_path: str, language: str, patch: str) -> str:
    return f"""Analyse ce diff de code {language} et detecte TOUTES
les vulnerabilites de securite presentes.

Fichier : {file_path}
Langage : {language}

Diff :
{patch}

Reponds UNIQUEMENT en JSON selon le format demande. Sans backticks."""


# ══════════════════════════════════════════════
# REVUE-35 : Analyse multi-langages
# ══════════════════════════════════════════════

LANGUAGE_SPECIFIC_RULES = {
    "python": """
REGLES SPECIFIQUES PYTHON :
- Detecter les divisions sans verification (ZeroDivisionError)
- Detecter les acces a des index sans verification (IndexError)
- Detecter les imports manquants ou incorrects
- Detecter l utilisation de 'except Exception' trop large
- Detecter les f-strings mal formees
- Detecter l utilisation de 'eval()' ou 'exec()'
- Detecter les comparaisons avec 'is' au lieu de '=='
- Detecter les variables globales inutiles
- Detecter les fonctions recursives sans cas de base
""",
    "javascript": """
REGLES SPECIFIQUES JAVASCRIPT :
- Detecter l utilisation de '==' au lieu de '==='
- Detecter l utilisation de 'var' au lieu de 'let' ou 'const'
- Detecter les callback hell (imbrication excessive de callbacks)
- Detecter les promises non gerees (.catch() manquant)
- Detecter les console.log() oublies en production
- Detecter les acces a des proprietes d objets non verifiees
- Detecter l utilisation de 'document.write()'
""",
    "typescript": """
REGLES SPECIFIQUES TYPESCRIPT :
- Detecter l utilisation du type 'any' non justifiee
- Detecter les assertions de type non securisees (as Type)
- Detecter les interfaces mal definies
- Detecter les types optionnels non verifies
- Detecter les enums mal utilises
- Detecter les generiques trop larges
""",
    "java": """
REGLES SPECIFIQUES JAVA :
- Detecter les NullPointerException potentielles
- Detecter les resource leaks (streams non fermes)
- Detecter les exceptions avalees (catch vide)
- Detecter les comparaisons de String avec ==
- Detecter les collections non typees (raw types)
- Detecter les synchronisations incorrectes
""",
    "go": """
REGLES SPECIFIQUES GO :
- Detecter les erreurs non gerees (err != nil manquant)
- Detecter les goroutines qui fuient (goroutine leak)
- Detecter les nil pointer dereferences
- Detecter les race conditions sur les variables partagees
- Detecter les defer mal places dans les boucles
- Detecter les channels non fermes
""",
    "php": """
REGLES SPECIFIQUES PHP :
- Detecter les injections SQL (requetes non parametrees)
- Detecter les XSS (echo sans htmlspecialchars)
- Detecter les inclusions de fichiers dangereuses (include $var)
- Detecter l utilisation de fonctions obsoletes (mysql_*)
- Detecter les variables non initialisees
- Detecter les sessions non securisees
""",
    "ruby": """
REGLES SPECIFIQUES RUBY :
- Detecter les injections SQL dans ActiveRecord
- Detecter l utilisation de 'eval' avec des entrees utilisateur
- Detecter les mass assignment non proteges
- Detecter les symboles crees depuis des entrees utilisateur
- Detecter les redirections non validees
- Detecter les secrets hardcodes
""",
    "csharp": """
REGLES SPECIFIQUES C# :
- Detecter les NullReferenceException potentielles
- Detecter les SQL Injection dans les requetes ADO.NET
- Detecter les ressources non liberees (IDisposable sans using)
- Detecter les exceptions avalees (catch vide)
- Detecter les conversions non securisees (cast sans as/is)
- Detecter les threads non synchronises
""",
    "swift": """
REGLES SPECIFIQUES SWIFT :
- Detecter les force unwrap dangereux (!)
- Detecter les memory leaks (retain cycles dans les closures)
- Detecter les acces concurrents non proteges
- Detecter les force cast dangereux (as!)
- Detecter les optionals mal geres
- Detecter les strong reference cycles
""",
    "kotlin": """
REGLES SPECIFIQUES KOTLIN :
- Detecter les NullPointerException potentielles
- Detecter les force unwrap dangereux (!!)
- Detecter les coroutines mal gerees
- Detecter les memory leaks dans les lambdas
- Detecter les conversions non securisees
- Detecter les acces concurrents non proteges
""",
    "c": """
REGLES SPECIFIQUES C :
- Detecter les buffer overflows (strcpy, gets sans limite)
- Detecter les memory leaks (malloc sans free)
- Detecter les pointeurs non initialises
- Detecter les acces hors limites aux tableaux
- Detecter les integer overflows
- Detecter les use-after-free
- Detecter les format string vulnerabilities
""",
    "cpp": """
REGLES SPECIFIQUES C++ :
- Detecter les buffer overflows
- Detecter les memory leaks (new sans delete)
- Detecter les dangling pointers
- Detecter les double free
- Detecter les use-after-free
- Detecter les exceptions non gerees
- Detecter les race conditions dans les threads
- Detecter l utilisation de fonctions dangereuses (strcpy, sprintf)
""",
    "unknown": """
REGLES GENERALES :
- Detecter les bugs logiques evidents
- Detecter les vulnerabilites de securite basiques
- Detecter les mauvaises pratiques courantes
- Detecter les credentials hardcodes
- Detecter les injections potentielles
"""
}


def build_language_specific_prompt(file_path: str, language: str, patch: str, custom_instructions: str = "") -> str:
    """
    Construit un prompt optimise selon le langage de programmation
    REVUE-35 : Analyse multi-langages
    REVUE-45 : Inclut les instructions personnalisees du repository
    """
    language_rules = LANGUAGE_SPECIFIC_RULES.get(
        language,
        LANGUAGE_SPECIFIC_RULES["unknown"]
    )

    custom_section = ""
    if custom_instructions and custom_instructions.strip():
        custom_section = f"""

INSTRUCTIONS SPECIFIQUES DU PROJET (priorite haute) :
{custom_instructions}
"""

    return f"""Analyse ce diff de code {language} en appliquant les regles specifiques a ce langage.

Fichier : {file_path}
Langage : {language}

{language_rules}
{custom_section}
Diff :
{patch}

Reponds UNIQUEMENT en JSON selon le format demande. Sans backticks.
Format : {{"issues": [{{"line": <numero>, "severity": "<critical|high|medium|low>", "type": "<bug|security|performance|logic>", "description": "<description>", "suggestion": "<suggestion>", "fix_code": "<code exact>"}}], "summary": "<resume>"}}"""