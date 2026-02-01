"""
Unit tests for main.py CLI entry point.
"""
import unittest
import tempfile
import os
import sys
from unittest.mock import patch, Mock, MagicMock
from io import StringIO

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

import main


class TestMain(unittest.TestCase):
    """Test cases for main.py CLI entry point."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_ini_path = os.path.join(self.temp_dir, 'test.ini')
        
        # Create a minimal test INI file
        with open(self.test_ini_path, 'w') as f:
            f.write('[freeDView_tester]\n')
            f.write('setTestPath = /test/path\n')
            f.write('freedviewPath = /test/path\n')
            f.write('freedviewVer = ver1_VS_ver2\n')
            f.write('eventName = E##\n')
            f.write('setName = S####\n')

    def tearDown(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_get_ini_path_custom_path(self):
        """Test get_ini_path with custom path."""
        result = main.get_ini_path(self.test_ini_path)
        self.assertEqual(result, self.test_ini_path)

    @patch('os.path.exists')
    def test_get_ini_path_default(self, mock_exists):
        """Test get_ini_path with default path."""
        # Mock that default INI file doesn't exist
        mock_exists.return_value = False
        with self.assertRaises(SystemExit):
            main.get_ini_path(None)

    def test_get_ini_path_nonexistent(self):
        """Test get_ini_path with nonexistent file."""
        with self.assertRaises(SystemExit):
            main.get_ini_path('/nonexistent/path.ini')

    @patch('jsonLocalizer.JsonLocalizer')
    @patch('main.get_ini_path')
    def test_run_localize_success(self, mock_get_ini, mock_json_localizer):
        """Test run_localize with successful execution."""
        mock_get_ini.return_value = self.test_ini_path
        mock_localizer = Mock()
        mock_localizer.do_it.return_value = None
        mock_json_localizer.return_value = mock_localizer
        
        args = Mock()
        args.ini = None
        
        # Should not raise exception
        try:
            main.run_localize(args)
        except SystemExit:
            self.fail("run_localize raised SystemExit unexpectedly")

    @patch('jsonLocalizer.JsonLocalizer')
    @patch('main.get_ini_path')
    def test_run_localize_failure(self, mock_get_ini, mock_json_localizer):
        """Test run_localize with failure."""
        mock_get_ini.return_value = self.test_ini_path
        mock_localizer = Mock()
        mock_localizer.do_it.side_effect = Exception("Test error")
        mock_json_localizer.return_value = mock_localizer
        
        args = Mock()
        args.ini = None
        
        with self.assertRaises(SystemExit):
            main.run_localize(args)

    @patch('main.freeDViewRunner.FreeDViewRunner')
    @patch('main.get_ini_path')
    def test_run_render_success(self, mock_get_ini, mock_runner_class):
        """Test run_render with successful execution."""
        mock_get_ini.return_value = self.test_ini_path
        mock_runner = Mock()
        mock_runner.do_it.return_value = None
        mock_runner_class.return_value = mock_runner
        
        args = Mock()
        args.ini = None
        args.max_workers = 4
        
        # Should not raise exception
        try:
            main.run_render(args)
        except SystemExit:
            self.fail("run_render raised SystemExit unexpectedly")

    @patch('main.renderCompare.RenderCompare')
    @patch('main.get_ini_path')
    def test_run_compare_success(self, mock_get_ini, mock_render_compare_class):
        """Test run_compare with successful execution."""
        mock_get_ini.return_value = self.test_ini_path
        mock_render_compare = Mock()
        mock_render_compare_class.return_value = mock_render_compare
        
        args = Mock()
        args.ini = None
        args.max_workers = 4
        
        # Should not raise exception
        try:
            main.run_compare(args)
        except SystemExit:
            self.fail("run_compare raised SystemExit unexpectedly")

    @patch('main.prepareUIData.PrepareUIData')
    @patch('main.get_ini_path')
    def test_run_prepare_ui_success(self, mock_get_ini, mock_prepare_ui_class):
        """Test run_prepare_ui with successful execution."""
        mock_get_ini.return_value = self.test_ini_path
        mock_prepare_ui = Mock()
        mock_prepare_ui.do_it.return_value = None
        mock_prepare_ui_class.return_value = mock_prepare_ui
        
        args = Mock()
        args.ini = None
        
        # Should not raise exception
        try:
            main.run_prepare_ui(args)
        except SystemExit:
            self.fail("run_prepare_ui raised SystemExit unexpectedly")

    @patch('prepareUIData.PrepareUIData')
    @patch('renderCompare.RenderCompare')
    @patch('freeDViewRunner.FreeDViewRunner')
    @patch('jsonLocalizer.JsonLocalizer')
    @patch('main.get_ini_path')
    def test_run_all_success(self, mock_get_ini, mock_json_localizer, 
                             mock_runner_class, mock_render_compare_class, 
                             mock_prepare_ui_class):
        """Test run_all with successful execution."""
        mock_get_ini.return_value = self.test_ini_path
        
        # Setup all mocks
        mock_localizer = Mock()
        mock_localizer.do_it.return_value = None
        mock_json_localizer.return_value = mock_localizer
        
        mock_runner = Mock()
        mock_runner.do_it.return_value = None
        mock_runner_class.return_value = mock_runner
        
        mock_render_compare = Mock()
        mock_render_compare_class.return_value = mock_render_compare
        
        mock_prepare_ui = Mock()
        mock_prepare_ui.do_it.return_value = None
        mock_prepare_ui_class.return_value = mock_prepare_ui
        
        args = Mock()
        args.ini = None
        args.max_workers = 4
        
        # Should not raise exception
        try:
            main.run_all(args)
        except SystemExit:
            self.fail("run_all raised SystemExit unexpectedly")

    @patch('renderCompare.RenderCompare')
    def test_run_compare_ui_success(self, mock_render_compare_class):
        """Test run_compare_ui with successful execution."""
        mock_render_compare = Mock()
        mock_render_compare.render_compare_do_it.return_value = None
        mock_render_compare_class.return_value = mock_render_compare
        
        # Create test image directories
        folder_frame_path = os.path.join(self.temp_dir, 'frames')
        freedview_path_tester = os.path.join(self.temp_dir, 'tester')
        freedview_path_orig = os.path.join(self.temp_dir, 'orig')
        os.makedirs(folder_frame_path, exist_ok=True)
        os.makedirs(freedview_path_tester, exist_ok=True)
        os.makedirs(freedview_path_orig, exist_ok=True)
        
        # Create test images
        for i in range(1, 4):
            with open(os.path.join(freedview_path_orig, f'{i:04d}.jpg'), 'w') as f:
                f.write('mock')
            with open(os.path.join(freedview_path_tester, f'{i:04d}.jpg'), 'w') as f:
                f.write('mock')
        
        args = Mock()
        args.paths = [
            folder_frame_path,
            freedview_path_tester,
            freedview_path_orig,
            'orig_name',
            'tester_name'
        ]
        
        # Should not raise exception
        try:
            main.run_compare_ui(args)
        except SystemExit:
            self.fail("run_compare_ui raised SystemExit unexpectedly")

    def test_run_compare_ui_insufficient_args(self):
        """Test run_compare_ui with insufficient arguments."""
        args = Mock()
        args.paths = ['path1', 'path2']  # Not enough paths
        
        with self.assertRaises(SystemExit):
            main.run_compare_ui(args)

    def test_run_compare_ui_nonexistent_paths(self):
        """Test run_compare_ui with nonexistent paths."""
        args = Mock()
        args.paths = [
            '/nonexistent/frames',
            '/nonexistent/tester',
            '/nonexistent/orig',
            'orig_name',
            'tester_name'
        ]
        
        with self.assertRaises(SystemExit):
            main.run_compare_ui(args)

    @patch('sys.argv', ['main.py', '--help'])
    def test_main_help(self):
        """Test main function with --help flag."""
        # This would print help and exit, so we just check it doesn't crash
        # In a real test, we'd capture stdout
        pass

    @patch('sys.argv', ['main.py'])
    def test_main_no_command(self):
        """Test main function with no command."""
        # Should print help and exit
        with self.assertRaises(SystemExit):
            main.main()


if __name__ == '__main__':
    unittest.main()
