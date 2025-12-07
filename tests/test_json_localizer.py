"""
Unit tests for jsonLocalizer module.
"""
import unittest
import tempfile
import os
import json

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from jsonLocalizer import JsonLocalizer


class TestJsonLocalizer(unittest.TestCase):
    """Test cases for JsonLocalizer module."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.json_localizer = JsonLocalizer()

    def tearDown(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_is_event_matching_pattern(self):
        """Test event pattern matching with matching pattern."""
        pattern = "E##_##_##_##_##_##__"
        test_path = "/some/path/E12_34_56_78_90_12__"
        result = self.json_localizer.is_event(pattern, test_path)
        self.assertTrue(result, "Should match event pattern")

    def test_is_event_non_matching_pattern(self):
        """Test event pattern matching with non-matching pattern."""
        pattern = "E##_##_##_##_##_##__"
        test_path = "/some/path/SomeOtherFolder"
        result = self.json_localizer.is_event(pattern, test_path)
        self.assertFalse(result, "Should not match event pattern")

    def test_is_event_short_path(self):
        """Test event pattern matching with path shorter than pattern."""
        pattern = "E##_##_##_##_##_##__"
        test_path = "/some/path/E12"
        result = self.json_localizer.is_event(pattern, test_path)
        self.assertFalse(result, "Should not match if path is too short")

    def test_is_event_with_digits(self):
        """Test event pattern matching correctly handles digit wildcards."""
        pattern = "E##_##_##_##_##_##__"
        test_path = "/some/path/E12_34_56_78_90_12__"
        result = self.json_localizer.is_event(pattern, test_path)
        self.assertTrue(result, "Should match pattern with digits")


if __name__ == '__main__':
    unittest.main()

