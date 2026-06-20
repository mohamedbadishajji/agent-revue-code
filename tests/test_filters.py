import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.filters import is_relevant, is_test_file, is_auto_generated


def test_is_relevant_python_file():
    """Test qu'un fichier Python est considéré pertinent"""
    assert is_relevant("app/main.py") == True


def test_is_relevant_markdown_ignored():
    """Test qu'un fichier markdown est ignoré"""
    assert is_relevant("README.md") == False


def test_is_relevant_lock_file_ignored():
    """Test qu'un fichier lock est ignoré"""
    assert is_relevant("package-lock.json") == False


def test_is_test_file_detection():
    """Test la détection des fichiers de test"""
    assert is_test_file("test_main.py") == True
    assert is_test_file("app/main.py") == False


def test_is_auto_generated_detection():
    """Test la détection des fichiers auto-générés"""
    assert is_auto_generated("yarn.lock") == True
    assert is_auto_generated("app/main.py") == False


def test_is_relevant_with_tests_excluded():
    """Test que les fichiers de test sont exclus par défaut"""
    assert is_relevant("test_main.py", include_tests=False) == False


def test_is_relevant_with_tests_included():
    """Test que les fichiers de test sont inclus si demandé"""
    assert is_relevant("test_main.py", include_tests=True) == True