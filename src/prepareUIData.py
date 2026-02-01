"""
Phase 4: Prepare UI Data with Status Tracking

This module scans testSets folder structure and compares with testSets_results to
create/update an aggregated XML file (uiData.xml) containing data for UI display,
including status tracking for each test (Ready, Rendered, Not Ready).
"""
import os
import logging
import xml.dom.minidom as minidom
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
import getDataIni as data_ini
import jsonLocalizer as json_localizer

# Configure module-level logger
logger = logging.getLogger(__name__)

# Constants
TEST_SETS_DIR = "testSets"
TEST_SETS_RESULTS_DIR = "testSets_results"
COMPARE_RESULT_XML = "compareResult.xml"
RESULTS_FOLDER = "results"
UI_DATA_XML = "uiData.xml"
SUPPORTED_IMAGE_EXTENSIONS = ['.jpg', '.png', '.jpeg']

# Status values
STATUS_READY = "Ready"                    # Phase 3 complete (compareResult.xml exists)
STATUS_RENDERED = "Rendered not compare"  # Phase 2 complete, but no comparison
STATUS_NOT_READY = "Not Ready"            # No results found


class PrepareUIData:
    """Handles aggregation of comparison results for UI display."""

    def __init__(self):
        """Initialize PrepareUIData."""
        logger.info("-- PrepareUIData --")

    def do_it(self, ini_path: Optional[str] = None) -> None:
        """
        Main entry point for UI data preparation with status tracking.

        Scans testSets folder structure, compares with testSets_results to determine
        status, and creates/updates uiData.xml with complete information including status.

        Args:
            ini_path: Path to the INI configuration file (optional, for getting base path)
        """
        logger.info("-- PrepareUIData --")

        # Get paths from INI
        test_sets_path = None
        test_sets_results_path = None
        event_name_pattern = None
        set_name_pattern = None
        # Phase 4 always processes all tests - ignore testFilter
        # testFilter is used in Phase 1 (Localize), Phase 2 (Render), and Phase 3 (Compare) for targeted processing
        # Phase 4 (Prepare UI Data) always processes all tests to maintain complete uiData.xml
        test_filter_set = set()
        
        if ini_path:
            set_test_path_tag = 'setTestPath'
            event_name_tag = 'eventName'
            set_name_tag = 'setName'
            # Note: run_on_test_list is intentionally NOT read here
            # Phase 4 always processes ALL tests to maintain complete uiData.xml file
            
            set_test_path = data_ini.getDataINI(ini_path, set_test_path_tag)[0]
            event_name_pattern = data_ini.getDataINI(ini_path, event_name_tag)[0]
            set_name_pattern = data_ini.getDataINI(ini_path, set_name_tag)[0]
            
            # Phase 4 always processes all tests - ignore run_on_test_list (already initialized above)
            logger.debug("Phase 4: Ignoring run_on_test_list - processing all tests to maintain complete uiData.xml")
            
            if set_test_path != data_ini.ERROR_VALUE:
                test_sets_path = set_test_path
                test_sets_results_path = set_test_path.replace(TEST_SETS_DIR, TEST_SETS_RESULTS_DIR)
        
        # Fallback: try to find in current directory
        if not test_sets_path or not os.path.exists(test_sets_path):
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            test_sets_path = os.path.join(current_dir, TEST_SETS_DIR)
            test_sets_results_path = os.path.join(current_dir, TEST_SETS_RESULTS_DIR)
        
        if not os.path.exists(test_sets_path):
            logger.error(f"testSets directory not found. Searched: {test_sets_path}")
            return
        
        if not os.path.exists(test_sets_results_path):
            logger.warning(f"testSets_results directory not found. Will create uiData.xml with all tests as 'Not Ready'. Searched: {test_sets_results_path}")
            # Continue - we can still bootstrap uiData.xml

        logger.info(f"Scanning testSets folder structure: {test_sets_path}")
        logger.info(f"Comparing with testSets_results: {test_sets_results_path if test_sets_results_path and os.path.exists(test_sets_results_path) else 'N/A'}")

        # Step 1: Scan testSets to discover all potential tests
        # Phase 4 always processes all tests (run_on_test_list is ignored) to maintain complete uiData.xml
        all_tests = self._scan_test_sets(test_sets_path, event_name_pattern, set_name_pattern, test_filter_set)
        logger.info(f"Found {len(all_tests)} test(s) in testSets folder structure (Phase 4 processes all tests)")

        # Step 2: Scan testSets_results for completed comparisons and collect render version names
        completed_comparisons = {}
        render_version_names = set()  # Use set to ensure uniqueness
        if test_sets_results_path and os.path.exists(test_sets_results_path):
            xml_files = self._find_xml_files(test_sets_results_path)
            logger.info(f"Found {len(xml_files)} compareResult.xml file(s) in testSets_results")
            
            # Collect render version folder names during recursive scan
            render_version_names = self._collect_render_version_names(test_sets_results_path)
            logger.info(f"Found {len(render_version_names)} unique render version folder(s)")
            
            for xml_file_path in xml_files:
                try:
                    data = self._parse_xml_file(xml_file_path)
                    if data:
                        # Use XML file path to derive frame folder path for matching
                        # XML is at: .../F####/freedview_X_VS_Y/results/compareResult.xml
                        # Extract frame folder path (up to F####, NOT including version folder)
                        try:
                            xml_path_obj = Path(xml_file_path)
                            # Go up from results/compareResult.xml to version folder, then to frame folder
                            # XML is at: .../F####/freedview_X_VS_Y/results/compareResult.xml
                            # parent = .../F####/freedview_X_VS_Y/results
                            # parent.parent = .../F####/freedview_X_VS_Y (version folder)
                            # parent.parent.parent = .../F#### (frame folder - this is what we want)
                            frame_folder_path = xml_path_obj.parent.parent.parent  # This is the frame folder (F####)
                            # Get relative path from testSets_results root to frame folder only
                            if test_sets_results_path:
                                test_sets_results_root = self._get_test_sets_results_root_from_path(str(xml_file_path))
                                if not test_sets_results_root:
                                    test_sets_results_root = test_sets_results_path
                                # Get relative path to frame folder (not including version folder)
                                match_key = self._make_path_relative(str(frame_folder_path), test_sets_results_root)
                                # Normalize to forward slashes for consistent matching
                                match_key = match_key.replace('\\', '/')
                                completed_comparisons[match_key] = data
                                logger.debug(f"Stored completed comparison with match_key: {match_key}")
                        except Exception as e:
                            logger.debug(f"Failed to extract match key from XML path {xml_file_path}: {e}")
                            # Fallback: use XML file path as key
                            completed_comparisons[xml_file_path] = data
                except Exception as e:
                    logger.warning(f"Failed to parse XML file '{xml_file_path}': {e}")
                    continue

        # Step 3: Merge data and determine status
        ui_data_list = self._merge_and_determine_status(all_tests, completed_comparisons, test_sets_results_path)

        if not ui_data_list:
            logger.warning("No test data to process")
            return

        # Sort by thumbnailPath to ensure consistent ordering (testKey is derived from thumbnailPath)
        ui_data_list.sort(key=lambda x: x.get('thumbnailPath', ''))

        # Step 4: Preserve user-editable fields from existing uiData.xml (if it exists)
        output_xml_path = os.path.join(test_sets_results_path if test_sets_results_path and os.path.exists(test_sets_results_path) else test_sets_path.replace(TEST_SETS_DIR, TEST_SETS_RESULTS_DIR), UI_DATA_XML)
        output_xml_path = output_xml_path.replace('\\', '/')
        output_dir = os.path.dirname(output_xml_path)
        os.makedirs(output_dir, exist_ok=True)
        preserved_fields = self._preserve_user_editable_fields(output_xml_path)
        
        # Step 5: Create/update aggregated XML file (will merge preserved fields and render versions)
        self._create_aggregated_xml(ui_data_list, output_xml_path, preserved_fields, render_version_names)

        logger.info(f"UI data XML created/updated: {output_xml_path}")
        logger.info(f"Total entries: {len(ui_data_list)}")
        
        # Count by status
        status_counts = {}
        for entry in ui_data_list:
            status = entry.get('status', STATUS_NOT_READY)
            status_counts[status] = status_counts.get(status, 0) + 1
        
        logger.info(f"Status breakdown: {status_counts}")
        logger.info("========================= Done PrepareUIData ============================")

    def _scan_test_sets(self, test_sets_path: str, event_name_pattern: Optional[str], set_name_pattern: Optional[str], test_filter_set: set = None) -> List[Dict]:
        """
        Scan testSets folder structure to discover all potential tests.
        Recursively finds all frame folders (F####) regardless of whether JSON files exist.
        
        Args:
            test_sets_path: Path to testSets directory
            event_name_pattern: Pattern for event names (optional, for filtering)
            set_name_pattern: Pattern for set names (optional, for filtering)
            test_filter_set: Optional set of testKeys to filter by (if empty/None, process all)
            
        Returns:
            List of dictionaries containing test information extracted from folder structure
        """
        if test_filter_set is None:
            test_filter_set = set()
        all_tests = []
        test_sets_path_obj = Path(test_sets_path)
        
        if not test_sets_path_obj.exists():
            logger.warning(f"testSets path does not exist: {test_sets_path}")
            return all_tests
        
        try:
            # Recursively scan for all frame folders (F#### pattern)
            # Frame folders are identified by names starting with 'F' followed by digits
            for frame_folder in test_sets_path_obj.rglob('F*'):
                if not frame_folder.is_dir():
                    continue
                
                # Validate frame folder name pattern (F followed by digits)
                frame_name = frame_folder.name
                if len(frame_name) > 1 and frame_name[0].upper() == 'F':
                    try:
                        # Try to parse the number part to validate it's a valid frame folder
                        int(frame_name[1:])
                        
                        # Extract metadata from this frame folder path
                        metadata = self._extract_metadata_from_test_sets_path(str(frame_folder), test_sets_path)
                        if metadata:
                            # Apply run_on_test_list if specified
                            # Derive testKey from frame folder path for filtering
                            frame_folder_path = metadata.get('frameFolderPath', '')
                            test_key = None
                            if frame_folder_path and test_sets_path:
                                try:
                                    frame_path_obj = Path(frame_folder_path)
                                    test_key = str(frame_path_obj.relative_to(Path(test_sets_path))).replace('\\', '/')
                                except Exception:
                                    test_key = None
                            
                            if test_filter_set and (not test_key or test_key not in test_filter_set):
                                continue  # Skip this test if not in filter
                            all_tests.append(metadata)
                    except (ValueError, IndexError):
                        # Not a valid frame folder (F followed by non-digits), skip
                        continue
                        
        except Exception as e:
            logger.error(f"Error scanning testSets folder structure: {e}", exc_info=True)
        
        return all_tests

    def _extract_metadata_from_test_sets_path(self, frame_folder_path: str, test_sets_path: str) -> Optional[Dict]:
        """
        Extract metadata from testSets folder path structure.
        
        Args:
            frame_folder_path: Path to frame folder (e.g., testSets/SportType/Event/Set/F1234)
            test_sets_path: Base path to testSets directory
            
        Returns:
            Dictionary with metadata, or None on error
        """
        try:
            # Normalize paths
            frame_path_norm = os.path.normpath(frame_folder_path)
            test_sets_norm = os.path.normpath(test_sets_path)
            
            # Get relative path
            frame_path_obj = Path(frame_path_norm)
            test_sets_obj = Path(test_sets_norm)
            
            try:
                relative_path = frame_path_obj.relative_to(test_sets_obj)
            except ValueError:
                logger.debug(f"Could not get relative path for {frame_folder_path}")
                return None
            
            # Split path parts
            parts = relative_path.parts
            
            # Extract frame name (last part, e.g., "F1234")
            frame_name = parts[-1] if parts else ""
            
            # Extract metadata based on path structure
            # Structure can be: Event/Set/F, SportType/Event/Set/F, SportType/Stadium/Event/Set/F, SportType/Stadium/Category/Event/Set/F
            sport_type = ""
            stadium_name = ""
            category_name = ""
            event_name = ""
            set_name = ""  # Initialize set_name to avoid potential NameError
            
            if len(parts) >= 3:
                # At minimum: Event/Set/F
                set_name = parts[-2]
                event_part = parts[-3]
                
                # Determine structure based on number of parts
                if len(parts) == 3:
                    # Event/Set/F
                    event_name = event_part
                elif len(parts) == 4:
                    # SportType/Event/Set/F
                    sport_type = parts[0]
                    event_name = event_part
                elif len(parts) == 5:
                    # SportType/Stadium/Event/Set/F
                    sport_type = parts[0]
                    stadium_name = parts[1]
                    event_name = event_part
                elif len(parts) >= 6:
                    # SportType/Stadium/Category/Event/Set/F
                    sport_type = parts[0]
                    stadium_name = parts[1]
                    category_name = parts[2]
                    event_name = event_part
            
            return {
                'eventName': event_name,
                'setName': set_name if len(parts) >= 3 else '',
                'sportType': sport_type,
                'stadiumName': stadium_name,
                'categoryName': category_name,
                'frameFolderPath': frame_folder_path
            }
            
        except Exception as e:
            logger.debug(f"Error extracting metadata from path {frame_folder_path}: {e}")
            return None


    def _determine_status(self, frame_folder_path: str, test_sets_results_path: str) -> Tuple[str, str]:
        """
        Determine status of a test by checking testSets_results and get thumbnail path if available.
        
        Args:
            frame_folder_path: Path to frame folder in testSets
            test_sets_results_path: Path to testSets_results directory
            
        Returns:
            Tuple of (status string, thumbnail_path): 
            - Status: "Ready", "Rendered not compare", or "Not Ready"
            - Thumbnail path: Path to first image if renders exist, empty string otherwise
        """
        try:
            # Convert testSets path to testSets_results path
            frame_path_results = frame_folder_path.replace(TEST_SETS_DIR, TEST_SETS_RESULTS_DIR)
            
            frame_path_obj = Path(frame_path_results)
            # Don't return early if folder doesn't exist - we still want to set thumbnailPath
            # for "Not Ready" status so the tool knows which test to render
            
            # Find testSets_results root for relative path conversion
            # First try to extract from frame_path_results, then fallback to test_sets_results_path parameter
            test_sets_results_root = self._get_test_sets_results_root_from_path(str(frame_path_results))
            if not test_sets_results_root and test_sets_results_path:
                # Fallback: use the test_sets_results_path directly if it's the root, or extract root from it
                if os.path.exists(test_sets_results_path):
                    # Check if test_sets_results_path itself is the root (ends with testSets_results)
                    if os.path.basename(test_sets_results_path) == TEST_SETS_RESULTS_DIR:
                        test_sets_results_root = test_sets_results_path
                    else:
                        # Try to extract root from the path
                        test_sets_results_root = self._get_test_sets_results_root_from_path(test_sets_results_path)
            logger.debug(f"_determine_status: frame_path_results={frame_path_results}, test_sets_results_root={test_sets_results_root}")
            
            # First, check for compareResult.xml (Phase 3 complete)
            # Look for any version comparison folder with results/compareResult.xml
            # Only check if the frame folder exists
            first_render_folder = None
            if frame_path_obj.exists():
                for item in frame_path_obj.iterdir():
                    if item.is_dir():
                        results_folder = item / RESULTS_FOLDER
                        xml_file = results_folder / COMPARE_RESULT_XML
                        if xml_file.exists():
                            return (STATUS_READY, '')
                
                # If no compareResult.xml found, check if render version folders exist with images (Phase 2 complete)
                # Look for version folders (e.g., freedview_1.2.1.3_1.0.0.7) that contain at least one JPG file
                for item in frame_path_obj.iterdir():
                    if item.is_dir():
                        # Skip the 'results' folder if it exists (it's empty or incomplete)
                        if item.name == RESULTS_FOLDER:
                            continue
                        
                        # Check if this version folder contains image files (recursively)
                        # Look for JPG/PNG files in the folder or its subdirectories
                        image_files = []
                        for ext in SUPPORTED_IMAGE_EXTENSIONS:
                            # Check directly in the folder
                            image_files.extend(item.glob(f'*{ext}'))
                            image_files.extend(item.glob(f'*{ext.upper()}'))
                            # Also check recursively in subdirectories (in case images are in subfolders)
                            image_files.extend(item.rglob(f'*{ext}'))
                            image_files.extend(item.rglob(f'*{ext.upper()}'))
                        
                        # If we found at least one image file, this version has been rendered
                        if image_files:
                            if first_render_folder is None:
                                first_render_folder = item
                            logger.debug(f"Found rendered images in version folder: {item.name} ({len(image_files)} images)")
            
            if first_render_folder:
                # Get thumbnail path from the first render folder
                thumbnail_path = self._get_thumbnail_path(str(first_render_folder), test_sets_results_root)
                logger.debug(f"Found first render folder: {first_render_folder}, thumbnail_path: {thumbnail_path}, root: {test_sets_results_root}")
                return (STATUS_RENDERED, thumbnail_path)
            
            # No renders found - return frame folder path from testSets (relative to testSets_results root)
            # This allows deriving testKey from thumbnailPath even when there are no renders
            # Even if the folder doesn't exist in testSets_results, we still want to set the path
            # so the tool knows which test to render
            if test_sets_results_root and frame_folder_path:
                # Convert testSets path to testSets_results path for relative path calculation
                frame_path_results = frame_folder_path.replace(TEST_SETS_DIR, TEST_SETS_RESULTS_DIR)
                # Ensure frame_path_results is an absolute path
                if not os.path.isabs(frame_path_results):
                    # If it's relative, make it absolute relative to test_sets_results_root
                    frame_path_results = os.path.join(test_sets_results_root, frame_path_results)
                # Get relative path from testSets_results root to frame folder
                # Don't check if it exists - we want the path even if the folder doesn't exist yet
                # Use _make_path_relative which handles non-existent paths
                relative_frame_path = self._make_path_relative(frame_path_results, test_sets_results_root)
                if relative_frame_path and relative_frame_path != frame_path_results:  # Only if conversion succeeded
                    logger.debug(f"No renders found, using frame folder path (may not exist): {relative_frame_path}")
                    return (STATUS_NOT_READY, relative_frame_path)
            
            return (STATUS_NOT_READY, '')
            
        except Exception as e:
            logger.debug(f"Error determining status for {frame_folder_path}: {e}")
            return (STATUS_NOT_READY, '')

    def _extract_render_version_from_path(self, path: str) -> Optional[str]:
        """
        Extract render version folder name from a path.
        Render version folders contain "_VS_" in their name.
        
        Args:
            path: Path string (can be relative or absolute, can be a file or folder path)
            
        Returns:
            Render version folder name if found, None otherwise
        """
        if not path:
            return None
        
        try:
            # Normalize path separators
            path_normalized = path.replace('\\', '/')
            # Split path into parts
            parts = path_normalized.split('/')
            
            # Look for a part that contains "_VS_"
            for part in parts:
                if "_VS_" in part:
                    return part
            
            return None
        except Exception as e:
            logger.debug(f"Error extracting render version from path {path}: {e}")
            return None
    
    def _get_render_versions_for_test(self, frame_folder_path: str, test_sets_results_path: Optional[str]) -> List[str]:
        """
        Get all render version folder names associated with a test by checking the frame folder.
        
        Args:
            frame_folder_path: Path to frame folder in testSets
            test_sets_results_path: Path to testSets_results directory
            
        Returns:
            List of render version folder names (containing "_VS_")
        """
        render_versions = []
        
        if not frame_folder_path or not test_sets_results_path:
            return render_versions
        
        try:
            # Convert testSets path to testSets_results path
            frame_path_results = frame_folder_path.replace(TEST_SETS_DIR, TEST_SETS_RESULTS_DIR)
            frame_path_obj = Path(frame_path_results)
            
            if not frame_path_obj.exists():
                return render_versions
            
            # Check all subdirectories in the frame folder
            for item in frame_path_obj.iterdir():
                if item.is_dir():
                    folder_name = item.name
                    # Check if folder name contains "_VS_" (render version folder)
                    if "_VS_" in folder_name:
                        render_versions.append(folder_name)
                        logger.debug(f"Found render version folder for test: {folder_name}")
        
        except Exception as e:
            logger.debug(f"Error getting render versions for test {frame_folder_path}: {e}")
        
        return render_versions

    def _merge_and_determine_status(self, all_tests: List[Dict], completed_comparisons: Dict[str, Dict], test_sets_results_path: Optional[str]) -> List[Dict]:
        """
        Merge testSets scan with testSets_results scan and determine status for each test.
        
        Args:
            all_tests: List of tests discovered from testSets folder structure
            completed_comparisons: Dictionary of completed comparisons (keyed by test key)
            test_sets_results_path: Path to testSets_results directory
            
        Returns:
            List of merged test data with status information
        """
        merged_data = []
        completed_keys = set(completed_comparisons.keys())
        
        logger.debug(f"Merging {len(all_tests)} tests from testSets with {len(completed_comparisons)} completed comparisons")
        
        for test in all_tests:
            frame_folder_path = test.get('frameFolderPath', '')
            
            # Generate match key from frame folder path for matching with completed comparisons
            # Convert frame folder path to testSets_results equivalent for matching
            match_key = None
            if frame_folder_path and test_sets_results_path:
                frame_path_results = frame_folder_path.replace(TEST_SETS_DIR, TEST_SETS_RESULTS_DIR)
                try:
                    frame_path_obj = Path(frame_path_results)
                    if frame_path_obj.exists():
                        test_sets_results_root = self._get_test_sets_results_root_from_path(str(frame_path_results))
                        if not test_sets_results_root:
                            test_sets_results_root = test_sets_results_path
                        match_key = self._make_path_relative(str(frame_path_obj), test_sets_results_root)
                        # Normalize to forward slashes for consistent matching
                        match_key = match_key.replace('\\', '/')
                    else:
                        # Frame folder doesn't exist in results yet, use path structure
                        match_key = str(Path(frame_path_results).relative_to(Path(test_sets_results_path))).replace('\\', '/')
                    logger.debug(f"Generated match_key for test {frame_folder_path}: {match_key}")
                    logger.debug(f"Available keys in completed_comparisons: {list(completed_comparisons.keys())}")
                except Exception:
                    match_key = None
            
            # Check if this test has completed comparison data
            if match_key and match_key in completed_comparisons:
                # Use completed comparison data and set status to Ready
                comparison_data = completed_comparisons[match_key].copy()
                comparison_data['status'] = STATUS_READY
                # Ensure thumbnailPath is set (it should come from _parse_xml_file, but verify it's not empty)
                if not comparison_data.get('thumbnailPath'):
                    logger.warning(f"Test {frame_folder_path}: Completed comparison found but thumbnailPath is empty, attempting to get from sourcePath")
                    # Try to get thumbnail from sourcePath if available
                    source_path = comparison_data.get('sourcePath', '')
                    if source_path and test_sets_results_path:
                        test_sets_results_root = self._get_test_sets_results_root_from_path(test_sets_results_path)
                        if not test_sets_results_root:
                            test_sets_results_root = test_sets_results_path
                        thumbnail_path = self._get_thumbnail_path(source_path, test_sets_results_root)
                        if thumbnail_path:
                            comparison_data['thumbnailPath'] = thumbnail_path
                        else:
                            # Fallback: try to get thumbnail from the frame folder in testSets_results
                            # The XML is at: .../F####/freedview_X_VS_Y/results/compareResult.xml
                            # Look for images in the version folders
                            if frame_folder_path and test_sets_results_path:
                                frame_path_results = frame_folder_path.replace(TEST_SETS_DIR, TEST_SETS_RESULTS_DIR)
                                frame_path_obj = Path(frame_path_results)
                                if frame_path_obj.exists():
                                    # Look for any version folder with images
                                    for item in frame_path_obj.iterdir():
                                        if item.is_dir() and item.name != RESULTS_FOLDER:
                                            # Check for images in this version folder
                                            thumbnail_path = self._get_thumbnail_path(str(item), test_sets_results_root)
                                            if thumbnail_path:
                                                comparison_data['thumbnailPath'] = thumbnail_path
                                                break
                
                # Extract render version from thumbnailPath or get from frame folder
                render_versions = []
                thumbnail_path = comparison_data.get('thumbnailPath', '')
                if thumbnail_path:
                    # Try to extract from thumbnailPath first
                    render_version = self._extract_render_version_from_path(thumbnail_path)
                    if render_version:
                        render_versions.append(render_version)
                
                # Also check frame folder for all render versions (in case there are multiple)
                if frame_folder_path and test_sets_results_path:
                    folder_render_versions = self._get_render_versions_for_test(frame_folder_path, test_sets_results_path)
                    # Merge with existing render_versions, avoiding duplicates
                    for rv in folder_render_versions:
                        if rv not in render_versions:
                            render_versions.append(rv)
                
                comparison_data['renderVersions'] = render_versions
                merged_data.append(comparison_data)
                logger.debug(f"Test {frame_folder_path}: Found completed comparison, status=Ready, thumbnailPath={comparison_data.get('thumbnailPath', '')}, renderVersions={render_versions}")
            else:
                # No completed comparison - determine status from folder structure
                status = STATUS_NOT_READY
                thumbnail_path = ''
                if test_sets_results_path and frame_folder_path:
                    status, thumbnail_path = self._determine_status(frame_folder_path, test_sets_results_path)
                
                # Extract render version from thumbnailPath or get from frame folder
                render_versions = []
                if thumbnail_path:
                    # Try to extract from thumbnailPath first
                    render_version = self._extract_render_version_from_path(thumbnail_path)
                    if render_version:
                        render_versions.append(render_version)
                
                # Also check frame folder for all render versions (in case there are multiple)
                if frame_folder_path and test_sets_results_path:
                    folder_render_versions = self._get_render_versions_for_test(frame_folder_path, test_sets_results_path)
                    # Merge with existing render_versions, avoiding duplicates
                    for rv in folder_render_versions:
                        if rv not in render_versions:
                            render_versions.append(rv)
                
                # Create entry with metadata from testSets scan
                entry = {
                    'eventName': test.get('eventName', ''),
                    'sportType': test.get('sportType', ''),
                    'stadiumName': test.get('stadiumName', ''),
                    'categoryName': test.get('categoryName', ''),
                    'numberOfFrames': 0,
                    'minValue': 0.0,
                    'numFramesUnderMin': 0,
                    'thumbnailPath': thumbnail_path,
                    'notes': '',
                    'status': status,
                    'renderVersions': render_versions
                }
                merged_data.append(entry)
                logger.debug(f"Test {frame_folder_path}: No completed comparison, status={status}, thumbnail={thumbnail_path}, renderVersions={render_versions}")
        
        logger.debug(f"Total merged entries: {len(merged_data)}")
        return merged_data

    def _find_xml_files(self, base_path: str) -> List[str]:
        """
        Recursively find all compareResult.xml files.

        Args:
            base_path: Base path to search in

        Returns:
            List of paths to compareResult.xml files
        """
        xml_files = []
        base_path_obj = Path(base_path)
        
        if not base_path_obj.exists():
            return xml_files

        # Search for compareResult.xml files in results folders
        for xml_file in base_path_obj.rglob(COMPARE_RESULT_XML):
            # Only include files that are in a results folder
            if RESULTS_FOLDER in xml_file.parts:
                xml_files.append(str(xml_file))

        return sorted(xml_files)

    def _collect_render_version_names(self, base_path: str) -> Set[str]:
        """
        Recursively find all render version folder names in testSets_results.
        Render version folders have names containing "_VS_" (e.g., "freedview_1.2.1.3_1.0.0.7_VS_freedView_1.3.0.0_1.0.0.1").

        Args:
            base_path: Base path to testSets_results directory

        Returns:
            Set of unique render version folder names
        """
        version_names = set()
        base_path_obj = Path(base_path)
        
        if not base_path_obj.exists():
            logger.debug(f"testSets_results path does not exist: {base_path}")
            return version_names

        try:
            # Recursively scan all directories in testSets_results
            # Use rglob with pattern to find all directories, then check their names
            for item in base_path_obj.rglob('*'):
                if item.is_dir():
                    folder_name = item.name
                    # Check if folder name contains "_VS_" (the separator between two version names)
                    if "_VS_" in folder_name:
                        version_names.add(folder_name)
                        logger.debug(f"Found render version folder: {folder_name} at {item}")
            
            # Also try a more explicit recursive directory walk as a fallback
            if not version_names:
                logger.debug("No versions found with rglob, trying explicit directory walk")
                def scan_directory(path: Path):
                    try:
                        for item in path.iterdir():
                            if item.is_dir():
                                folder_name = item.name
                                if "_VS_" in folder_name:
                                    version_names.add(folder_name)
                                    logger.debug(f"Found render version folder: {folder_name} at {item}")
                                # Recursively scan subdirectories
                                scan_directory(item)
                    except PermissionError:
                        logger.debug(f"Permission denied accessing: {path}")
                    except Exception as e:
                        logger.debug(f"Error scanning directory {path}: {e}")
                
                scan_directory(base_path_obj)
                
        except Exception as e:
            logger.warning(f"Error collecting render version names: {e}", exc_info=True)

        logger.info(f"Collected {len(version_names)} unique render version folder name(s): {sorted(version_names) if version_names else 'none'}")
        return version_names

    def _parse_xml_file(self, xml_file_path: str) -> Optional[Dict]:
        """
        Parse a compareResult.xml file and extract relevant data.

        Args:
            xml_file_path: Path to the compareResult.xml file

        Returns:
            Dictionary containing extracted data, or None on error
        """
        try:
            # Find testSets_results root for relative path handling
            test_sets_results_root = self._get_test_sets_results_root(xml_file_path)
            if not test_sets_results_root:
                # Fallback: try to extract from xml_file_path directly
                xml_path_obj = Path(xml_file_path)
                # Go up until we find testSets_results
                current = xml_path_obj.parent
                while current != current.parent:  # Stop at root
                    if current.name == TEST_SETS_RESULTS_DIR:
                        test_sets_results_root = str(current)
                        break
                    current = current.parent
            logger.debug(f"_parse_xml_file: xml_file_path={xml_file_path}, test_sets_results_root={test_sets_results_root}")
            
            dom = minidom.parse(xml_file_path)
            root = dom.documentElement

            # Helper function to get text content from element
            def get_text(tag_name: str, default: str = "") -> str:
                elements = root.getElementsByTagName(tag_name)
                if elements and elements[0].firstChild:
                    return elements[0].firstChild.nodeValue.strip()
                return default

            # Extract metadata
            event_name = get_text('eventName')
            sport_type = get_text('sportType')
            stadium_name = get_text('stadiumName')
            category_name = get_text('categoryName')
            start_frame_str = get_text('startFrame')
            end_frame_str = get_text('endFrame')
            min_val_str = get_text('minVal')
            source_path = get_text('sourcePath')

            # Convert string values to numbers
            try:
                start_frame = int(start_frame_str) if start_frame_str else 0
                end_frame = int(end_frame_str) if end_frame_str else 0
                min_val = float(min_val_str) if min_val_str else 0.0
            except (ValueError, TypeError):
                logger.warning(f"Failed to parse numeric values in {xml_file_path}")
                return None

            # Calculate number of frames
            num_frames = end_frame - start_frame + 1 if end_frame >= start_frame else 0

            # Extract frame values and count frames under minVal
            frame_values = []
            frames_element = root.getElementsByTagName('frames')
            if frames_element:
                frame_nodes = frames_element[0].getElementsByTagName('frame')
                for frame_node in frame_nodes:
                    value_elements = frame_node.getElementsByTagName('value')
                    if value_elements and value_elements[0].firstChild:
                        try:
                            value = float(value_elements[0].firstChild.nodeValue.strip())
                            frame_values.append(value)
                        except (ValueError, TypeError):
                            continue

            # Count frames under minVal
            num_frames_under_min = sum(1 for v in frame_values if v < min_val)

            # Get thumbnail path (first image from sourcePath folder)
            # Pass test_sets_results_root so thumbnail path is returned as relative
            logger.debug(f"_parse_xml_file: source_path={source_path}, test_sets_results_root={test_sets_results_root}")
            thumbnail_path = self._get_thumbnail_path(source_path, test_sets_results_root)
            logger.debug(f"_parse_xml_file: thumbnail_path={thumbnail_path}")

            # Extract render version from XML file path or sourcePath
            # XML is at: .../F####/freedview_X_VS_Y/results/compareResult.xml
            render_versions = []
            # Try to extract from XML file path first (most reliable)
            render_version = self._extract_render_version_from_path(xml_file_path)
            if render_version:
                render_versions.append(render_version)
            # Also try sourcePath as fallback
            if not render_versions and source_path:
                render_version = self._extract_render_version_from_path(source_path)
                if render_version and render_version not in render_versions:
                    render_versions.append(render_version)

            return {
                'id': 0,  # Will be set sequentially later
                'eventName': event_name,
                'sportType': sport_type,
                'stadiumName': stadium_name,
                'categoryName': category_name,
                'numberOfFrames': num_frames,
                'minValue': min_val,
                'numFramesUnderMin': num_frames_under_min,
                'thumbnailPath': thumbnail_path,
                'notes': '',
                'status': STATUS_READY,  # If we have XML, status is Ready
                'renderVersions': render_versions
            }

        except Exception as e:
            logger.error(f"Error parsing XML file '{xml_file_path}': {e}", exc_info=True)
            return None

    def _get_test_sets_results_root(self, xml_file_path: str) -> Optional[str]:
        """
        Extract testSets_results root directory from XML file path.

        Args:
            xml_file_path: Path to compareResult.xml file

        Returns:
            Path to testSets_results root, or None if not found
        """
        return self._get_test_sets_results_root_from_path(xml_file_path)
    
    def _get_test_sets_results_root_from_path(self, path: str) -> Optional[str]:
        """
        Extract testSets_results root directory from any path.

        Args:
            path: Any path within testSets_results structure

        Returns:
            Path to testSets_results root, or None if not found
        """
        path_normalized = os.path.normpath(path)
        parts = Path(path_normalized).parts
        
        # Find where testSets_results appears in the path
        try:
            index = parts.index(TEST_SETS_RESULTS_DIR)
            # Reconstruct path up to and including testSets_results
            root_path = os.path.join(*parts[:index + 1])
            return root_path
        except ValueError:
            # testSets_results not found in path
            return None

    def _make_path_relative(self, absolute_path: str, base_path: str) -> str:
        """
        Convert an absolute path to a relative path (relative to base_path).

        Args:
            absolute_path: Absolute path to convert
            base_path: Base path to make relative to (e.g., testSets_results root)

        Returns:
            Relative path string with Windows-style backslashes, or original path if conversion fails
        """
        try:
            abs_path_norm = os.path.normpath(absolute_path)
            base_path_norm = os.path.normpath(base_path)
            
            # Use pathlib for reliable relative path calculation
            abs_path_obj = Path(abs_path_norm)
            base_path_obj = Path(base_path_norm)
            
            try:
                relative_path = abs_path_obj.relative_to(base_path_obj)
                # Use Windows-style backslashes (native on Windows)
                # pathlib.Path uses backslashes on Windows by default
                return str(relative_path)
            except ValueError:
                # Paths don't share a common base, return original
                logger.debug(f"Could not make path relative: {absolute_path} (base: {base_path})")
                return absolute_path
        except Exception as e:
            logger.debug(f"Error converting path to relative: {e}")
            return absolute_path

    def _get_thumbnail_path(self, source_path: str, test_sets_results_root: Optional[str] = None) -> str:
        """
        Get the path to the first image file in the source path folder.
        Returns path relative to testSets_results root if root is provided.

        Args:
            source_path: Path to the source (original version) image folder (can be relative or absolute)
            test_sets_results_root: Optional testSets_results root path for relative path conversion

        Returns:
            Path to the first image file (relative if root provided), or empty string if not found
        """
        if not source_path:
            logger.debug("_get_thumbnail_path: source_path is empty")
            return ""
        
        # Resolve source_path to absolute path
        if os.path.isabs(source_path):
            # Already absolute
            source_path_abs = source_path
        elif test_sets_results_root:
            # Resolve relative to testSets_results root
            # Normalize path separators first
            source_path_normalized = source_path.replace('/', os.sep).replace('\\', os.sep)
            source_path_abs = os.path.join(test_sets_results_root, source_path_normalized)
            # Normalize the resulting path (resolve .. and .)
            source_path_abs = os.path.normpath(source_path_abs)
        else:
            # No root provided, try to use source_path as-is
            source_path_abs = os.path.normpath(source_path)
        
        if not os.path.exists(source_path_abs):
            logger.warning(f"_get_thumbnail_path: Path does not exist: {source_path_abs} (source_path={source_path}, root={test_sets_results_root})")
            return ""

        try:
            source_path_obj = Path(source_path_abs)
            # Find all image files (recursively, in case images are in subdirectories)
            image_files = []
            for ext in SUPPORTED_IMAGE_EXTENSIONS:
                # Check directly in the folder
                image_files.extend(source_path_obj.glob(f'*{ext}'))
                image_files.extend(source_path_obj.glob(f'*{ext.upper()}'))
                # Also check recursively in subdirectories
                image_files.extend(source_path_obj.rglob(f'*{ext}'))
                image_files.extend(source_path_obj.rglob(f'*{ext.upper()}'))

            if image_files:
                # Sort to ensure consistent ordering, get first image
                image_files.sort()
                thumbnail_abs_path = str(image_files[0].absolute())
                logger.debug(f"_get_thumbnail_path: Found {len(image_files)} images, using: {thumbnail_abs_path}")
                
                # Convert to relative if root is provided
                if test_sets_results_root:
                    relative_path = self._make_path_relative(thumbnail_abs_path, test_sets_results_root)
                    logger.debug(f"_get_thumbnail_path: Converted to relative: {relative_path}")
                    return relative_path
                else:
                    logger.debug(f"_get_thumbnail_path: No root provided, returning absolute: {thumbnail_abs_path}")
                    return thumbnail_abs_path
            else:
                logger.debug(f"_get_thumbnail_path: No image files found in: {source_path_abs}")

        except Exception as e:
            logger.debug(f"Error getting thumbnail from {source_path}: {e}", exc_info=True)

        return ""

    def _preserve_user_editable_fields(self, xml_path: str) -> Dict[str, Dict[str, str]]:
        """
        Read existing uiData.xml and extract user-editable fields (eventName, sportType, stadiumName, categoryName, notes) to preserve.
        
        Args:
            xml_path: Path to existing uiData.xml file
            
        Returns:
            Dictionary mapping test key (thumbnailPath) to dict of editable fields to preserve
        """
        preserved = {}
        
        if not os.path.exists(xml_path):
            logger.debug(f"No existing uiData.xml to preserve fields from: {xml_path}")
            return preserved
        
        try:
            dom = minidom.parse(xml_path)
            root = dom.documentElement
            entries = root.getElementsByTagName('entry')
            
            for entry in entries:
                # Extract fields that can be used for matching and preservation
                def get_field_text(tag_name: str) -> str:
                    elements = entry.getElementsByTagName(tag_name)
                    if elements and elements[0].firstChild:
                        return elements[0].firstChild.nodeValue.strip()
                    return ""
                
                thumbnail_path = get_field_text('thumbnailPath')
                
                # Use thumbnailPath as the key for matching (most reliable identifier)
                if thumbnail_path:
                    # Normalize path for matching (use forward slashes, remove trailing slashes)
                    key = thumbnail_path.replace('\\', '/').rstrip('/')
                    # Preserve ALL user-editable fields (exclude computed fields: status, numberOfFrames, minValue, numFramesUnderMin, id, thumbnailPath)
                    # Fields to preserve: eventName, sportType, stadiumName, categoryName, notes
                    preserved[key] = {
                        'eventName': get_field_text('eventName'),
                        'sportType': get_field_text('sportType'),
                        'stadiumName': get_field_text('stadiumName'),
                        'categoryName': get_field_text('categoryName'),
                        'notes': get_field_text('notes')
                    }
            
            logger.info(f"Preserved user-editable fields from {len(preserved)} entries in existing uiData.xml")
            if preserved:
                logger.debug(f"Sample preserved keys: {list(preserved.keys())[:3]}")
        except Exception as e:
            logger.warning(f"Failed to preserve user-editable fields from existing uiData.xml: {e}")
            # Continue - if we can't preserve, just regenerate without preserving
        
        return preserved
    
    def _create_aggregated_xml(self, data_list: List[Dict], output_path: str, preserved_fields: Optional[Dict[str, Dict[str, str]]] = None, render_version_names: Optional[Set[str]] = None) -> None:
        """
        Create aggregated XML file with all UI data.

        Args:
            data_list: List of dictionaries containing UI data
            output_path: Path where the XML file should be saved
            preserved_fields: Optional dictionary mapping thumbnailPath to dict of fields to preserve (notes, categoryName)
            render_version_names: Optional set of unique render version folder names to include in XML
        """
        try:
            # Assign sequential IDs
            for idx, data in enumerate(data_list, start=1):
                data['id'] = idx

            # Create XML document
            doc = minidom.Document()
            root = doc.createElement('uiData')
            doc.appendChild(root)

            # Add render versions section (if any were found)
            logger.debug(f"_create_aggregated_xml: render_version_names = {render_version_names}, type = {type(render_version_names)}, len = {len(render_version_names) if render_version_names else 0}")
            if render_version_names and len(render_version_names) > 0:
                logger.info(f"Adding {len(render_version_names)} render version(s) to XML")
                render_versions = doc.createElement('renderVersions')
                root.appendChild(render_versions)
                # Sort version names for consistent ordering
                for version_name in sorted(render_version_names):
                    version_elem = doc.createElement('version')
                    version_elem.appendChild(doc.createTextNode(version_name))
                    render_versions.appendChild(version_elem)
                logger.info(f"Successfully added {len(render_version_names)} render version(s) to XML")
            else:
                logger.info(f"No render versions to add to XML (render_version_names is empty or None)")

            # Add entries
            entries = doc.createElement('entries')
            root.appendChild(entries)

            for data in data_list:
                entry = doc.createElement('entry')
                entries.appendChild(entry)

                # Merge preserved user-editable fields if available
                thumbnail_path = data.get('thumbnailPath', '')
                if preserved_fields and thumbnail_path:
                    # Normalize path for matching (use forward slashes, remove trailing slashes)
                    key = thumbnail_path.replace('\\', '/').rstrip('/')
                    # Try exact match first
                    preserved = None
                    if key in preserved_fields:
                        preserved = preserved_fields[key]
                    else:
                        # Try fuzzy match (case-insensitive or partial)
                        for preserved_key in preserved_fields.keys():
                            if key.lower() == preserved_key.lower() or key in preserved_key or preserved_key in key:
                                preserved = preserved_fields[preserved_key]
                                break
                    
                    if preserved:
                        # Override with preserved values (preserve all user-editable fields, including empty values)
                        # This ensures user edits are preserved even if the user cleared a field
                        if 'eventName' in preserved:
                            data['eventName'] = preserved['eventName']
                        if 'sportType' in preserved:
                            data['sportType'] = preserved['sportType']
                        if 'stadiumName' in preserved:
                            data['stadiumName'] = preserved['stadiumName']
                        if 'categoryName' in preserved:
                            data['categoryName'] = preserved['categoryName']
                        if 'notes' in preserved:
                            data['notes'] = preserved['notes']

                # Add all fields including status
                # Format values for consistent display and sorting
                id_value = data.get('id', 0)
                min_value = data.get('minValue', 0.0)
                
                # Get renderVersions list and convert to comma-separated string
                render_versions_list = data.get('renderVersions', [])
                render_versions_str = ','.join(render_versions_list) if render_versions_list else ''
                
                fields = [
                    ('id', str(id_value).zfill(3)),  # Pad ID to 3 digits (e.g., 1 -> 001, 10 -> 010)
                    ('eventName', data.get('eventName', '')),
                    ('sportType', data.get('sportType', '')),
                    ('stadiumName', data.get('stadiumName', '')),
                    ('categoryName', data.get('categoryName', '')),
                    ('numberOfFrames', str(data.get('numberOfFrames', 0)).zfill(4)),  # Pad to 4 digits (e.g., 62 -> 0062)
                    ('minValue', f"{min_value:.4f}"),  # Format to 4 decimal places (e.g., 0.7625)
                    ('numFramesUnderMin', str(data.get('numFramesUnderMin', 0))),
                    ('thumbnailPath', data.get('thumbnailPath', '')),
                    ('status', data.get('status', STATUS_NOT_READY)),
                    ('notes', data.get('notes', '')),
                    ('renderVersions', render_versions_str)  # Comma-separated list of render version folder names
                    # testKey is no longer stored - it will be derived from thumbnailPath when needed
                ]

                for field_name, field_value in fields:
                    field_elem = doc.createElement(field_name)
                    field_elem.appendChild(doc.createTextNode(field_value))
                    entry.appendChild(field_elem)

            # Write XML file
            output_path_obj = Path(output_path)
            output_path_obj.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                # Use toprettyxml for readable formatting, but remove extra blank lines
                xml_str = doc.toprettyxml(indent="  ")
                # Remove extra blank lines
                lines = [line for line in xml_str.split('\n') if line.strip()]
                f.write('\n'.join(lines))

            logger.info(f"Created aggregated XML file: {output_path}")

        except Exception as e:
            logger.error(f"Failed to create aggregated XML file: {e}", exc_info=True)
            raise


def run_prepare_ui_data() -> None:
    """Run PrepareUIData as standalone script."""
    project_path = os.path.dirname(__file__)
    ini_path = os.path.join(project_path, 'freeDView_tester.ini')
    prepare_ui_data = PrepareUIData()
    prepare_ui_data.do_it(ini_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Prepare UI Data")
    parser.add_argument(
        "-sa",
        action="store_true",
        dest="standalone",
        help="run script as stand alone"
    )

    args = parser.parse_args()
    if args.standalone:
        logger.info("Running PrepareUIData as stand alone process.")
        run_prepare_ui_data()

