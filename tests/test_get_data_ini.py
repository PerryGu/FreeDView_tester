"""
Unit tests for getDataIni module.
"""
import unittest
import tempfile
import os
import configparser

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

import getDataIni


class TestGetDataIni(unittest.TestCase):
    """Test cases for getDataIni module."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_ini_path = os.path.join(self.temp_dir, 'test.ini')
        
        # Create a test INI file
        config = configparser.ConfigParser()
        config['test_section'] = {
            'testKey': 'testValue',
            'testPath': '/some/path/to/file',
            'testNumber': '123'
        }
        
        with open(self.test_ini_path, 'w') as f:
            config.write(f)

    def tearDown(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_get_data_ini_existing_key(self):
        """Test reading existing key from INI file."""
        result = getDataIni.getDataINI(self.test_ini_path, 'testKey')
        self.assertEqual(result[0], 'testValue')

    def test_get_data_ini_nonexistent_key(self):
        """Test reading non-existent key returns error."""
        result = getDataIni.getDataINI(self.test_ini_path, 'nonexistent')
        self.assertEqual(result[0], 'error')

    def test_get_data_ini_nonexistent_file(self):
        """Test reading from non-existent file returns error."""
        result = getDataIni.getDataINI('/nonexistent/path.ini', 'testKey')
        self.assertEqual(result[0], 'error')

    def test_get_data_ini_file_check_valid(self):
        """Test file_check with valid file path."""
        # Create a test file
        test_file_path = os.path.join(self.temp_dir, 'testfile.txt')
        with open(test_file_path, 'w') as f:
            f.write('test')
        
        config = configparser.ConfigParser()
        config['test_section'] = {'testPath': test_file_path}
        ini_path = os.path.join(self.temp_dir, 'test2.ini')
        with open(ini_path, 'w') as f:
            config.write(f)
        
        result = getDataIni.getDataINI(ini_path, 'testPath', file_check=1)
        self.assertEqual(result[0], test_file_path)

    def test_get_data_ini_file_check_invalid(self):
        """Test file_check with invalid file path."""
        config = configparser.ConfigParser()
        config['test_section'] = {'testPath': '/nonexistent/file.txt'}
        ini_path = os.path.join(self.temp_dir, 'test3.ini')
        with open(ini_path, 'w') as f:
            config.write(f)
        
        result = getDataIni.getDataINI(ini_path, 'testPath', file_check=1)
        self.assertEqual(result[0], 'error')


if __name__ == '__main__':
    unittest.main()

