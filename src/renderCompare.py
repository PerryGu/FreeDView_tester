"""
Phase 3: Render Compare

This module compares sequences of different rendered FreeDView versions and
creates new sequential alpha_images, diff_images, and compareResult.xml file.
"""
import os
import logging
import shutil
import time
import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional
from xml.dom import minidom
try:
    from skimage.metrics import structural_similarity as ssim
except ImportError:
    # Fallback for older versions of scikit-image
    from skimage.measure import structural_similarity as ssim
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import getDataIni as data_ini
import jsonLocalizer as json_localizer

# Constants
TEST_SETS_DIR = "testSets"
TEST_SETS_RESULTS_DIR = "testSets_results"
RESULTS_FOLDER = "results"
DIFF_IMAGES_FOLDER = "diff_images"
ALPHA_IMAGES_FOLDER = "alpha_images"
COMPARE_RESULT_XML = "compareResult.xml"
VERSION_SEPARATOR = "_VS_"

# Image processing constants
DILATION_KERNEL_SIZE = (5, 5)
DILATION_ITERATIONS = 1
SUPPORTED_IMAGE_EXTENSIONS = ['.jpg', '.png', '.jpeg']
DEFAULT_MAX_WORKERS = 4  # Default number of parallel comparison threads
DEFAULT_FRAME_WORKERS = 2  # Default number of parallel frame processing threads per folder

# Configure module-level logger
logger = logging.getLogger(__name__)


def mean_squared_error(image_a: np.ndarray, image_b: np.ndarray) -> float:
    """
    Calculate the Mean Squared Error between two images.

    Args:
        image_a: First image array
        image_b: Second image array

    Returns:
        MSE value - the lower the error, the more similar the images are

    Raises:
        ValueError: If images have different dimensions
    """
    if image_a.shape != image_b.shape:
        raise ValueError(
            f"Images must have the same dimensions. "
            f"Got {image_a.shape} and {image_b.shape}"
        )
    
    err = np.sum((image_a.astype("float") - image_b.astype("float")) ** 2)
    # Fix: Use total number of pixels (height * width)
    err /= float(image_a.shape[0] * image_a.shape[1])
    return err


