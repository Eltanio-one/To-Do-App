import unittest
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

import src.app as app


class TestCase(unittest.TestCase):
    def setUp(self) -> None:
        app.app.testing = True
        self.app = app.app.test_client()

    def test_home(self) -> None:
        result = self.app.get("/")
