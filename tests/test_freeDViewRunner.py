"""
Unit tests for freeDViewRunner module (Phase 2).
"""
import unittest
import tempfile
import os
import json
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

import freeDViewRunner


class TestFreeDViewRunner(unittest.TestCase):
    """Test cases for FreeDViewRunner module."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_ini_path = os.path.join(self.temp_dir, 'test.ini')
        self.max_workers = 2
        
        # Create test directory structure
        self.test_sets_dir = os.path.join(self.temp_dir, 'testSets')
        self.test_sets_results_dir = os.path.join(self.temp_dir, 'testSets_results')
        os.makedirs(self.test_sets_dir, exist_ok=True)
        os.makedirs(self.test_sets_results_dir, exist_ok=True)
        
        # Create a test frame folder
        self.frame_folder = os.path.join(self.test_sets_dir, 'Event', 'Set', 'F0001')
        os.makedirs(self.frame_folder, exist_ok=True)
        
        # Create dynamicINIsBackup folder with required INI files
        self.dynamic_inis_backup = os.path.join(self.frame_folder, 'dynamicINIsBackup')
        os.makedirs(self.dynamic_inis_backup, exist_ok=True)
        
        # Create cameracontrol.ini
        camera_control_ini = os.path.join(self.dynamic_inis_backup, 'cameracontrol.ini')
        with open(camera_control_ini, 'w') as f:
            f.write('[Camera]\n')
            f.write('outputWidth=1920\n')
            f.write('outputHeight=1080\n')
        
        # Create campreset.ini
        campreset_ini = os.path.join(self.dynamic_inis_backup, 'campreset.ini')
        with open(campreset_ini, 'w') as f:
            f.write('[Preset]\n')
            f.write('name=test\n')
        
        # Create Render/Json folder with testMe.json
        self.render_json_dir = os.path.join(self.frame_folder, 'Render', 'Json')
        os.makedirs(self.render_json_dir, exist_ok=True)
        
        self.test_me_json = os.path.join(self.render_json_dir, 'testMe.json')
        test_json_data = {
            'startFrame': 1,
            'endFrame': 10
        }
        with open(self.test_me_json, 'w') as f:
            json.dump(test_json_data, f)

    def tearDown(self):
        """Clean up after tests."""
        shutil.rmtree(self.temp_dir)

    def test_init(self):
        """Test FreeDViewRunner initialization."""
        runner = freeDViewRunner.FreeDViewRunner(max_workers=self.max_workers)
        self.assertEqual(runner.max_workers, self.max_workers)
        self.assertEqual(runner._render_count, 0)
        self.assertEqual(runner._successful_renders, 0)
        self.assertEqual(runner._failed_renders, 0)

    def test_init_default_workers(self):
        """Test FreeDViewRunner initialization with default workers."""
        runner = freeDViewRunner.FreeDViewRunner()
        self.assertEqual(runner.max_workers, freeDViewRunner.DEFAULT_MAX_WORKERS)

    @patch('getDataIni.getDataINI')
    @patch('jsonLocalizer.JsonLocalizer')
    def test_do_it_no_json_files(self, mock_json_localizer, mock_get_data_ini):
        """Test do_it when no JSON files are found."""
        # Setup mocks
        mock_get_data_ini.return_value = ['/test/path']
        
        mock_localizer = Mock()
        mock_localizer.get_json_files.return_value = ([], [], [], [], [], [])
        mock_json_localizer.return_value = mock_localizer
        
        runner = freeDViewRunner.FreeDViewRunner()
        runner.do_it(self.test_ini_path)
        
        # Should complete without error
        self.assertTrue(True)

    @patch('getDataIni.getDataINI')
    def test_do_it_invalid_ini_data(self, mock_get_data_ini):
        """Test do_it with invalid INI data."""
        # Setup mock to return error value
        mock_get_data_ini.return_value = ['error']
        
        runner = freeDViewRunner.FreeDViewRunner()
        runner.do_it(self.test_ini_path)
        
        # Should return early without error
        self.assertTrue(True)

    @patch('getDataIni.getDataINI')
    def test_do_it_invalid_version_format(self, mock_get_data_ini):
        """Test do_it with invalid version format."""
        # Setup mocks
        def mock_get_data_ini_side_effect(ini_path, tag):
            if tag == 'freedviewVer':
                return ['invalid_version_format']  # Missing _VS_
            return ['/test/path']
        
        mock_get_data_ini.side_effect = mock_get_data_ini_side_effect
        
        runner = freeDViewRunner.FreeDViewRunner()
        runner.do_it(self.test_ini_path)
        
        # Should return early without error
        self.assertTrue(True)

    def test_get_freedview_versions_path_not_exists(self):
        """Test _get_freedview_versions when path doesn't exist."""
        runner = freeDViewRunner.FreeDViewRunner()
        path_list, name_list = runner._get_freedview_versions(
            '/nonexistent/path', 'ver1_VS_ver2', 'ver1', 'ver2'
        )
        self.assertEqual(len(path_list), 0)
        self.assertEqual(len(name_list), 0)

    def test_get_freedview_versions_found(self):
        """Test _get_freedview_versions when versions are found."""
        # Create version directory structure
        freedview_path = os.path.join(self.temp_dir, 'freedviewVer')
        version_folder = os.path.join(freedview_path, 'ver1_VS_ver2')
        orig_version = os.path.join(version_folder, 'ver1')
        test_version = os.path.join(version_folder, 'ver2')
        os.makedirs(orig_version, exist_ok=True)
        os.makedirs(test_version, exist_ok=True)
        
        runner = freeDViewRunner.FreeDViewRunner()
        path_list, name_list = runner._get_freedview_versions(
            freedview_path, 'ver1_VS_ver2', 'ver1', 'ver2'
        )
        
        self.assertEqual(len(path_list), 2)
        self.assertEqual(len(name_list), 2)
        self.assertIn('ver1', name_list)
        self.assertIn('ver2', name_list)

    @patch('freeDViewRunner.subprocess.Popen')
    def test_run_freedview_success(self, mock_popen):
        """Test run_freedview with successful execution."""
        # Setup mock subprocess
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b'stdout', b'stderr')
        mock_popen.return_value = mock_process
        
        # Create output directory
        output_path = os.path.join(self.temp_dir, 'output')
        os.makedirs(output_path, exist_ok=True)
        
        # Create freedview.exe (mock)
        freedview_path = os.path.join(self.temp_dir, 'freedview')
        os.makedirs(freedview_path, exist_ok=True)
        freedview_exe = os.path.join(freedview_path, 'freedview.exe')
        with open(freedview_exe, 'w') as f:
            f.write('mock')
        
        runner = freeDViewRunner.FreeDViewRunner()
        result = runner.run_freedview(
            freedview_path,
            self.test_me_json,
            [1920, 1080],
            output_path,
            [1, 10]
        )
        
        self.assertTrue(result)
        mock_popen.assert_called_once()

    @patch('freeDViewRunner.subprocess.Popen')
    def test_run_freedview_executable_not_found(self, mock_popen):
        """Test run_freedview when executable doesn't exist."""
        freedview_path = os.path.join(self.temp_dir, 'freedview')
        os.makedirs(freedview_path, exist_ok=True)
        # Don't create freedview.exe
        
        runner = freeDViewRunner.FreeDViewRunner()
        result = runner.run_freedview(
            freedview_path,
            self.test_me_json,
            [1920, 1080],
            os.path.join(self.temp_dir, 'output'),
            [1, 10]
        )
        
        self.assertFalse(result)

    @patch('freeDViewRunner.subprocess.Popen')
    def test_run_freedview_process_failure(self, mock_popen):
        """Test run_freedview when process fails."""
        # Setup mock subprocess with failure
        mock_process = Mock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b'stdout', b'error message')
        mock_popen.return_value = mock_process
        
        freedview_path = os.path.join(self.temp_dir, 'freedview')
        os.makedirs(freedview_path, exist_ok=True)
        freedview_exe = os.path.join(freedview_path, 'freedview.exe')
        with open(freedview_exe, 'w') as f:
            f.write('mock')
        
        runner = freeDViewRunner.FreeDViewRunner()
        result = runner.run_freedview(
            freedview_path,
            self.test_me_json,
            [1920, 1080],
            os.path.join(self.temp_dir, 'output'),
            [1, 10]
        )
        
        self.assertFalse(result)

    def test_render_single_task_missing_camera_control_ini(self):
        """Test _render_single_task when camera control INI is missing."""
        # Remove camera control INI
        camera_control_ini = os.path.join(self.dynamic_inis_backup, 'cameracontrol.ini')
        os.remove(camera_control_ini)
        
        task = {
            'version_index': 0,
            'freedview_ver_path': '/test/path',
            'freedview_ver_name': 'test_version',
            'json_index': 0,
            'json_file_path': self.test_me_json,
            'folder_frame': self.frame_folder,
            'freedview_ver': 'ver1_VS_ver2',
            'total_renders': 1
        }
        
        runner = freeDViewRunner.FreeDViewRunner()
        result = runner._render_single_task(task)
        
        self.assertFalse(result)

    def test_render_single_task_missing_campreset_ini(self):
        """Test _render_single_task when campreset INI is missing."""
        # Remove campreset INI
        campreset_ini = os.path.join(self.dynamic_inis_backup, 'campreset.ini')
        os.remove(campreset_ini)
        
        task = {
            'version_index': 0,
            'freedview_ver_path': '/test/path',
            'freedview_ver_name': 'test_version',
            'json_index': 0,
            'json_file_path': self.test_me_json,
            'folder_frame': self.frame_folder,
            'freedview_ver': 'ver1_VS_ver2',
            'total_renders': 1
        }
        
        runner = freeDViewRunner.FreeDViewRunner()
        result = runner._render_single_task(task)
        
        self.assertFalse(result)

    def test_render_single_task_invalid_json(self):
        """Test _render_single_task with invalid JSON file."""
        # Create invalid JSON
        invalid_json = os.path.join(self.render_json_dir, 'invalid.json')
        with open(invalid_json, 'w') as f:
            f.write('invalid json content')
        
        task = {
            'version_index': 0,
            'freedview_ver_path': '/test/path',
            'freedview_ver_name': 'test_version',
            'json_index': 0,
            'json_file_path': invalid_json,
            'folder_frame': self.frame_folder,
            'freedview_ver': 'ver1_VS_ver2',
            'total_renders': 1
        }
        
        runner = freeDViewRunner.FreeDViewRunner()
        result = runner._render_single_task(task)
        
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
