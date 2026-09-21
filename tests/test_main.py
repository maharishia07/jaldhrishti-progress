"""Offline regression checks for the repository reorganisation."""

import importlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.config import settings
from src.services.engine.financial_engine import calculate_financial_plan


class StructureTests(unittest.TestCase):
    def test_imports_have_no_network_database_or_environment_side_effects(self):
        code = """
import importlib, os, socket, sqlite3
from unittest.mock import patch
with patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden')), patch.object(sqlite3, 'connect', side_effect=AssertionError('database forbidden')), patch('dotenv.load_dotenv', side_effect=AssertionError('env loading forbidden')):
    for name in ['main', 'src.main', 'src.bot.handlers', 'src.services.scheduler.reminders', 'scripts.demo_reminder', 'scripts.check_geospatial']:
        importlib.import_module(name)
print('PASS: imports are offline and side-effect free')
"""
        result = subprocess.run([sys.executable, "-c", code], cwd=settings.PROJECT_ROOT,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_launcher_delegates_to_package(self):
        import main
        from src.main import main as package_main
        self.assertIs(main.main, package_main)

    def test_environment_load_is_root_relative(self):
        with patch("dotenv.load_dotenv") as load:
            settings.load_environment()
        load.assert_called_once_with(settings.PROJECT_ROOT / ".env", override=False)

    def test_database_override_keeps_legacy_relative_semantics(self):
        with patch.dict(os.environ, {"JALDHRISHTI_DB": "custom/state.db"}):
            self.assertEqual(settings.database_path(), "custom/state.db")

    def test_existing_legacy_database_is_not_reset(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"JALDHRISHTI_DB": ""}):
            root = Path(directory)
            legacy = root / "scheduler" / "jaldhrishti.db"
            legacy.parent.mkdir()
            legacy.touch()
            with patch.object(settings, "PROJECT_ROOT", root):
                self.assertEqual(settings.database_path(), str(legacy))

    def test_fresh_database_uses_output_folder(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"JALDHRISHTI_DB": ""}):
            root = Path(directory)
            with patch.object(settings, "PROJECT_ROOT", root), patch.object(settings, "OUTPUT_DIR", root / "data/output"):
                self.assertEqual(settings.database_path(), str(root / "data/output/jaldhrishti.db"))

    def test_financial_rules_do_not_depend_on_working_directory(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                plan = calculate_financial_plan(10000)
            finally:
                os.chdir(previous)
        self.assertEqual(plan["project_cost"], 100000)
        self.assertEqual(plan["loan_amount"], 90000)
        self.assertEqual(plan["scheme_name"], "micro_finance")
        self.assertAlmostEqual(sum(row["principal"] for row in plan["repayment_schedule"]), 90000, places=2)

    def test_financial_validation_and_term_loan(self):
        self.assertEqual(calculate_financial_plan(0), {"error": "invalid margin money"})
        self.assertEqual(calculate_financial_plan(-1), {"error": "invalid margin money"})
        self.assertEqual(calculate_financial_plan(600000), {"error": "exceeds scheme limit"})
        self.assertEqual(calculate_financial_plan(100000)["scheme_name"], "term_loan")

    def test_demo_uses_temporary_database_and_restores_path(self):
        from scripts.demo_reminder import main
        from src.services.scheduler import storage
        original = storage.DB_PATH
        with patch("socket.socket.connect", side_effect=AssertionError("network forbidden")):
            main()
        self.assertEqual(storage.DB_PATH, original)

    def test_geospatial_script_requires_live_opt_in(self):
        from scripts.check_geospatial import main
        with patch("socket.socket.connect", side_effect=AssertionError("network forbidden")):
            with self.assertRaises(SystemExit) as raised:
                main([])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
