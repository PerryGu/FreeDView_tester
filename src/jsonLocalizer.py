"""
Phase 1: JSON Localizer

This module changes all paths in "standAloneRender.json" files and writes new files
called "testMe.json". The new paths are set to the local directory structure
so FreeDView can render the sets.
"""
import os
import logging
import json
from pathlib import Path
from typing import List, Tuple, Optional
import getDataIni as data_ini

# Configure module-level logger
logger = logging.getLogger(__name__)


class JsonLocalizer:
    """Handles JSON file localization for FreeDView rendering."""

    def __init__(self):
        self.sport_folder_index = 1
        self.stadium_folder_index = 1

    def do_it(self, ini_path: Optional[str] = None) -> None:
        """
        Main entry point for JSON localization process.

        Args:
            ini_path: Path to the INI configuration file
        """
        logger.info("-- JsonLocalizer ---")

        # Read configuration from INI file to get test paths and patterns.
        set_test_path_tag = 'setTestPath'
        event_name_tag = 'eventName'
        set_name_tag = 'setName'

        json_file_path_set_test = data_ini.getDataINI(ini_path, set_test_path_tag)[0]
        event_name_set_test = data_ini.getDataINI(ini_path, event_name_tag)[0]
        set_name_set_test = data_ini.getDataINI(ini_path, set_name_tag)[0]

        # Validate INI data
        if json_file_path_set_test == data_ini.ERROR_VALUE:
            logger.error(f"Failed to read required configuration from INI file: {ini_path}")
            return

        # Search for all JSON files matching the event and set name patterns.
        # Set create_folders to False to avoid modifying directory structure.
        create_folders = False
        (folder_set_list, folder_frame_list, frame_name_list,
         json_folder_list, json_file_list,
         event_with_set_path_list) = self.get_json_files(
            json_file_path_set_test, event_name_set_test,
            set_name_set_test, create_folders
        )

        # Create localized copies of JSON files with updated paths.
        self.duplicate_and_modify_json_files(
            json_file_path_set_test, folder_set_list, folder_frame_list,
            frame_name_list, json_folder_list, json_file_list,
            event_with_set_path_list
        )

    def get_json_files(
        self,
        json_file_path: str,
        event_name_set_test: str,
        set_name_set_test: str,
        create_folders: bool
    ) -> Tuple[List[str], List[str], List[str], List[str], List[str], List[str]]:
        """
        Find all JSON files in the directory structure.

        Args:
            json_file_path: Base path to search for JSON files
            event_name_set_test: Pattern to match event names
            set_name_set_test: Pattern to match set names
            create_folders: Whether to create missing folder structures

        Returns:
            Tuple of lists: (folder_set_list, folder_frame_list, frame_name_list,
                           json_folder_list, json_file_list, event_with_set_path_list)
        """
        event_path_list = []
        self.sport_folder_index = 1

        # Traverse directory structure to find events.
        # Directory structure can be: Event, SportType/Event, SportType/Stadium/Event,
        # or SportType/Stadium/Category/Event.
        base_path = Path(json_file_path)
        if not base_path.exists():
            logger.warning(f"Base path does not exist: {json_file_path}")
            return ([], [], [], [], [], [])

        # Iterate through directories and identify events using pattern matching.
        for item in base_path.iterdir():
            if not item.is_dir():
                continue

            event_path = str(item)
            self.stadium_folder_index = 1

            # Check if current directory matches event pattern or needs deeper traversal.
            is_event = self.is_event(event_name_set_test, event_path)

            if not is_event:
                # Not an event - this is a Sport Type folder, need to drill deeper.
                event_path = self._traverse_sport_type(
                    item, event_name_set_test, create_folders
                )
                if event_path:
                    event_path_list.append(event_path)
            else:
                # This is an event
                if create_folders:
                    drilling_depth = 3
                    new_folder_path = self.create_extra_folder(
                        event_path, drilling_depth
                    )
                    event_path = new_folder_path
                event_path_list.append(event_path)

        # Collect all sets and frames from found events.
        folder_set_list = []
        folder_frame_list = []
        frame_name_list = []
        json_folder_list = []
        json_file_list = []
        event_with_set_path_list = []

        for event_path in event_path_list:
            event_path_obj = Path(event_path)
            if not event_path_obj.exists():
                continue

            # Iterate through sets in each event folder.
            for set_item in event_path_obj.iterdir():
                if not set_item.is_dir():
                    continue

                set_path = str(set_item)

                # Iterate through frames in each set folder.
                for frame_item in set_item.iterdir():
                    if not frame_item.is_dir():
                        continue

                    frame_path = str(frame_item)
                    frame_name = frame_item.name

                    # Validate frame name matches pattern (e.g., "F1234").
                    # Frame names must start with 'F' followed by digits.
                    split_string = frame_name.split('F')
                    if len(split_string) == 2:
                        try:
                            int(split_string[-1])  # Validate it's a number.

                            # Locate the Render/Json folder containing standAloneRender.json.
                            json_folder = os.path.join(frame_path, 'Render', 'Json')
                            json_file = os.path.join(json_folder, 'standAloneRender.json')

                            if os.path.exists(json_file):
                                folder_set_list.append(set_path)
                                folder_frame_list.append(frame_path)
                                frame_name_list.append(frame_name)
                                json_folder_list.append(json_folder)
                                json_file_list.append(json_file.replace('\\', '/'))
                                event_with_set_path_list.append(event_path)

                        except ValueError:
                            pass

        return (folder_set_list, folder_frame_list, frame_name_list,
                json_folder_list, json_file_list, event_with_set_path_list)

    def _traverse_sport_type(
        self,
        sport_type_path: Path,
        event_name_set_test: str,
        create_folders: bool
    ) -> Optional[str]:
        """
        Traverse sport type directory to find events.

        Args:
            sport_type_path: Path to sport type directory
            event_name_set_test: Pattern to match event names
            create_folders: Whether to create missing folders

        Returns:
            Event path if found, None otherwise
        """
        for stadium_item in sport_type_path.iterdir():
            if not stadium_item.is_dir():
                continue

            stadium_path = str(stadium_item)
            is_event = self.is_event(event_name_set_test, stadium_path)

            if not is_event:
                # Not an event - this is a Stadium Name folder, need to drill deeper.
                event_path = self._traverse_stadium(
                    stadium_item, event_name_set_test
                )
                if event_path:
                    return event_path
            else:
                # Found an event at stadium level.
                if create_folders:
                    drilling_depth = 2
                    new_folder_path = self.create_extra_folder(
                        stadium_path, drilling_depth
                    )
                    return new_folder_path
                return stadium_path

        return None

    def _traverse_stadium(
        self,
        stadium_path: Path,
        event_name_set_test: str
    ) -> Optional[str]:
        """
        Traverse stadium directory to find events.

        Args:
            stadium_path: Path to stadium directory
            event_name_set_test: Pattern to match event names

        Returns:
            Event path if found, None otherwise
        """
        for category_item in stadium_path.iterdir():
            if not category_item.is_dir():
                        continue

            category_path = str(category_item)
            is_event = self.is_event(event_name_set_test, category_path)

            if is_event:
                return category_path

        return None

    def create_extra_folder(
        self,
        parent_path: str,
        drilling_depth: int
    ) -> str:
        """
        Create extra folder structure if missing.

        Args:
            parent_path: Parent path where folders should be created
            drilling_depth: Depth of folder structure to create (2 or 3)

        Returns:
            Path to the new event location
        """
        parent_path_obj = Path(parent_path)
        event_only = parent_path_obj.name

        if drilling_depth == 2:
            # Create missing folder structure: stadiumName_X/categoryName/eventName.
            # Use incremental index to avoid conflicts with existing folders.
            parent_dir = parent_path_obj.parent
            stadium_folder_path = parent_dir / f'stadiumName_{self.stadium_folder_index}'

            while (stadium_folder_path / 'categoryName').exists():
                self.stadium_folder_index += 1
                stadium_folder_path = parent_dir / f'stadiumName_{self.stadium_folder_index}'

            new_folder_path = stadium_folder_path / 'categoryName'
            new_folder_path.mkdir(parents=True, exist_ok=True)
            new_event_path = new_folder_path / event_only

        elif drilling_depth == 3:
            # Create missing folder structure: sportType_X/stadiumName/categoryName/eventName.
            # Use incremental index to avoid conflicts with existing folders.
            parent_dir = parent_path_obj.parent
            sport_folder_path = parent_dir / f'sportType_{self.sport_folder_index}'

            while (sport_folder_path / 'stadiumName' / 'categoryName').exists():
                self.sport_folder_index += 1
                sport_folder_path = parent_dir / f'sportType_{self.sport_folder_index}'

            new_folder_path = sport_folder_path / 'stadiumName' / 'categoryName'
            new_folder_path.mkdir(parents=True, exist_ok=True)
            new_event_path = new_folder_path / event_only

        else:
            return parent_path

        return str(new_event_path)

    def is_event(self, event_name_set_test: str, test_path: str) -> bool:
        """
        Check if the input path is an EVENT folder based on pattern matching.

        Args:
            event_name_set_test: Pattern to match (e.g., "E##_##_##_##_##_##__")
            test_path: Path to test

        Returns:
            True if path matches event pattern, False otherwise
        """
        split_path = os.path.basename(test_path)

        if len(split_path) < len(event_name_set_test):
            return False

        match_count = 0
        digits = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9'}

        # Compare pattern character by character.
        # '#' in pattern matches any digit in the path.
        for x in range(len(event_name_set_test)):
            if event_name_set_test[x] == split_path[x]:
                match_count += 1
            elif event_name_set_test[x] == '#' and split_path[x] in digits:
                match_count += 1
            else:
                break

        # Require at least 20 matching characters to consider it an event.
        # This threshold prevents false matches with similar folder names.
        return match_count >= 20

    def duplicate_and_modify_json_files(
        self,
        json_file_path_set_test: str,
        folder_set_list: List[str],
        folder_frame_list: List[str],
        frame_name_list: List[str],
        json_folder_list: List[str],
        json_file_list: List[str],
        event_with_set_path_list: List[str]
    ) -> None:
        """
        Duplicate and modify JSON files with localized paths.

        Args:
            json_file_path_set_test: Base path for test sets
            folder_set_list: List of set folder paths
            folder_frame_list: List of frame folder paths
            frame_name_list: List of frame names
            json_folder_list: List of JSON folder paths
            json_file_list: List of JSON file paths
            event_with_set_path_list: List of event paths
        """
        total_files = len(json_file_list)
        logger.info(f"Processing {total_files} JSON file(s)")

        for i, json_file_path in enumerate(json_file_list):
            if not os.path.exists(json_file_path):
                logger.warning(f"File {json_file_path} does not exist! Skipping.")
                continue

            try:
                with open(json_file_path, 'r', encoding='utf-8') as json_file:
                    json_data = json_file.read()

                # Extract event and set names from folder paths.
                split_string = folder_frame_list[i].split('/')
                event_name = os.path.basename(event_with_set_path_list[i])
                set_name = os.path.basename(folder_set_list[i])

                # Build old path pattern (Events/eventName/setName) and replace with new path.
                # This localizes paths so FreeDView can find files in the test directory structure.
                old_event_path = os.path.join(split_string[0], 'Events', event_name, set_name)
                old_event_path = old_event_path.replace('\\', '/')

                new_event_path = os.path.join(event_with_set_path_list[i], set_name)
                new_event_path = new_event_path.replace('\\', '/')

                # Replace all occurrences of old path with new path in JSON content.
                modified_data = json_data.replace(old_event_path, new_event_path)

                # Write localized JSON file as testMe.json for FreeDView to use.
                json_file_dup = os.path.join(json_folder_list[i], 'testMe.json')
                try:
                    with open(json_file_dup, 'w', encoding='utf-8') as new_json_file:
                        new_json_file.write(modified_data)
                    logger.debug(f"Created localized JSON: {json_file_dup}")
                except Exception as write_error:
                    logger.error(
                        f"Failed to write localized JSON file '{json_file_dup}': {write_error}"
                    )
                    continue

            except Exception as e:
                logger.error(f"Error processing {json_file_path}: {e}", exc_info=True)
                continue

        if event_with_set_path_list:
            logger.info(f"Last processed event: {event_with_set_path_list[-1]}")

        logger.info("========================= Done JsonLocalizer ============================")


def run_json_localizer() -> None:
    """Run JSON localizer as standalone script."""
    project_path = os.path.dirname(__file__)
    ini_path = os.path.join(project_path, 'freeDView_tester.ini')

    json_localizer = JsonLocalizer()
    json_localizer.do_it(ini_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="JSON localizer")
    parser.add_argument(
        "-sa",
                        action="store_true",
                        dest="standalone",
        help="run script as stand alone"
    )

    args = parser.parse_args()
    if args.standalone:
        logger.info("Running JSON localizer as stand alone process.")
        run_json_localizer()