class RenderCompare:
    """Handles comparison between rendered image sequences."""

    def __init__(self, ini_path: Optional[str] = None, max_workers: int = DEFAULT_MAX_WORKERS, 
                 frame_workers: int = DEFAULT_FRAME_WORKERS) -> None:
        """
        Initialize RenderCompare.

        Args:
            ini_path: Path to the INI configuration file
            max_workers: Maximum number of parallel comparison threads (default: 4)
            frame_workers: Maximum number of parallel frame processing threads per folder (default: 2)
        """
        self.max_workers = max_workers
        self.frame_workers = frame_workers
        self._progress_lock = Lock()
        self._processed_folders = 0
        self._total_folders = 0
        self._total_frames_all = 0  # Total frames across all folders
        self._completed_frames_all = 0  # Completed frames across all folders
        logger.info("-- RenderCompare --")
        if ini_path is not None:
            self._process_from_ini(ini_path)

    def _process_from_ini(self, ini_path: str) -> None:
        """
        Process comparison based on INI file configuration.

        Args:
            ini_path: Path to the INI configuration file
        """
        # Read configuration from INI file to get test paths and version info.
        set_test_path_tag = 'setTestPath'
        freedview_ver_tag = 'freedviewVer'
        event_name_tag = 'eventName'
        set_name_tag = 'setName'
        test_filter_tag = 'run_on_test_list'

        set_test_path = data_ini.getDataINI(ini_path, set_test_path_tag)[0]
        freedview_ver = data_ini.getDataINI(ini_path, freedview_ver_tag)[0]
        event_name_set_test = data_ini.getDataINI(ini_path, event_name_tag)[0]
        set_name_set_test = data_ini.getDataINI(ini_path, set_name_tag)[0]
        test_filter_raw = data_ini.getDataINI(ini_path, test_filter_tag)[0] if data_ini.getDataINI(ini_path, test_filter_tag)[0] != data_ini.ERROR_VALUE else ""

        # Parse run_on_test_list (comma-separated or newline-separated list of testKeys)
        # Handles empty filter as: "", "[]", or whitespace-only
        # Supports bracket format: [test1] or [test1, test2, test3]
        test_filter_set = set()
        if test_filter_raw and test_filter_raw.strip():
            test_filter_stripped = test_filter_raw.strip()
            # Handle empty array format: "[]"
            if test_filter_stripped == "[]" or test_filter_stripped == "":
                logger.debug("run_on_test_list is empty ([]) - processing all tests")
            else:
                # Strip brackets if present: [test1] -> test1, [test1, test2] -> test1, test2
                if test_filter_stripped.startswith('[') and test_filter_stripped.endswith(']'):
                    test_filter_stripped = test_filter_stripped[1:-1].strip()
                # Split by comma or newline, strip whitespace
                for key in test_filter_stripped.replace('\n', ',').split(','):
                    key = key.strip()
                    # Skip empty keys and "[]" entries
                    if key and key != "[]":
                        test_filter_set.add(key.replace('\\', '/'))
            if test_filter_set:
                logger.info(f"run_on_test_list active: {len(test_filter_set)} test(s) specified")
            else:
                logger.debug("run_on_test_list is empty - processing all tests")
        else:
            logger.debug("run_on_test_list is empty - processing all tests")

        # Validate INI data
        if set_test_path == data_ini.ERROR_VALUE:
            logger.error(f"Failed to read required configuration from INI file: {ini_path}")
            return

        # Convert testSets to testSets_results path
        test_sets_results_path = set_test_path.replace("testSets", TEST_SETS_RESULTS_DIR)
        
        # Check if freedviewVer is empty or not specified - if so, scan for all version comparisons
        # Handle cases where INI file has: freedviewVer = "" (returns '""') or freedviewVer = (empty)
        freedview_ver_stripped = freedview_ver.strip() if freedview_ver else ""
        # Remove surrounding quotes if present (e.g., '""' becomes '')
        if freedview_ver_stripped.startswith('"') and freedview_ver_stripped.endswith('"'):
            freedview_ver_stripped = freedview_ver_stripped[1:-1]
        if not freedview_ver or freedview_ver == data_ini.ERROR_VALUE or freedview_ver_stripped == "":
            logger.info("freedviewVer is empty - scanning for all version comparisons in testSets_results")
            comparison_tasks = self._scan_all_version_comparisons(test_sets_results_path, test_filter_set)
        else:
            # Parse version string to extract original and test version names.
            try:
                freedview_split = freedview_ver.split(VERSION_SEPARATOR)
                if len(freedview_split) != 2:
                    logger.error(
                        f"Invalid version format in INI file. "
                        f"Expected 'version1{VERSION_SEPARATOR}version2', got: {freedview_ver}"
                    )
                    return
                freedview_name_orig = freedview_split[0]
                freedview_name_tester = freedview_split[1]
            except Exception as e:
                logger.error(f"Error parsing version string '{freedview_ver}': {e}")
                return

            # Use JsonLocalizer to locate all frame folders that contain rendered images.
            json_localizer_obj = json_localizer.JsonLocalizer()
            create_folders = None
            get_json_info = json_localizer_obj.get_json_files(
                set_test_path, event_name_set_test, set_name_set_test, create_folders, test_filter_set
            )

            folder_frame_list = get_json_info[1]

            if not folder_frame_list:
                logger.warning("No frame folders found to process")
                return

            # Create list of comparison tasks
            comparison_tasks = []
            for folder_idx, folder_frame in enumerate(folder_frame_list):
                comparison_tasks.append({
                    'folder_idx': folder_idx,
                    'folder_frame': folder_frame,
                    'freedview_ver': freedview_ver,
                    'freedview_name_orig': freedview_name_orig,
                    'freedview_name_tester': freedview_name_tester,
                    'total_folders': len(folder_frame_list)
                })

        if not comparison_tasks:
            logger.warning("No comparison tasks found to process")
            return

        total_folders = len(comparison_tasks)
        self._total_folders = total_folders
        self._processed_folders = 0
        self._total_frames_all = 0
        self._completed_frames_all = 0
        
        # Pre-calculate total frames across all folders for overall progress tracking
        # Only count frames from folders that will actually be processed (same validation as _compare_single_folder)
        logger.info("Calculating total frames across all folders...")
        for task in comparison_tasks:
            try:
                folder_frame = task['folder_frame']
                if TEST_SETS_RESULTS_DIR not in folder_frame:
                    replace_path = folder_frame.replace("testSets", TEST_SETS_RESULTS_DIR)
                else:
                    replace_path = folder_frame
                
                freedview_ver_path = os.path.join(replace_path, task['freedview_ver'])
                # Check if path exists (same check as in _compare_single_folder)
                if os.path.exists(freedview_ver_path):
                    image_orig_list, image_tester_list, freedview_path_orig, freedview_path_tester = (
                        self._collect_image_paths(
                            freedview_ver_path, task['freedview_name_orig'], task['freedview_name_tester']
                        )
                    )
                    # Same validation as _compare_single_folder - only count if valid
                    if (len(image_orig_list) == len(image_tester_list) and 
                        len(image_orig_list) > 1 and 
                        freedview_path_orig and freedview_path_tester):
                        self._total_frames_all += len(image_orig_list)
                        logger.debug(
                            f"Will process {len(image_orig_list)} frames from {os.path.basename(folder_frame)}"
                        )
            except Exception as e:
                logger.debug(f"Error calculating frames for {task.get('folder_frame', 'unknown')}: {e}")
        
        logger.info(
            f"Processing {total_folders} comparison task(s) with {self.max_workers} parallel worker thread(s) "
            f"({self._total_frames_all} total frames that will be processed)"
        )

        # Execute comparisons in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._compare_single_folder, task): task
                for task in comparison_tasks
            }

            # Process completed tasks
            for future in as_completed(futures):
                task = futures[future]
                try:
                    success = future.result()
                    if success:
                        with self._progress_lock:
                            self._processed_folders += 1
                except Exception as e:
                    logger.error(
                        f"Unexpected error in comparison task for folder '{task['folder_frame']}': {e}",
                        exc_info=True
                    )
            # Executor will automatically shutdown when exiting the 'with' block
        
        logger.info(
            f"Completed parallel processing: {self._processed_folders}/{total_folders} "
            f"folders processed successfully"
        )
        
        # Explicitly flush all logging handlers to ensure output is written
        for handler in logging.root.handlers:
            handler.flush()

    def _scan_all_version_comparisons(self, test_sets_results_path: str, test_filter_set: set = None) -> List[dict]:
        """
        Scan testSets_results for all version comparison folders and create comparison tasks.

        Args:
            test_sets_results_path: Path to testSets_results directory
            test_filter_set: Optional set of testKeys to filter by (if empty/None, process all)

        Returns:
            List of comparison task dictionaries
        """
        if test_filter_set is None:
            test_filter_set = set()
        comparison_tasks = []
        test_sets_results_obj = Path(test_sets_results_path)
        
        if not test_sets_results_obj.exists():
            logger.warning(f"testSets_results path does not exist: {test_sets_results_path}")
            return comparison_tasks

        logger.info(f"Scanning for version comparison folders in: {test_sets_results_path}")
        
        # Find all folders matching the pattern "*_VS_*"
        # These folders are at: testSets_results/.../F####/freedview_X_Y_VS_freedview_A_B
        found_folders = []
        for item in test_sets_results_obj.rglob('*'):
            if item.is_dir() and VERSION_SEPARATOR in item.name:
                # Check if this folder contains version comparison structure
                found_folders.append(item)
        
        logger.info(f"Found {len(found_folders)} version comparison folder(s)")
        
        # Process each found folder
        for folder_idx, version_folder in enumerate(found_folders):
            try:
                # Extract version names from folder name (e.g., "freedview_1.2.1.3_1.0.0.7_VS_freedView_1.3.0.0_1.0.0.1")
                folder_name = version_folder.name
                if VERSION_SEPARATOR not in folder_name:
                    continue
                
                freedview_split = folder_name.split(VERSION_SEPARATOR)
                if len(freedview_split) != 2:
                    logger.debug(f"Skipping invalid folder name format: {folder_name}")
                    continue
                
                freedview_name_orig = freedview_split[0]
                freedview_name_tester = freedview_split[1]
                freedview_ver = folder_name
                
                # The folder_frame_path is the parent directory (the F#### folder)
                folder_frame_path = str(version_folder.parent)
                
                # Skip folders that already have a results folder with compareResult.xml (already processed)
                results_folder = Path(folder_frame_path) / RESULTS_FOLDER
                result_xml_file = results_folder / COMPARE_RESULT_XML
                if result_xml_file.exists() and result_xml_file.is_file():
                    logger.debug(f"Skipping already-processed folder: {folder_frame_path} (compareResult.xml exists)")
                    continue
                
                # Generate testKey for filtering (relative path from testSets root)
                # Convert testSets_results path to testSets path for testKey generation
                try:
                    # Get relative path from testSets_results root
                    test_sets_results_obj = Path(test_sets_results_path)
                    frame_path_obj = Path(folder_frame_path)
                    relative_from_results = frame_path_obj.relative_to(test_sets_results_obj)
                    # testKey is the same relative path (works for both testSets and testSets_results)
                    test_key = str(relative_from_results).replace('\\', '/')
                    
                    # Apply filter if specified
                    if test_filter_set and test_key not in test_filter_set:
                        continue  # Skip this comparison if not in filter
                except ValueError:
                    # If relative path can't be computed, skip filtering for this item
                    if test_filter_set:
                        continue  # Skip if filter is active but we can't generate testKey
                
                # Create comparison task
                comparison_tasks.append({
                    'folder_idx': folder_idx,
                    'folder_frame': folder_frame_path,
                    'freedview_ver': freedview_ver,
                    'freedview_name_orig': freedview_name_orig,
                    'freedview_name_tester': freedview_name_tester,
                    'total_folders': len(comparison_tasks) + 1  # Will be updated after all tasks are created
                })
                
                logger.debug(f"Found version comparison: {freedview_name_orig} vs {freedview_name_tester} at {folder_frame_path}")
                
            except Exception as e:
                logger.warning(f"Error processing folder '{version_folder}': {e}")
                continue
        
        # Update total_folders for each task now that we know the final count
        for task in comparison_tasks:
            task['total_folders'] = len(comparison_tasks)
        
        logger.info(f"Created {len(comparison_tasks)} comparison task(s) from scanned folders (skipped already-processed folders)")
        return comparison_tasks

    def _compare_single_folder(self, task: dict) -> bool:
        """
        Compare a single frame folder in a thread-safe manner.

        Args:
            task: Dictionary containing comparison task parameters:
                - folder_idx: Index of folder
                - folder_frame: Path to frame folder
                - freedview_ver: FreeDView version string
                - freedview_name_orig: Name of original version
                - freedview_name_tester: Name of test version
                - total_folders: Total number of folders for progress tracking

        Returns:
            True if comparison succeeded, False otherwise
        """
        try:
            # Handle both paths from testSets (need conversion) and testSets_results (already correct)
            folder_frame = task['folder_frame']
            if TEST_SETS_RESULTS_DIR not in folder_frame:
                # Convert from testSets to testSets_results
                replace_path = folder_frame.replace("testSets", TEST_SETS_RESULTS_DIR)
            else:
                # Already in testSets_results
                replace_path = folder_frame
            
            freedview_ver_path = os.path.join(replace_path, task['freedview_ver'])

            if not os.path.exists(freedview_ver_path):
                logger.debug(f"Skipping non-existent path: {freedview_ver_path}")
                return False

            image_orig_list, image_tester_list, freedview_path_orig, freedview_path_tester = (
                self._collect_image_paths(
                    freedview_ver_path, task['freedview_name_orig'], task['freedview_name_tester']
                )
            )

            if (len(image_orig_list) == len(image_tester_list) and
                    len(image_orig_list) > 1 and
                    freedview_path_orig and freedview_path_tester):

                # Thread-safe progress logging
                with self._progress_lock:
                    current_processed = self._processed_folders + 1
                    folder_progress = int((current_processed / task['total_folders']) * 100)
                    logger.info(
                        f"Folder progress: {current_processed}/{task['total_folders']} folders "
                        f"({folder_progress}%) - Processing: {os.path.basename(task['folder_frame'])}"
                    )

                self.render_compare_do_it(
                    freedview_ver_path, image_orig_list, image_tester_list,
                    freedview_path_orig, freedview_path_tester,
                    task['freedview_name_orig'], task['freedview_name_tester']
                )
                return True
            else:
                if len(image_orig_list) != len(image_tester_list):
                    logger.warning(
                        f"The number of frames in the Orig folder ({len(image_orig_list)}) "
                        f"does not match the number of frames in the VS Tested folder "
                        f"({len(image_tester_list)})! Skipping: {task['folder_frame']}"
                    )
                elif len(image_orig_list) <= 1:
                    logger.warning(
                        f"There are no images to compare (found {len(image_orig_list)}). "
                        f"Skipping: {task['folder_frame']}"
                    )
                else:
                    logger.warning(
                        f"The FreeDView versions in the folder do not match "
                        f"the FreeDView versions in the INI file! Skipping: {task['folder_frame']}"
                    )
                return False
        except Exception as e:
            logger.error(f"Error processing frame folder '{task['folder_frame']}': {e}", exc_info=True)
            return False

    def _process_single_frame(
        self,
        frame_index: int,
        orig_image_path: str,
        test_image_path: str,
        start_frame: int,
        diff_folder: str,
        alpha_folder: str
    ) -> Tuple[int, Optional[float], Optional[float], bool]:
        """
        Process a single frame pair: compare images and generate output files.

        Args:
            frame_index: Index of the frame in the sequence
            orig_image_path: Path to original version image
            test_image_path: Path to test version image
            start_frame: Starting frame number for naming
            diff_folder: Directory to save diff images
            alpha_folder: Directory to save alpha images

        Returns:
            Tuple of (frame_index, mse_result, ssim_result, success)
            Returns (frame_index, None, None, False) on failure
        """
        try:
            # Load images from disk for comparison.
            source_frame = cv2.imread(orig_image_path)
            tested_frame = cv2.imread(test_image_path)

            if source_frame is None or tested_frame is None:
                logger.warning(
                    f"Could not read image {orig_image_path} or {test_image_path}. "
                    f"Skipping frame {frame_index}"
                )
                return (frame_index, None, None, False)

            # Validate image dimensions
            if source_frame.shape != tested_frame.shape:
                logger.warning(
                    f"Image dimension mismatch at frame {frame_index}: "
                    f"{source_frame.shape} vs {tested_frame.shape}. Skipping"
                )
                return (frame_index, None, None, False)

            # Convert to grayscale for comparison metrics (MSE and SSIM work on grayscale).
            source_frame_gr = cv2.cvtColor(source_frame, cv2.COLOR_BGR2GRAY)
            tested_frame_gr = cv2.cvtColor(tested_frame, cv2.COLOR_BGR2GRAY)

            # Calculate Mean Squared Error (pixel-level difference metric).
            try:
                mse_result = mean_squared_error(source_frame_gr, tested_frame_gr)
            except ValueError as e:
                logger.warning(f"MSE calculation failed for frame {frame_index}: {e}")
                mse_result = 0.0

            # Calculate Structural Similarity Index (perceptual similarity metric).
            try:
                ssim_result = ssim(source_frame_gr, tested_frame_gr)
            except Exception as e:
                logger.warning(f"SSIM calculation failed for frame {frame_index}: {e}")
                ssim_result = 0.0

            # Create visual difference image showing pixel-level changes.
            difference_image = cv2.absdiff(source_frame_gr, tested_frame_gr)

            # Apply HOT colormap to difference image for better visualization.
            # Hot colormap highlights differences in red/yellow colors.
            im_color = cv2.applyColorMap(difference_image, cv2.COLORMAP_HOT)
            frame_number = start_frame + frame_index
            counter = str(frame_number).zfill(4)
            diff_image_path = os.path.join(diff_folder, f'{counter}.jpg')
            
            if not cv2.imwrite(diff_image_path, im_color):
                logger.warning(f"Failed to write diff image: {diff_image_path}")

            # Create binary mask using Otsu thresholding to identify significant differences.
            _, im_bw = cv2.threshold(
                difference_image, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU
            )

            # Create RGBA alpha image combining colored diff with binary mask as alpha channel.
            # Apply dilation to make differences more visible.
            b, g, r = cv2.split(im_color)
            rgba = [b, g, r, im_bw]
            im_alpha = cv2.merge(rgba)
            kernel = np.ones(DILATION_KERNEL_SIZE, np.uint8)
            dilation = cv2.dilate(im_alpha, kernel, iterations=DILATION_ITERATIONS)
            alpha_image_path = os.path.join(alpha_folder, f'{counter}.png')
            
            if not cv2.imwrite(alpha_image_path, dilation):
                logger.warning(f"Failed to write alpha image: {alpha_image_path}")

            return (frame_index, mse_result, ssim_result, True)

        except Exception as e:
            logger.error(f"Error processing frame {frame_index}: {e}", exc_info=True)
            return (frame_index, None, None, False)

    def _collect_image_paths(
        self,
        freedview_ver_path: str,
        freedview_name_orig: str,
        freedview_name_tester: str
    ) -> Tuple[List[str], List[str], Optional[str], Optional[str]]:
        """
        Collect image paths from FreeDView version directories.

        Args:
            freedview_ver_path: Path to FreeDView version directory
            freedview_name_orig: Name of original version
            freedview_name_tester: Name of test version

        Returns:
            Tuple of (image_orig_list, image_tester_list, freedview_path_orig, freedview_path_tester)
        """
        image_orig_list = []
        image_tester_list = []
        freedview_path_orig = None
        freedview_path_tester = None

        freedview_ver_path_obj = Path(freedview_ver_path)
        if not freedview_ver_path_obj.exists():
            logger.debug(f"Path does not exist: {freedview_ver_path}")
            return image_orig_list, image_tester_list, freedview_path_orig, freedview_path_tester

        for item in freedview_ver_path_obj.iterdir():
            if not item.is_dir() or item.name == RESULTS_FOLDER:
                continue

            item_path = str(item)
            item_name = item.name

            if item_name == freedview_name_orig:
                freedview_path_orig = item_path
                # Collect all rendered image files from original version directory.
                for image_file in item.iterdir():
                    if (image_file.is_file() and 
                            image_file.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS):
                        image_orig_list.append(str(image_file))

            elif item_name == freedview_name_tester:
                freedview_path_tester = item_path
                # Collect all rendered image files from test version directory.
                for image_file in item.iterdir():
                    if (image_file.is_file() and 
                            image_file.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS):
                        image_tester_list.append(str(image_file))

        # Sort lists to ensure matching order
        image_orig_list.sort()
        image_tester_list.sort()

        return image_orig_list, image_tester_list, freedview_path_orig, freedview_path_tester

    def _get_test_sets_results_root(self, path: str) -> Optional[str]:
        """
        Extract testSets_results root directory from a given path.

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
            Relative path string, or original path if conversion fails
        """
        try:
            abs_path_norm = os.path.normpath(absolute_path)
            base_path_norm = os.path.normpath(base_path)
            
            # Use pathlib for reliable relative path calculation
            abs_path_obj = Path(abs_path_norm)
            base_path_obj = Path(base_path_norm)
            
            try:
                relative_path = abs_path_obj.relative_to(base_path_obj)
                # Convert to forward slashes for consistency
                return str(relative_path).replace('\\', '/')
            except ValueError:
                # Paths don't share a common base, return original
                logger.warning(f"Could not make path relative: {absolute_path} (base: {base_path})")
                return absolute_path
        except Exception as e:
            logger.warning(f"Error converting path to relative: {e}")
            return absolute_path

    def write_to_xml_file(
        self,
        result_folder: str,
        compare_type_list: List[List[float]],
        start_frame: str,
        end_frame: str,
        path_list: List[str],
        event_name: str,
        freedview_name_orig: str,
        freedview_name_tester: str,
        sport_type: Optional[str] = None,
        stadium_name: Optional[str] = None,
        category_name: Optional[str] = None
    ) -> None:
        """
        Write comparison results to XML file.

        Args:
            result_folder: Folder where results will be saved
            compare_type_list: List containing [mse_list, ssim_list]
            start_frame: Start frame number (as string)
            end_frame: End frame number (as string)
            path_list: List of paths [orig_path, test_path, result_folder, diff_path, alpha_path]
            event_name: Name of the event
            freedview_name_orig: Name of original FreeDView version
            freedview_name_tester: Name of test FreeDView version
            sport_type: Optional sport type
            stadium_name: Optional stadium name
            category_name: Optional category name

        Raises:
            IOError: If XML file cannot be written
            ValueError: If compare_type_list is empty or invalid
        """
        if not compare_type_list or len(compare_type_list) < 2:
            raise ValueError("compare_type_list must contain [mse_list, ssim_list]")
        
        ssim_list = compare_type_list[1]
        if not ssim_list:
            raise ValueError("SSIM list is empty, cannot generate XML report")

        result_xml_file = os.path.join(result_folder, COMPARE_RESULT_XML)
        result_xml_file = result_xml_file.replace('\\', '/')

        try:
            # Find testSets_results root for relative path conversion
            test_sets_results_root = self._get_test_sets_results_root(result_folder)
            
            root = minidom.Document()
            xml_root = root.createElement('root')
            root.appendChild(xml_root)

            # Add paths (convert to relative if testSets_results root is found)
            paths_to_add = [
                ('sourcePath', path_list[0]),
                ('testPath', path_list[1]),
                ('diffPath', path_list[3]),
                ('alphaPath', path_list[4])
            ]
            
            for path_name, path_value in paths_to_add:
                # Convert to relative path if base is found
                if test_sets_results_root:
                    relative_path = self._make_path_relative(path_value, test_sets_results_root)
                else:
                    relative_path = path_value
                
                element = root.createElement(path_name)
                xml_root.appendChild(element)
                element.appendChild(root.createTextNode(relative_path))

            # Add version names
            for version_name, version_value in [
                ('origFreeDView', freedview_name_orig),
                ('testFreedview', freedview_name_tester)
            ]:
                element = root.createElement(version_name)
                xml_root.appendChild(element)
                element.appendChild(root.createTextNode(str(version_value)))

            # Add metadata
            for meta_name, meta_value in [
                ('eventName', event_name),
                ('sportType', sport_type or ''),
                ('stadiumName', stadium_name or ''),
                ('categoryName', category_name or ''),
                ('startFrame', start_frame),
                ('endFrame', end_frame),
                ('minVal', str(min(ssim_list))),
                ('maxVal', str(max(ssim_list)))
            ]:
                element = root.createElement(meta_name)
                xml_root.appendChild(element)
                element.appendChild(root.createTextNode(str(meta_value)))

            # Add frame data
            frames = root.createElement('frames')
            xml_root.appendChild(frames)

            for x in range(len(ssim_list)):
                frame_index = x + int(start_frame)
                frame_child = root.createElement('frame')
                frames.appendChild(frame_child)

                frame_index_elem = root.createElement('frameIndex')
                frame_index_elem.appendChild(root.createTextNode(str(frame_index)))
                frame_child.appendChild(frame_index_elem)

                value_elem = root.createElement('value')
                value_elem.appendChild(root.createTextNode(str(ssim_list[x])))
                frame_child.appendChild(value_elem)

            xml_str = root.toprettyxml(indent="\t")
            with open(result_xml_file, 'w', encoding='utf-8') as f:
                f.write(xml_str)
            
            logger.info(f"XML report written to: {result_xml_file}")
        except Exception as e:
            logger.error(f"Failed to write XML file '{result_xml_file}': {e}", exc_info=True)
            raise IOError(f"Failed to write XML file: {e}") from e

    def render_compare_do_it(
        self,
        folder_frame_path: str,
        image_orig_list: List[str],
        image_tester_list: List[str],
        freedview_path_orig: str,
        freedview_path_tester: str,
        freedview_name_orig: str,
        freedview_name_tester: str
    ) -> None:
        """
        Compare all images and generate results.

        Args:
            folder_frame_path: Path to frame folder
            image_orig_list: List of original image paths
            image_tester_list: List of test image paths
            freedview_path_orig: Path to original version directory
            freedview_path_tester: Path to test version directory
            freedview_name_orig: Name of original version
            freedview_name_tester: Name of test version
        """
        start_time = time.time()
        logger.info(f"Starting comparison for: {folder_frame_path}")

        # Validate inputs
        if not image_orig_list or not image_tester_list:
            logger.error("Empty image lists provided")
            return

        if len(image_orig_list) != len(image_tester_list):
            logger.error(
                f"Image list length mismatch: {len(image_orig_list)} vs {len(image_tester_list)}"
            )
            return

        # Extract start frame number from first image filename for sequential naming.
        try:
            first_image_name = os.path.basename(image_orig_list[0])
            start_frame = int(first_image_name.split('.')[0])
        except (ValueError, IndexError) as e:
            logger.error(f"Failed to extract start frame from '{image_orig_list[0]}': {e}")
            return

        path_list = [freedview_path_orig, freedview_path_tester]

        # Create results directory structure for comparison outputs.
        result_folder = os.path.join(folder_frame_path, RESULTS_FOLDER)
        result_folder = result_folder.replace('\\', '/')
        result_folder_obj = Path(result_folder)
        try:
            result_folder_obj.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create results folder '{result_folder}': {e}")
            return
        path_list.append(result_folder)

        # Extract event metadata from folder path structure for XML report.
        event_name, sport_type, stadium_name, category_name = (
            self._extract_metadata_from_path(result_folder)
        )

        # Create directories for difference and alpha mask images.
        diff_folder = os.path.join(result_folder, DIFF_IMAGES_FOLDER)
        diff_folder = diff_folder.replace('\\', '/')
        try:
            Path(diff_folder).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create diff_images folder: {e}")
            return
        path_list.append(diff_folder)

        alpha_folder = os.path.join(result_folder, ALPHA_IMAGES_FOLDER)
        alpha_folder = alpha_folder.replace('\\', '/')
        try:
            Path(alpha_folder).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create alpha_images folder: {e}")
            return
        path_list.append(alpha_folder)

        # Compare all image pairs and calculate metrics using parallel frame processing.
        total_frames = len(image_orig_list)
        logger.info(f"Comparing {total_frames} frame(s) with {self.frame_workers} parallel worker thread(s)")

        # Create frame processing tasks
        frame_tasks = [
            (i, orig_image_path, test_image_path)
            for i, (orig_image_path, test_image_path) in enumerate(zip(image_orig_list, image_tester_list))
        ]

        # Process frames in parallel using ThreadPoolExecutor
        frame_results = []  # List of (frame_index, mse, ssim, success) tuples
        progress_interval = max(1, min(10, total_frames // 10))
        completed_count = 0

        def update_progress():
            nonlocal completed_count
            with self._progress_lock:
                completed_count += 1
                # Update overall completed frames (thread-safe)
                self._completed_frames_all += 1
                
                # Report overall progress if we have total frames calculated
                if self._total_frames_all > 0:
                    overall_percent = int((self._completed_frames_all / self._total_frames_all) * 100)
                    # Only log at intervals to avoid too many messages
                    if completed_count % progress_interval == 0 or completed_count == total_frames:
                        logger.info(
                            f"Overall progress: {self._completed_frames_all}/{self._total_frames_all} frames "
                            f"({overall_percent}%) - Current folder: {completed_count}/{total_frames} frames"
                        )
                else:
                    # Fallback to per-folder progress if total not calculated
                    if completed_count % progress_interval == 0 or completed_count == total_frames:
                        progress_percent = int((completed_count / total_frames) * 100)
                        logger.info(f"Progress: {completed_count}/{total_frames} frames ({progress_percent}%)")

        with ThreadPoolExecutor(max_workers=self.frame_workers) as executor:
            futures = {
                executor.submit(
                    self._process_single_frame,
                    frame_index,
                    orig_image_path,
                    test_image_path,
                    start_frame,
                    diff_folder,
                    alpha_folder
                ): frame_index
                for frame_index, orig_image_path, test_image_path in frame_tasks
            }

            # Collect results as they complete
            for future in as_completed(futures):
                result = future.result()
                frame_results.append(result)
                update_progress()
            # Executor will automatically shutdown when exiting the 'with' block

        # Sort results by frame index to maintain order
        frame_results.sort(key=lambda x: x[0])

        # Extract MSE and SSIM results in order
        result_mse_list = []
        result_ssim_list = []
        failed_comparisons = 0

        for frame_index, mse_result, ssim_result, success in frame_results:
            if success and mse_result is not None and ssim_result is not None:
                result_mse_list.append(mse_result)
                result_ssim_list.append(ssim_result)
            else:
                # Handle failed frames by appending default values
                result_mse_list.append(0.0)
                result_ssim_list.append(0.0)
                failed_comparisons += 1

        # Progress is now logged dynamically during parallel processing

        successful_comparisons = total_frames - failed_comparisons
        
        # Report final overall progress for this folder's completion
        with self._progress_lock:
            if self._total_frames_all > 0:
                overall_percent = int((self._completed_frames_all / self._total_frames_all) * 100)
                logger.info(
                    f"Frame comparison completed: {successful_comparisons}/{total_frames} frames processed successfully. "
                    f"Overall progress: {self._completed_frames_all}/{self._total_frames_all} frames ({overall_percent}%)"
                )
            else:
                logger.info(
                    f"Frame comparison completed: {successful_comparisons}/{total_frames} "
                    f"frames processed successfully"
                )

        if failed_comparisons > 0:
            logger.warning(
                f"Failed to process {failed_comparisons} out of {total_frames} frame(s)"
            )

        if not result_ssim_list:
            logger.error("No valid comparisons completed. Cannot generate XML report.")
            # Clean up empty results folder since no work was done
            try:
                if result_folder_obj.exists():
                    logger.debug(f"Cleaning up empty results folder: {result_folder}")
                    shutil.rmtree(result_folder)
            except Exception as e:
                logger.warning(f"Error cleaning up empty results folder {result_folder}: {e}")
            return

        # Generate XML report with comparison metrics and metadata.
        compare_type_list = [result_mse_list, result_ssim_list]
        start_frame_str = str(start_frame).zfill(4)
        end_frame = len(image_orig_list) + start_frame - 1
        end_frame_str = str(end_frame).zfill(4)

        try:
            self.write_to_xml_file(
                result_folder, compare_type_list, start_frame_str, end_frame_str,
                path_list, event_name, freedview_name_orig, freedview_name_tester,
                sport_type, stadium_name, category_name
            )
            
            # Count created images and calculate elapsed time
            elapsed_time = time.time() - start_time
            diff_images_count = len(list(Path(diff_folder).glob('*.jpg'))) if Path(diff_folder).exists() else 0
            alpha_images_count = len(list(Path(alpha_folder).glob('*.png'))) if Path(alpha_folder).exists() else 0
            total_images_created = diff_images_count + alpha_images_count
            
            logger.info(f"Successfully completed comparison for: {folder_frame_path}")
            logger.info(
                f"Summary: Created {total_images_created} images ({diff_images_count} diff images, "
                f"{alpha_images_count} alpha images) in {elapsed_time:.2f} seconds ({elapsed_time/60:.2f} minutes)"
            )
        except Exception as e:
            logger.error(f"Failed to generate XML report: {e}", exc_info=True)
            # Check if any output files were actually created
            diff_files = list(Path(diff_folder).glob('*.jpg')) if Path(diff_folder).exists() else []
            alpha_files = list(Path(alpha_folder).glob('*.png')) if Path(alpha_folder).exists() else []
            xml_file = Path(result_folder) / COMPARE_RESULT_XML
            if not diff_files and not alpha_files and not xml_file.exists():
                # No files were created, clean up the folder structure
                try:
                    if result_folder_obj.exists():
                        logger.debug(f"Cleaning up results folder with no output files: {result_folder}")
                        shutil.rmtree(result_folder)
                except Exception as e:
                    logger.warning(f"Error cleaning up results folder {result_folder}: {e}")

    def _extract_metadata_from_path(
        self, result_folder: str
    ) -> Tuple[str, str, str, str]:
        """
        Extract event metadata from folder path structure.

        Args:
            result_folder: Path to result folder

        Returns:
            Tuple of (event_name, sport_type, stadium_name, category_name)
        """
        result_structure = result_folder.split(TEST_SETS_RESULTS_DIR)
        if len(result_structure) < 2:
            logger.debug(f"Could not extract metadata from path: {result_folder}")
            return "", "", "", ""

        split_string = result_structure[1].split("/")
        split_string = [s for s in split_string if s]  # Remove empty strings

        sport_type = ""
        stadium_name = ""
        category_name = ""
        event_name = ""

        if len(split_string) == 5:  # Direct event
            event_name = split_string[0]
        elif len(split_string) == 6:  # sportType/event
            sport_type = split_string[0]
            event_name = split_string[1]
        elif len(split_string) == 7:  # sportType/stadiumName/event
            sport_type = split_string[0]
            stadium_name = split_string[1]
            event_name = split_string[2]
        elif len(split_string) >= 8:  # sportType/stadiumName/categoryName/event
            sport_type = split_string[0]
            stadium_name = split_string[1]
            category_name = split_string[2]
            event_name = split_string[3]

        return event_name, sport_type, stadium_name, category_name


def run_render_compare() -> None:
    """Run render compare as standalone script."""
    project_path = os.path.dirname(__file__)
    ini_path = os.path.join(project_path, 'freeDView_tester.ini')
    RenderCompare(ini_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Render compare")
    parser.add_argument(
        "-sa",
        action="store_true",
        dest="standalone",
        help="run script as stand alone"
    )

    args = parser.parse_args()
    if args.standalone:
        logger.info("Running render compare as stand alone process.")
        run_render_compare()
