"""
Unit tests for prepareUIData module (Phase 4).
"""
import unittest
import tempfile
import os
import shutil
import xml.dom.minidom as minidom
from pathlib import Path

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from prepareUIData import PrepareUIData, STATUS_READY, STATUS_RENDERED, STATUS_NOT_READY


class TestPrepareUIData(unittest.TestCase):
    """Test cases for PrepareUIData module."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_sets_dir = os.path.join(self.temp_dir, 'testSets')
        self.test_sets_results_dir = os.path.join(self.temp_dir, 'testSets_results')
        os.makedirs(self.test_sets_dir, exist_ok=True)
        os.makedirs(self.test_sets_results_dir, exist_ok=True)
        
        # Create test frame folder structure
        self.frame_folder = os.path.join(self.test_sets_dir, 'Event', 'Set', 'F0001')
        os.makedirs(self.frame_folder, exist_ok=True)

    def tearDown(self):
        """Clean up after tests."""
        shutil.rmtree(self.temp_dir)

    def test_init(self):
        """Test PrepareUIData initialization."""
        prepare_ui = PrepareUIData()
        self.assertIsNotNone(prepare_ui)

    def test_scan_test_sets_basic(self):
        """Test _scan_test_sets with basic structure."""
        prepare_ui = PrepareUIData()
        tests = prepare_ui._scan_test_sets(
            self.test_sets_dir,
            None,
            None,
            set()
        )
        
        self.assertEqual(len(tests), 1)
        self.assertEqual(tests[0]['eventName'], 'Event')
        self.assertEqual(tests[0]['setName'], 'Set')

    def test_scan_test_sets_with_sport_type(self):
        """Test _scan_test_sets with sport type structure."""
        # Create SportType/Event/Set/F structure
        sport_frame_folder = os.path.join(self.test_sets_dir, 'NFL', 'Event', 'Set', 'F0002')
        os.makedirs(sport_frame_folder, exist_ok=True)
        
        prepare_ui = PrepareUIData()
        tests = prepare_ui._scan_test_sets(
            self.test_sets_dir,
            None,
            None,
            set()
        )
        
        # Should find both frames
        self.assertGreaterEqual(len(tests), 2)
        
        # Find the NFL test
        nfl_test = next((t for t in tests if t.get('sportType') == 'NFL'), None)
        self.assertIsNotNone(nfl_test)
        self.assertEqual(nfl_test['sportType'], 'NFL')

    def test_extract_metadata_from_test_sets_path(self):
        """Test _extract_metadata_from_test_sets_path."""
        prepare_ui = PrepareUIData()
        
        # Test basic structure: Event/Set/F
        metadata = prepare_ui._extract_metadata_from_test_sets_path(
            self.frame_folder,
            self.test_sets_dir
        )
        
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata['eventName'], 'Event')
        self.assertEqual(metadata['frameFolderPath'], self.frame_folder)

    def test_determine_status_not_ready(self):
        """Test _determine_status for Not Ready status."""
        prepare_ui = PrepareUIData()
        status, thumbnail = prepare_ui._determine_status(
            self.frame_folder,
            self.test_sets_results_dir
        )
        
        self.assertEqual(status, STATUS_NOT_READY)

    def test_determine_status_ready(self):
        """Test _determine_status for Ready status (with compareResult.xml)."""
        # Create results structure with compareResult.xml
        frame_results = self.frame_folder.replace('testSets', 'testSets_results')
        version_folder = os.path.join(frame_results, 'ver1_VS_ver2')
        results_folder = os.path.join(version_folder, 'results')
        os.makedirs(results_folder, exist_ok=True)
        
        # Create compareResult.xml
        xml_file = os.path.join(results_folder, 'compareResult.xml')
        doc = minidom.Document()
        root = doc.createElement('root')
        doc.appendChild(root)
        with open(xml_file, 'w') as f:
            f.write(doc.toprettyxml())
        
        prepare_ui = PrepareUIData()
        status, thumbnail = prepare_ui._determine_status(
            self.frame_folder,
            self.test_sets_results_dir
        )
        
        self.assertEqual(status, STATUS_READY)

    def test_determine_status_rendered(self):
        """Test _determine_status for Rendered not compare status."""
        # Create results structure with rendered images but no compareResult.xml
        frame_results = self.frame_folder.replace('testSets', 'testSets_results')
        version_folder = os.path.join(frame_results, 'ver1_VS_ver2')
        orig_version = os.path.join(version_folder, 'ver1')
        os.makedirs(orig_version, exist_ok=True)
        
        # Create a test image
        test_image = os.path.join(orig_version, '0001.jpg')
        with open(test_image, 'w') as f:
            f.write('mock image')
        
        prepare_ui = PrepareUIData()
        status, thumbnail = prepare_ui._determine_status(
            self.frame_folder,
            self.test_sets_results_dir
        )
        
        self.assertEqual(status, STATUS_RENDERED)
        self.assertNotEqual(thumbnail, '')

    def test_find_xml_files(self):
        """Test _find_xml_files."""
        # Create results structure with compareResult.xml
        frame_results = self.frame_folder.replace('testSets', 'testSets_results')
        version_folder = os.path.join(frame_results, 'ver1_VS_ver2')
        results_folder = os.path.join(version_folder, 'results')
        os.makedirs(results_folder, exist_ok=True)
        
        # Create compareResult.xml
        xml_file = os.path.join(results_folder, 'compareResult.xml')
        doc = minidom.Document()
        root = doc.createElement('root')
        doc.appendChild(root)
        with open(xml_file, 'w') as f:
            f.write(doc.toprettyxml())
        
        prepare_ui = PrepareUIData()
        xml_files = prepare_ui._find_xml_files(self.test_sets_results_dir)
        
        self.assertEqual(len(xml_files), 1)
        self.assertIn('compareResult.xml', xml_files[0])

    def test_parse_xml_file(self):
        """Test _parse_xml_file."""
        # Create a test compareResult.xml
        xml_file = os.path.join(self.temp_dir, 'compareResult.xml')
        doc = minidom.Document()
        root = doc.createElement('root')
        doc.appendChild(root)
        
        # Add required elements
        for tag, value in [
            ('eventName', 'TestEvent'),
            ('sportType', 'NFL'),
            ('startFrame', '1'),
            ('endFrame', '10'),
            ('minVal', '0.95'),
            ('sourcePath', '/test/path')
        ]:
            elem = doc.createElement(tag)
            elem.appendChild(doc.createTextNode(value))
            root.appendChild(elem)
        
        # Add frames
        frames = doc.createElement('frames')
        root.appendChild(frames)
        for i in range(1, 11):
            frame = doc.createElement('frame')
            frame_index = doc.createElement('frameIndex')
            frame_index.appendChild(doc.createTextNode(str(i)))
            value = doc.createElement('value')
            value.appendChild(doc.createTextNode('0.98'))
            frame.appendChild(frame_index)
            frame.appendChild(value)
            frames.appendChild(frame)
        
        with open(xml_file, 'w') as f:
            f.write(doc.toprettyxml())
        
        prepare_ui = PrepareUIData()
        data = prepare_ui._parse_xml_file(xml_file)
        
        self.assertIsNotNone(data)
        self.assertEqual(data['eventName'], 'TestEvent')
        self.assertEqual(data['sportType'], 'NFL')
        self.assertEqual(data['numberOfFrames'], 10)
        self.assertEqual(data['minValue'], 0.95)

    def test_parse_xml_file_invalid(self):
        """Test _parse_xml_file with invalid XML."""
        # Create invalid XML file
        xml_file = os.path.join(self.temp_dir, 'invalid.xml')
        with open(xml_file, 'w') as f:
            f.write('invalid xml content')
        
        prepare_ui = PrepareUIData()
        data = prepare_ui._parse_xml_file(xml_file)
        
        self.assertIsNone(data)

    def test_get_thumbnail_path(self):
        """Test _get_thumbnail_path."""
        # Create test image folder
        image_folder = os.path.join(self.temp_dir, 'images')
        os.makedirs(image_folder, exist_ok=True)
        
        # Create test images
        for i in range(1, 4):
            image_file = os.path.join(image_folder, f'{i:04d}.jpg')
            with open(image_file, 'w') as f:
                f.write('mock image')
        
        prepare_ui = PrepareUIData()
        thumbnail = prepare_ui._get_thumbnail_path(image_folder, self.test_sets_results_dir)
        
        self.assertNotEqual(thumbnail, '')
        self.assertIn('.jpg', thumbnail)

    def test_get_thumbnail_path_no_images(self):
        """Test _get_thumbnail_path when no images exist."""
        # Create empty folder
        empty_folder = os.path.join(self.temp_dir, 'empty')
        os.makedirs(empty_folder, exist_ok=True)
        
        prepare_ui = PrepareUIData()
        thumbnail = prepare_ui._get_thumbnail_path(empty_folder, self.test_sets_results_dir)
        
        self.assertEqual(thumbnail, '')

    def test_extract_render_version_from_path(self):
        """Test _extract_render_version_from_path."""
        prepare_ui = PrepareUIData()
        
        # Test path with _VS_
        path = '/test/path/freedview_1.2.3_VS_freedview_1.3.4/images'
        version = prepare_ui._extract_render_version_from_path(path)
        
        self.assertIsNotNone(version)
        self.assertIn('_VS_', version)

    def test_extract_render_version_from_path_no_version(self):
        """Test _extract_render_version_from_path when no version found."""
        prepare_ui = PrepareUIData()
        
        # Test path without _VS_
        path = '/test/path/regular_folder/images'
        version = prepare_ui._extract_render_version_from_path(path)
        
        self.assertIsNone(version)

    def test_get_test_sets_results_root_from_path(self):
        """Test _get_test_sets_results_root_from_path."""
        prepare_ui = PrepareUIData()
        
        # Test path with testSets_results
        path = '/base/testSets_results/Event/Set/F0001/results/compareResult.xml'
        root = prepare_ui._get_test_sets_results_root_from_path(path)
        
        self.assertIsNotNone(root)
        self.assertIn('testSets_results', root)

    def test_make_path_relative(self):
        """Test _make_path_relative."""
        prepare_ui = PrepareUIData()
        
        base_path = '/base/testSets_results'
        absolute_path = '/base/testSets_results/Event/Set/F0001/image.jpg'
        relative = prepare_ui._make_path_relative(absolute_path, base_path)
        
        self.assertIsNotNone(relative)
        self.assertNotEqual(relative, absolute_path)
        self.assertIn('Event', relative)

    def test_preserve_user_editable_fields(self):
        """Test _preserve_user_editable_fields."""
        # Create existing uiData.xml
        xml_file = os.path.join(self.temp_dir, 'uiData.xml')
        doc = minidom.Document()
        root = doc.createElement('uiData')
        doc.appendChild(root)
        
        entries = doc.createElement('entries')
        root.appendChild(entries)
        
        entry = doc.createElement('entry')
        entries.appendChild(entry)
        
        # Add fields
        for tag, value in [
            ('thumbnailPath', 'Event/Set/F0001/image.jpg'),
            ('eventName', 'TestEvent'),
            ('sportType', 'NFL'),
            ('notes', 'Test notes')
        ]:
            elem = doc.createElement(tag)
            elem.appendChild(doc.createTextNode(value))
            entry.appendChild(elem)
        
        with open(xml_file, 'w') as f:
            f.write(doc.toprettyxml())
        
        prepare_ui = PrepareUIData()
        preserved = prepare_ui._preserve_user_editable_fields(xml_file)
        
        self.assertGreater(len(preserved), 0)
        key = 'Event/Set/F0001/image.jpg'
        self.assertIn(key, preserved)
        self.assertEqual(preserved[key]['eventName'], 'TestEvent')
        self.assertEqual(preserved[key]['notes'], 'Test notes')

    def test_preserve_user_editable_fields_no_file(self):
        """Test _preserve_user_editable_fields when file doesn't exist."""
        prepare_ui = PrepareUIData()
        preserved = prepare_ui._preserve_user_editable_fields('/nonexistent/file.xml')
        
        self.assertEqual(len(preserved), 0)


if __name__ == '__main__':
    unittest.main()
