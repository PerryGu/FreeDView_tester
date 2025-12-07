"""
Phase 3: Render Compare

This module compares sequences of different rendered FreeDView versions and
creates new sequential alpha_images, diff_images, and compareResult.xml file.
"""
import os
import logging
import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional
from xml.dom import minidom
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

    def __init__(self, ini_path: Optional[str] = None, max_workers: int = DEFAULT_MAX_WORKERS) -> None:
        """
        Initialize RenderCompare.

        Args:
            ini_path: Path to the INI configuration file
            max_workers: Maximum number of parallel comparison threads (default: 4)
        """
        self.max_workers = max_workers
        self._progress_lock = Lock()
        self._processed_folders = 0
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

        set_test_path = data_ini.getDataINI(ini_path, set_test_path_tag)[0]
        freedview_ver = data_ini.getDataINI(ini_path, freedview_ver_tag)[0]
        event_name_set_test = data_ini.getDataINI(ini_path, event_name_tag)[0]
        set_name_set_test = data_ini.getDataINI(ini_path, set_name_tag)[0]

        # Validate INI data
        if set_test_path == data_ini.ERROR_VALUE or freedview_ver == data_ini.ERROR_VALUE:
            logger.error(f"Failed to read required configuration from INI file: {ini_path}")
            return

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
            set_test_path, event_name_set_test, set_name_set_test, create_folders
        )

        folder_frame_list = get_json_info[1]

        if not folder_frame_list:
            logger.warning("No frame folders found to process")
            return

        total_folders = len(folder_frame_list)
        self._processed_folders = 0
        logger.info(
            f"Processing {total_folders} frame folder(s) with {self.max_workers} parallel worker thread(s)"
        )

        # Create list of comparison tasks
        comparison_tasks = []
        for folder_idx, folder_frame in enumerate(folder_frame_list):
            comparison_tasks.append({
                'folder_idx': folder_idx,
                'folder_frame': folder_frame,
                'freedview_ver': freedview_ver,
                'freedview_name_orig': freedview_name_orig,
                'freedview_name_tester': freedview_name_tester,
                'total_folders': total_folders
            })

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
        
        logger.info(
            f"Completed parallel processing: {self._processed_folders}/{total_folders} "
            f"folders processed successfully"
        )

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
            replace_path = task['folder_frame'].replace(TEST_SETS_DIR, TEST_SETS_RESULTS_DIR)
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
            root = minidom.Document()
            xml_root = root.createElement('root')
            root.appendChild(xml_root)

            # Add paths
            for path_name, path_value in [
                ('sourcePath', path_list[0]),
                ('testPath', path_list[1]),
                ('diffPath', path_list[3]),
                ('alphaPath', path_list[4])
            ]:
                element = root.createElement(path_name)
                xml_root.appendChild(element)
                element.appendChild(root.createTextNode(str(path_value)))

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

        # Compare all image pairs and calculate metrics.
        result_mse_list = []
        result_ssim_list = []
        failed_comparisons = 0

        total_frames = len(image_orig_list)
        logger.info(f"Comparing {total_frames} frame(s)")

        # Progress indication: log every 10% or every 10 frames, whichever is more frequent
        progress_interval = max(1, min(10, total_frames // 10))
        last_progress_log = -1

        for i, (orig_image_path, test_image_path) in enumerate(
            zip(image_orig_list, image_tester_list)
        ):
            # Log progress
            if i % progress_interval == 0 or i == total_frames - 1:
                progress_percent = int((i + 1) / total_frames * 100)
                logger.info(f"Progress: {i + 1}/{total_frames} frames ({progress_percent}%)")
                last_progress_log = i
            try:
                # Load images from disk for comparison.
                source_frame = cv2.imread(orig_image_path)
                tested_frame = cv2.imread(test_image_path)

                if source_frame is None or tested_frame is None:
                    logger.warning(
                        f"Could not read image {orig_image_path} or {test_image_path}. "
                        f"Skipping frame {i}"
                    )
                    failed_comparisons += 1
                    continue

                # Validate image dimensions
                if source_frame.shape != tested_frame.shape:
                    logger.warning(
                        f"Image dimension mismatch at frame {i}: "
                        f"{source_frame.shape} vs {tested_frame.shape}. Skipping"
                    )
                    failed_comparisons += 1
                    continue

                # Convert to grayscale for comparison metrics (MSE and SSIM work on grayscale).
                source_frame_gr = cv2.cvtColor(source_frame, cv2.COLOR_BGR2GRAY)
                tested_frame_gr = cv2.cvtColor(tested_frame, cv2.COLOR_BGR2GRAY)

                # Calculate Mean Squared Error (pixel-level difference metric).
                try:
                    mse_result = mean_squared_error(source_frame_gr, tested_frame_gr)
                    result_mse_list.append(mse_result)
                except ValueError as e:
                    logger.warning(f"MSE calculation failed for frame {i}: {e}")
                    mse_result = 0.0
                    result_mse_list.append(mse_result)

                # Calculate Structural Similarity Index (perceptual similarity metric).
                try:
                    ssim_result = ssim(source_frame_gr, tested_frame_gr)
                    result_ssim_list.append(ssim_result)
                except Exception as e:
                    logger.warning(f"SSIM calculation failed for frame {i}: {e}")
                    ssim_result = 0.0
                    result_ssim_list.append(ssim_result)

                # Create visual difference image showing pixel-level changes.
                difference_image = cv2.absdiff(source_frame_gr, tested_frame_gr)

                # Apply HOT colormap to difference image for better visualization.
                # Hot colormap highlights differences in red/yellow colors.
                im_color = cv2.applyColorMap(difference_image, cv2.COLORMAP_HOT)
                frame_number = start_frame + i
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

            except Exception as e:
                logger.error(f"Error processing frame {i}: {e}", exc_info=True)
                failed_comparisons += 1
                continue

        # Log final progress if not already logged
        if last_progress_log < total_frames - 1:
            logger.info(f"Progress: {total_frames}/{total_frames} frames (100%)")

        successful_comparisons = total_frames - failed_comparisons
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
            logger.info(f"Successfully completed comparison for: {folder_frame_path}")
        except Exception as e:
            logger.error(f"Failed to generate XML report: {e}", exc_info=True)

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
