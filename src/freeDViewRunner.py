"""
Phase 2: FreeDView Runner

This module renders the sets in the "testSets" directory and creates
new sequential images using the FreeDView renderer.
"""
import re
import os
import logging
import json
import shutil
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import getDataIni as data_ini
import jsonLocalizer as json_localizer

# Constants
TEST_SETS_DIR = "testSets"
TEST_SETS_RESULTS_DIR = "testSets_results"
VERSION_SEPARATOR = "_VS_"
DYNAMIC_INIS_BACKUP = "dynamicINIsBackup"
CAMERA_CONTROL_INI = "cameracontrol.ini"
CAMPRESET_INI = "campreset.ini"
FREEDVIEW_EXE = "freedview.exe"
STANDALONE_RENDER = "standAloneRender"
TEST_ME_JSON = "testMe"
OUTPUT_IMAGE_PREFIX = "wauwStills_F.jpg"
CLUSTER_SIZE = "12"
VIDEO_EXPORT_CAMERA_NAME = "renderCAM_NEWShape"
DEFAULT_MAX_WORKERS = 4  # Default number of parallel rendering threads

# Configure module-level logger
logger = logging.getLogger(__name__)


class FreeDViewRunner:
    """Handles running FreeDView renderer on test sets."""

    def __init__(self, max_workers: int = DEFAULT_MAX_WORKERS):
        """
        Initialize FreeDViewRunner.

        Args:
            max_workers: Maximum number of parallel rendering threads (default: 4)
        """
        self.max_workers = max_workers
        self._progress_lock = Lock()
        self._render_count = 0
        self._successful_renders = 0
        self._failed_renders = 0

    def do_it(self, ini_path: str) -> None:
        """
        Main entry point for FreeDView rendering process.

        Args:
            ini_path: Path to the INI configuration file
        """
        logger.info("-- FreeDViewRunner --")

        # Read configuration from INI file to get paths and version information.
        set_test_path_tag = 'setTestPath'
        freedview_path_tag = 'freedviewPath'
        freedview_ver_tag = 'freedviewVer'
        event_name_tag = 'eventName'
        set_name_tag = 'setName'

        json_file_path_set_test = data_ini.getDataINI(ini_path, set_test_path_tag)[0]
        freedview_path = data_ini.getDataINI(ini_path, freedview_path_tag)[0]
        freedview_ver = data_ini.getDataINI(ini_path, freedview_ver_tag)[0]
        event_name_set_test = data_ini.getDataINI(ini_path, event_name_tag)[0]
        set_name_set_test = data_ini.getDataINI(ini_path, set_name_tag)[0]

        # Validate INI data
        if (json_file_path_set_test == data_ini.ERROR_VALUE or
                freedview_path == data_ini.ERROR_VALUE or
                freedview_ver == data_ini.ERROR_VALUE):
            logger.error(f"Failed to read required configuration from INI file: {ini_path}")
            return

        # Use JsonLocalizer to find all JSON files that need to be rendered.
        json_localizer_obj = json_localizer.JsonLocalizer()

        # Get JSON file paths from JsonLocalizer without creating folders.
        create_folders = None
        get_json_info = json_localizer_obj.get_json_files(
            json_file_path_set_test, event_name_set_test,
            set_name_set_test, create_folders
        )

        # Extract frame and JSON file lists from JsonLocalizer results.
        folder_frame_list = get_json_info[1]
        json_file_list = get_json_info[4]

        if not json_file_list:
            logger.warning("No JSON files found to render")
            return

        logger.info(f"FreeDView version: {freedview_ver}")
        logger.info(f"Processing {len(json_file_list)} JSON file(s)")

        # Parse version string to extract original and test version names.
        # Format: "version1_VS_version2"
        try:
            freedview_split = freedview_ver.split(VERSION_SEPARATOR)
            if len(freedview_split) != 2:
                logger.error(
                    f"Invalid version format in INI file. "
                    f"Expected 'version1{VERSION_SEPARATOR}version2', got: {freedview_ver}"
                )
                return
            freedview_orig, freedview_test = freedview_split
        except Exception as e:
            logger.error(f"Error parsing version string '{freedview_ver}': {e}")
            return

        # Locate FreeDView version directories in the specified path.
        freedview_ver_path_list, freedview_ver_name_list = (
            self._get_freedview_versions(freedview_path, freedview_ver,
                                        freedview_orig, freedview_test)
        )

        if not freedview_ver_path_list:
            logger.error(
                f"No FreeDView versions found in path: {freedview_path}. "
                f"Expected versions: {freedview_orig}, {freedview_test}"
            )
            return

        logger.info(
            f"Found {len(freedview_ver_path_list)} FreeDView version(s): "
            f"{', '.join(freedview_ver_name_list)}"
        )

        # Process each FreeDView version and render all JSON files using parallel threads.
        total_renders = len(freedview_ver_path_list) * len(json_file_list)
        self._render_count = 0
        self._successful_renders = 0
        self._failed_renders = 0

        # Create list of all render tasks
        render_tasks = []
        for i, freedview_ver_path in enumerate(freedview_ver_path_list):
            for x, json_file_path in enumerate(json_file_list):
                render_tasks.append({
                    'version_index': i,
                    'freedview_ver_path': freedview_ver_path,
                    'freedview_ver_name': freedview_ver_name_list[i],
                    'json_index': x,
                    'json_file_path': json_file_path,
                    'folder_frame': folder_frame_list[x],
                    'freedview_ver': freedview_ver,  # Full version string for path building
                    'total_renders': total_renders  # For progress tracking
                })

        logger.info(
            f"Starting parallel rendering with {self.max_workers} worker thread(s) "
            f"for {total_renders} render task(s)"
        )

        # Execute renders in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._render_single_task, task): task
                for task in render_tasks
            }

            # Process completed tasks
            for future in as_completed(futures):
                task = futures[future]
                try:
                    success = future.result()
                    if success:
                        self._successful_renders += 1
                    else:
                        self._failed_renders += 1
                except Exception as e:
                    logger.error(
                        f"Unexpected error in render task (version {task['freedview_ver_name']}, "
                        f"file {os.path.basename(task['json_file_path'])}): {e}",
                        exc_info=True
                    )
                    self._failed_renders += 1

        logger.info(
            f"Completed parallel rendering: {self._successful_renders} successful, "
            f"{self._failed_renders} failed out of {total_renders} total renders"
        )
        logger.info("========================= Done FreedviewRunner ============================")

    def _render_single_task(self, task: dict) -> bool:
        """
        Render a single task (one version + one JSON file) in a thread-safe manner.

        Args:
            task: Dictionary containing render task parameters:
                - version_index: Index of FreeDView version
                - freedview_ver_path: Path to FreeDView version directory
                - freedview_ver_name: Name of FreeDView version
                - json_index: Index of JSON file
                - json_file_path: Path to JSON file
                - folder_frame: Path to frame folder

        Returns:
            True if render succeeded, False otherwise
        """
        try:
            # Thread-safe progress tracking
            with self._progress_lock:
                self._render_count += 1
                current_count = self._render_count
                total_renders = task.get('total_renders', 0)

            if total_renders > 0:
                progress_pct = int((current_count / total_renders) * 100)
                logger.info(
                    f"Render progress: {current_count}/{total_renders} ({progress_pct}%) - "
                    f"Version: {task['freedview_ver_name']}, "
                    f"File: {os.path.basename(task['json_file_path'])}"
                )
            else:
                logger.info(
                    f"Render task: Version {task['freedview_ver_name']}, "
                    f"File {os.path.basename(task['json_file_path'])}"
                )

            # Verify required INI files exist in dynamicINIsBackup folder.
            camera_control_ini = os.path.join(
                task['folder_frame'], DYNAMIC_INIS_BACKUP, CAMERA_CONTROL_INI
            )
            if not os.path.exists(camera_control_ini):
                logger.error(
                    f"The {CAMERA_CONTROL_INI} is missing in "
                    f"{task['folder_frame']}. Skipping render."
                )
                return False

            campreset_ini = os.path.join(
                task['folder_frame'], DYNAMIC_INIS_BACKUP, CAMPRESET_INI
            )
            if not os.path.exists(campreset_ini):
                logger.error(
                    f"The {CAMPRESET_INI} is missing in "
                    f"{task['folder_frame']}. Skipping render."
                )
                return False

            # Read output resolution from camera control INI file.
            try:
                output_width = data_ini.getDataINI(camera_control_ini, 'outputWidth')[0]
                output_height = data_ini.getDataINI(camera_control_ini, 'outputHeight')[0]

                if (output_width == data_ini.ERROR_VALUE or
                        output_height == data_ini.ERROR_VALUE):
                    logger.error(
                        f"Failed to read output resolution from {camera_control_ini}"
                    )
                    return False

                output_res = [int(output_width), int(output_height)]
            except (ValueError, IndexError) as e:
                logger.error(
                    f"Invalid output resolution in {camera_control_ini}: {e}"
                )
                return False

            # Read frame range from testMe.json file created by JsonLocalizer.
            try:
                with open(task['json_file_path'], 'r', encoding='utf-8') as data_file:
                    json_data = json.load(data_file)
                    start_frame = json_data['startFrame']
                    end_frame = json_data['endFrame']
                    sequence_length = [start_frame, end_frame]
            except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
                logger.error(f"Failed to read JSON file {task['json_file_path']}: {e}")
                return False

            # Create output directory structure: testSets_results/.../version_name.
            # Replace existing output to ensure clean renders.
            replace_path = task['folder_frame'].replace(
                TEST_SETS_DIR, TEST_SETS_RESULTS_DIR
            )
            freedview_ver_path_dir = os.path.join(replace_path, task['freedview_ver'])
            output_path = os.path.join(
                freedview_ver_path_dir, task['freedview_ver_name']
            )
            output_path = output_path.replace('\\', '/')

            output_path_obj = Path(output_path)
            if output_path_obj.exists():
                logger.debug(f"Removing existing output directory: {output_path}")
                shutil.rmtree(output_path)
            try:
                output_path_obj.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"Failed to create output directory {output_path}: {e}")
                return False

            # Use testMe.json (localized version) instead of standAloneRender.json.
            set_test_path = task['json_file_path'].replace(STANDALONE_RENDER, TEST_ME_JSON)
            self.run_freedview(
                task['freedview_ver_path'], set_test_path, output_res,
                output_path, sequence_length
            )
            return True

        except Exception as e:
            logger.error(
                f"Error processing render (version {task['freedview_ver_name']}, "
                f"file {task['json_file_path']}): {e}",
                exc_info=True
            )
            return False

    def _get_freedview_versions(
        self,
        freedview_path: str,
        freedview_ver: str,
        freedview_orig: str,
        freedview_test: str
    ) -> Tuple[List[str], List[str]]:
        """
        Get all FreeDView versions from the folder path.

        Args:
            freedview_path: Base path to FreeDView versions
            freedview_ver: Version string to match
            freedview_orig: Original version name
            freedview_test: Test version name

        Returns:
            Tuple of (version_path_list, version_name_list)
        """
        freedview_ver_path_list = []
        freedview_ver_name_list = []

        freedview_path_obj = Path(freedview_path)
        if not freedview_path_obj.exists():
            logger.warning(f"FreeDView path does not exist: {freedview_path}")
            return freedview_ver_path_list, freedview_ver_name_list

        # Find the matching version folder
        for item in freedview_path_obj.iterdir():
            if not item.is_dir():
                continue

            if item.name == freedview_ver:
                # Look for original and test versions inside
                for sub_item in item.iterdir():
                    if not sub_item.is_dir():
                        continue

                    dir_name = sub_item.name
                    if dir_name == freedview_orig:
                        freedview_ver_path_list.append(str(sub_item.absolute()))
                        freedview_ver_name_list.append(dir_name)
                        logger.debug(f"Found original version: {dir_name}")
                    elif dir_name == freedview_test:
                        freedview_ver_path_list.append(str(sub_item.absolute()))
                        freedview_ver_name_list.append(dir_name)
                        logger.debug(f"Found test version: {dir_name}")

        return freedview_ver_path_list, freedview_ver_name_list

    def run_freedview(
        self,
        fd_path: str,
        set_test_path: str,
        output_res: List[int],
        output_path: str,
        sequence_length: List[int]
    ) -> None:
        """
        Run FreeDView to create new images and rename them.

        Args:
            fd_path: Path to FreeDView executable directory
            set_test_path: Path to test JSON file
            output_res: Output resolution [width, height]
            output_path: Path where output images will be saved
            sequence_length: [start_frame, end_frame]
        """
        logger.info(f"Running FreeDView render: {os.path.basename(set_test_path)}")

        output_res_x = output_res[0]
        output_res_y = output_res[1]
        start_frame = sequence_length[0]
        end_frame = sequence_length[1]

        # Build command line arguments for FreeDView executable.
        # FreeDView exports video frames as sequential images.
        freedview_exe = os.path.join(fd_path, FREEDVIEW_EXE)
        
        if not os.path.exists(freedview_exe):
            logger.error(f"FreeDView executable not found: {freedview_exe}")
            return

        output_file_path = os.path.join(output_path, OUTPUT_IMAGE_PREFIX)

        cmd = [
            freedview_exe,
            set_test_path,
            '-exportVideo',
            '-imageSize', f'{output_res_x}x{output_res_y}',
            '-videoOutputPath', output_file_path,
            '-clusterSize', CLUSTER_SIZE,
            '-startFrame', str(start_frame),
            '-endFrame', str(end_frame),
            '-vidExportCameraName', VIDEO_EXPORT_CAMERA_NAME
        ]

        logger.debug(f"FreeDView command: {' '.join(cmd)}")

        # Execute FreeDView renderer as subprocess.
        # Capture stdout/stderr for error reporting.
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=fd_path
            )
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore')
                logger.error(
                    f"FreeDView process failed with return code {process.returncode}. "
                    f"Error: {error_msg}"
                )
                return
            else:
                logger.debug("FreeDView process completed successfully")

        except FileNotFoundError:
            logger.error(f"FreeDView executable not found: {freedview_exe}")
            return
        except Exception as e:
            logger.error(f"Exception running FreeDView: {e}", exc_info=True)
            return

        # Rename rendered images to sequential format (e.g., 0001.jpg, 0002.jpg).
        # FreeDView may generate files with different naming, so we standardize them.
        output_path_obj = Path(output_path)
        renamed_count = 0
        
        try:
            for image_file in output_path_obj.iterdir():
                if image_file.is_file():
                    image_file_path = str(image_file)
                    # Extract frame number from filename using regex.
                    frame_numbers = re.findall(r'\d+', image_file_path)
                    if frame_numbers:
                        frame_index = frame_numbers[-1]
                        new_image_path = output_path_obj / f"{frame_index}.jpg"
                        if image_file_path != str(new_image_path):
                            image_file.rename(new_image_path)
                            renamed_count += 1

            if renamed_count > 0:
                logger.debug(f"Renamed {renamed_count} image file(s)")
            else:
                logger.debug("No image files needed renaming")
        except Exception as e:
            logger.warning(f"Error renaming image files in {output_path}: {e}")

        logger.debug(f"Render completed for: {set_test_path}")


def run_freedview_runner() -> None:
    """Run FreeDView runner as standalone script."""
    project_path = os.path.dirname(__file__)
    ini_path = os.path.join(project_path, 'freeDView_tester.ini')
    freedview_runner = FreeDViewRunner()
    freedview_runner.do_it(ini_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FreeDView runner")
    parser.add_argument(
        "-sa",
        action="store_true",
        dest="standalone",
        help="run script as stand alone"
    )

    args = parser.parse_args()
    if args.standalone:
        logger.info("Running FreeDView runner as stand alone process.")
        run_freedview_runner()
