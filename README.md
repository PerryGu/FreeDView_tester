# FreeDView Tester

Automated testing and comparison tool for FreeDView renderer versions. This tool helps compare rendered outputs from different FreeDView versions to identify visual differences and regressions.

## TL;DR

-   **JSON Localization**: Automatically localizes JSON configuration files for rendering
-   **Multi-Version Rendering**: Renders image sequences using different FreeDView versions via subprocess integration
-   **Image Comparison**: Compares rendered outputs using MSE and SSIM metrics
-   **Visual Analysis**: Generates diff images and alpha masks for visual inspection
-   **Detailed Reports**: Creates XML reports with per-frame comparison data
-   **Progress Tracking**: Real-time progress indication for long operations
-   **External Process Management**: Integrates with FreeDView renderer with error handling
-   **Parallel Processing**: Multi-threaded rendering and comparison for improved performance

**Quick Start:**
```bash
pip install opencv-python numpy scikit-image
python src/main.py all
```

------------------------------------------------------------------------

## Overview

FreeDView Tester is a three-phase automated testing pipeline designed to identify visual differences between FreeDView renderer versions. The tool processes test sets, renders them using different FreeDView versions, and provides comprehensive comparison analysis.

It was originally developed to support the needs of my team at Intel, providing an automated solution for regression testing and version comparison of the FreeDView renderer.

The system follows a modular architecture: each phase is implemented as an independent module. The phases communicate through file-based data exchange, keeping the workflow efficient, stable, and easy to extend.

Phase 2 integrates with the FreeDView renderer executable using Python's `subprocess` module, demonstrating advanced process management capabilities including stdout/stderr capture, error handling, and return code validation.

This modular design allows each component to evolve independently and makes the suite maintainable and scalable.

------------------------------------------------------------------------

# Phase Breakdown (High-Level Responsibilities)

## Phase 1: JSON Localizer - Path Localization

The main module that localizes JSON configuration files for rendering.

### Features:

-   Scans test sets directory for `standAloneRender.json` files
-   Pattern-based matching for events and sets (supports `#` wildcards)
-   Creates localized `testMe.json` files with updated paths
-   Supports flexible directory structures (Event, SportType/Event, SportType/Stadium/Event, etc.)
-   Preserves all JSON structure while updating paths

------------------------------------------------------------------------

## Phase 2: FreeDView Runner - Rendering Execution

Executes FreeDView renderer on localized JSON files.

### Features:

-   Reads localized `testMe.json` files created by Phase 1
-   Executes FreeDView renderer as subprocess
-   Renders image sequences for multiple versions (original and test)
-   Processes frame ranges from JSON configuration
-   Renames output images to sequential format
-   Organizes output in structured directories

------------------------------------------------------------------------

## Phase 3: Render Compare - Image Comparison & Analysis

Compares rendered images between versions and generates reports.

### Features:

-   Compares image pairs from original and test versions
-   Calculates MSE (Mean Squared Error) and SSIM (Structural Similarity Index) metrics
-   Generates visual difference images with HOT colormap
-   Creates alpha mask images using Otsu thresholding
-   Generates XML reports with per-frame comparison data
-   Extracts metadata from directory structure

------------------------------------------------------------------------

## Architecture

The system follows a modular architecture:

- **Core Modules** (`src/main.py`, `src/jsonLocalizer.py`, `src/freeDViewRunner.py`, `src/renderCompare.py`): Independent phase implementations
  - Each phase can run independently or as part of the complete pipeline
  - File-based communication between phases
  - Consistent error handling and logging

- **Utilities** (`getDataIni.py`): Configuration file reading utility
  - INI file parsing with error handling
  - Backward compatibility support
  - Validation and logging

- **Shared Patterns**: Consistent code style, logging, error handling across all modules

### Data Flow

```
Configuration (INI file)
    ↓
JSON Localizer (Phase 1)
    ├── Scans testSets directory
    ├── Matches events/sets by pattern
    └── Creates localized testMe.json files
    ↓
FreeDView Runner (Phase 2)
    ├── Reads testMe.json files
    ├── Executes FreeDView renderer
    └── Generates rendered image sequences
    ↓
Render Compare (Phase 3)
    ├── Loads images from both versions
    ├── Calculates comparison metrics
    ├── Generates diff/alpha images
    └── Creates XML reports
```

## Performance

- **Progress Tracking**: Real-time progress indication for long operations
- **Error Resilience**: Continues processing when individual items fail
- **Logging**: Detailed logging with configurable verbosity levels
- **Validation**: Comprehensive input validation before processing

------------------------------------------------------------------------

# Architecture Diagram

                     ┌────────────────────────────────────┐
                     │            main.py                  │
                     │   (CLI Entry Point & Orchestration) │
                     └────────────────────────────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
         ┌──────────▼──────┐ ┌─────▼──────┐ ┌─────▼──────┐
         │  Phase 1:       │ │ Phase 2:   │ │ Phase 3:   │
         │  JSON Localizer  │ │ FreeDView  │ │ Render     │
         │                  │ │ Runner     │ │ Compare    │
         │  - Scans dirs    │ │            │ │            │
         │  - Matches       │ │ - Executes │ │ - Compares │
         │    patterns      │ │   FreeDView│ │   images   │
         │  - Creates       │ │ - Renders  │ │ - Generates│
         │    testMe.json   │ │   sequences│ │   reports  │
         └──────────────────┘ └────────────┘ └────────────┘
                    │              │              │
                    └──────────────┼──────────────┘
                                   │
                     ┌─────────────▼─────────────┐
                     │   getDataIni.py           │
                     │   (Configuration Reader)  │
                     └────────────────────────────┘

------------------------------------------------------------------------

## Project Structure

```markdown
📁 freeDView_tester/
│
├── 📁 src/                    # Source code
│   ├── 📄 __init__.py
│   ├── 📄 main.py            # Main CLI entry point and orchestration
│   ├── 📄 jsonLocalizer.py   # Phase 1: JSON file localization
│   ├── 📄 freeDViewRunner.py # Phase 2: FreeDView rendering execution
│   ├── 📄 renderCompare.py   # Phase 3: Image comparison and analysis
│   └── 📄 getDataIni.py      # INI configuration file reader utility
│
├── 📁 tests/                  # Unit tests
│   ├── 📄 README.md           # Testing documentation
│   ├── 📄 test_get_data_ini.py
│   ├── 📄 test_json_localizer.py
│   └── 📄 test_render_compare.py
│
├── 📄 freeDView_tester.ini    # Configuration file (paths, versions, patterns)
└── 📄 README.md               # This file
```

------------------------------------------------------------------------

## Installation

### Prerequisites

- Python 3.8 or higher
- FreeDView executable
- Test sets directory with JSON configuration files

### Setup Steps

1. **Clone or download the project:**
   ```bash
   git clone <repository-url>
   cd freeDView_tester
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   
   Or install manually:
   ```bash
   pip install opencv-python numpy scikit-image
   ```

3. **Configure the INI file:**
   - Edit `freeDView_tester.ini` with your paths and settings
   - See Configuration section for detailed parameter descriptions

4. **Verify FreeDView executable:**
   - Ensure FreeDView is accessible at the path specified in INI file
   - Verify executable permissions

5. **Verify test sets structure:**
   - Check that test sets directory contains `standAloneRender.json` files
   - Ensure directory structure matches expected patterns (see Configuration)

------------------------------------------------------------------------

## Usage

### Basic Workflow

**Run Complete Pipeline:**
```bash
python src/main.py all
```

**Run Individual Phases:**
```bash
# Phase 1: JSON Localizer
python src/main.py localize

# Phase 2: FreeDView Runner
python src/main.py render

# Phase 3: Render Compare
python src/main.py compare
```

**Custom INI File:**
```bash
python src/main.py all --ini path/to/custom.ini
```

**Multiple Version Comparisons (Multiple INI Files):**

To compare multiple version groups, create separate INI files for each comparison and run them sequentially:

```bash
# Create separate INI files for each version comparison
# freeDView_tester_v1.ini - compares version1_VS_version2
# freeDView_tester_v2.ini - compares version3_VS_version4

# Run each comparison
python src/main.py all --ini freeDView_tester_v1.ini
python src/main.py all --ini freeDView_tester_v2.ini
```

Each INI file should contain one `freedviewVer` entry. The tool will process all JSON files found in `setTestPath` for each version comparison, running them in parallel using multi-threading.

**Verbose Logging:**
```bash
python src/main.py all --verbose
```

**UI Comparison Mode:**
```bash
python src/main.py compare-ui folder_frame_path freedview_path_tester freedview_path_orig freedview_name_orig freedview_name_tester
```

### Directory Structure

This section explains the directory structure at different stages of the pipeline.

#### Input Structure (testSets/)

The input directory contains test sets with JSON configuration files:

```
testSets/
└── SportType/                    # Optional: e.g., NFL, Football
    └── EventName/                # e.g., E17_01_07_16_01_25_LIVE_05
        └── SetName/              # e.g., S170123190428
            └── F####/            # Frame folder (actually a SEQUENCE), e.g., F0224
                └── Render/
                    └── Json/
                        └── standAloneRender.json    # Contains startFrame, endFrame
```

#### Output Structure (testSets_results/)

Results are written to `testSets_results/` directory. The structure evolves as the pipeline progresses:

**After Phase 2 (Rendering):**

```
testSets_results/
└── SportType/                    # e.g., NFL
    └── EventName/                # e.g., E17_01_07_16_01_25_LIVE_05
        └── SetName/              # e.g., S170123190428
            └── F####/            # e.g., F0224
                └── freedview_version1_VS_version2/    # Comparison folder
                    ├── freedview_version1/           # Original version images
                    │   ├── 0135.jpg                  ← Frame 135
                    │   ├── 0136.jpg                  ← Frame 136
                    │   ├── 0137.jpg                  ← Frame 137
                    │   └── ...                       ← Sequential frames
                    └── freedview_version2/           # Test version images
                        ├── 0135.jpg                  ← Frame 135
                        ├── 0136.jpg                  ← Frame 136
                        └── ...                       ← Sequential frames
```

**Example path:** `testSets_results/NFL/E17_01_07_16_01_25_LIVE_05/S170123190428/F0224/freedview_1.3.2.0_1.0.0.3_VS_freedview_1.3.5.0_1.0.0.0/`

**After Phase 3 (Comparison):**

```
testSets_results/
└── SportType/                    # e.g., NFL
    └── EventName/                # e.g., E17_01_07_16_01_25_LIVE_05
        └── SetName/              # e.g., S170123190428
            └── F####/            # e.g., F0224
                └── freedview_version1_VS_version2/    # Comparison folder
                    ├── freedview_version1/           # Rendered images (original version)
                    ├── freedview_version2/           # Rendered images (test version)
                    └── results/
                        ├── compareResult.xml          # ONE XML with data for ALL frames
                        ├── diff_images/              # Visual difference images (ONE per frame)
                        │   ├── 0135.jpg              ← Diff image for frame 135
                        │   ├── 0136.jpg              ← Diff image for frame 136
                        │   ├── 0137.jpg              ← Diff image for frame 137
                        │   └── ...                   ← One diff image per frame
                        └── alpha_images/             # Alpha mask images (ONE per frame)
                            ├── 0135.png              ← Alpha mask for frame 135
                            ├── 0136.png              ← Alpha mask for frame 136
                            ├── 0137.png              ← Alpha mask for frame 137
                            └── ...                   ← One alpha mask per frame
```

**Note:** Frame numbers use 4-digit format with leading zeros (e.g., `0135.jpg`, `0136.jpg`). The actual frame numbers depend on the `startFrame` and `endFrame` values in the `standAloneRender.json` file.

### XML Report Structure

The `compareResult.xml` file contains aggregated comparison data for all frames in a sequence. Here's an example structure:

```xml
<?xml version="1.0" ?>
<root>
    <sourcePath>D:/testSets_results/EventName/SetName/F1234/freedview_ver/version_orig</sourcePath>
    <testPath>D:/testSets_results/EventName/SetName/F1234/freedview_ver/version_test</testPath>
    <diffPath>D:/testSets_results/EventName/SetName/F1234/results/diff_images</diffPath>
    <alphaPath>D:/testSets_results/EventName/SetName/F1234/results/alpha_images</alphaPath>
    <origFreeDView>freedview_1.2.1.6_1.0.0.5</origFreeDView>
    <testFreedview>freedview_1.2.1.6_1.0.0.8</testFreedview>
    <eventName>E##_##_##_##_##_##__</eventName>
    <sportType>Football</sportType>
    <stadiumName>StadiumA</stadiumName>
    <categoryName>Category1</categoryName>
    <startFrame>0100</startFrame>
    <endFrame>0150</endFrame>
    <minVal>0.985</minVal>
    <maxVal>0.999</maxVal>
    <frames>
        <frame>
            <frameIndex>100</frameIndex>
            <value>0.998</value>
        </frame>
        <frame>
            <frameIndex>101</frameIndex>
            <value>0.997</value>
        </frame>
        <frame>
            <frameIndex>102</frameIndex>
            <value>0.996</value>
        </frame>
        <!-- ... more frames ... -->
        <frame>
            <frameIndex>149</frameIndex>
            <value>0.986</value>
        </frame>
        <frame>
            <frameIndex>150</frameIndex>
            <value>0.985</value>
        </frame>
    </frames>
</root>
```

**XML File Notes:**
- **One XML file per frame folder** 
- Contains metadata: paths, version names, event/sport/stadium info, frame range
- Contains per-frame SSIM values in the `<frames>` section
- `minVal` and `maxVal` represent the minimum and maximum SSIM values across all frames
- Each `<frame>` element contains `frameIndex` and `value` (SSIM score)

------------------------------------------------------------------------

# Dependencies

### Python Packages

-   **opencv-python** (cv2): Image processing and comparison
-   **numpy**: Numerical operations for image analysis
-   **scikit-image**: SSIM (Structural Similarity Index) calculation
-   **configparser**: Built-in Python module for INI file parsing (included in Python standard library)

### Installation Command

```bash
pip install opencv-python numpy scikit-image
```

------------------------------------------------------------------------

# Requirements

-   **Python**: 3.8 or later
-   **FreeDView**: Executable must be available at path specified in INI file
-   **Test Sets**: Directory structure with JSON configuration files matching the patterns specified in INI file

------------------------------------------------------------------------

# Configuration

The tool is configured via `freeDView_tester.ini`:

```ini
[freeDView_tester]
setTestPath = D:\freeDView_tester\testSets
freedviewPath = D:\freeDView_tester\freedviewVer
freedviewVer = freedview_1.2.1.6_1.0.0.5_VS_freedview_1.2.1.6_1.0.0.8
eventName = E##_##_##_##_##_##__
setName = S####
```

### Configuration Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `setTestPath` | Base path to test sets directory | `D:\freeDView_tester\testSets` |
| `freedviewPath` | Path to FreeDView version directories | `D:\freeDView_tester\freedviewVer` |
| `freedviewVer` | Version string format: `version1_VS_version2` | `freedview_1.2.1.6_1.0.0.5_VS_freedview_1.2.1.6_1.0.0.8` |
| `eventName` | Pattern to match event folders (`#` = digit) | `E##_##_##_##_##_##__` |
| `setName` | Pattern to match set folders (`#` = digit) | `S####` |

### Setup Steps

1.  Edit `freeDView_tester.ini` with your paths and settings
2.  Ensure FreeDView executable is accessible at the specified path
3.  Verify test sets directory structure matches expected patterns
4.  Run a test to verify configuration: `python src/main.py localize --verbose`

### Multiple Version Comparisons

For comparing multiple version groups, create separate INI files for each comparison:

**Example - Multiple INI Files:**

```ini
# freeDView_tester_v1.ini
[freeDView_tester]
setTestPath = D:\freeDView_tester\testSets
freedviewPath = D:\freeDView_tester\freedviewVer
freedviewVer = freedview_1.2.1.6_1.0.0.5_VS_freedview_1.2.1.6_1.0.0.8
eventName = E##_##_##_##_##_##__
setName = S####
```

```ini
# freeDView_tester_v2.ini
[freeDView_tester]
setTestPath = D:\freeDView_tester\testSets
freedviewPath = D:\freeDView_tester\freedviewVer
freedviewVer = freedview_1.3.0.0_1.0.0.0_VS_freedview_1.3.5.0_1.0.0.0
eventName = E##_##_##_##_##_##__
setName = S####
```

**Run each comparison:**
```bash
python src/main.py all --ini freeDView_tester_v1.ini
python src/main.py all --ini freeDView_tester_v2.ini
```

**Benefits of multiple INI files:**
- **Clear separation**: Each file = one comparison task
- **Easy testing**: Test individual comparisons independently
- **Simple management**: Add/remove version groups easily
- **Better error isolation**: Errors are clearly associated with specific configurations
- **Professional practice**: Follows standard configuration management patterns

**Note:** Each INI file should contain one `freedviewVer` entry. The tool will process all JSON files found in `setTestPath` for each version comparison, running them in parallel using multi-threading.

------------------------------------------------------------------------

## Troubleshooting

### INI File Issues

**Issue: "INI file not found"**
- Verify `freeDView_tester.ini` exists in the project directory
- Or use `--ini` flag to specify custom path

**Issue: "Failed to read required configuration"**
- Check INI file format and ensure all required parameters are present
- Verify file encoding is correct (UTF-8)

### FreeDView Issues

**Issue: "FreeDView executable not found"**
- Verify the `freedviewPath` in INI file points to the correct directory
- Ensure FreeDView versions are in the expected subdirectory structure

**Issue: "Error running FreeDView"**
- Check FreeDView executable permissions
- Verify JSON files are valid and paths are correct
- Check FreeDView logs for detailed error messages

### File and Path Issues

**Issue: "No JSON files found to render"**
- Check that `setTestPath` is correct
- Verify test sets contain `standAloneRender.json` files
- Ensure event/set name patterns match your directory structure

**Issue: "Failed to read output resolution"**
- Ensure `cameracontrol.ini` exists in `dynamicINIsBackup` folder
- Verify INI file contains `outputWidth` and `outputHeight` keys

**Issue: "Images have different dimensions"**
- Verify both FreeDView versions render at the same resolution
- Check camera control INI files for both versions

### Dependency Issues

**Issue: Import errors (skimage, cv2, etc.)**
- Install missing packages: `pip install opencv-python numpy scikit-image`
- Verify Python version is 3.8 or higher
- Check virtual environment if using one

### Performance Issues

- Use `--verbose` flag to see detailed progress
- Check log files for bottlenecks
- Verify disk space is available for output

------------------------------------------------------------------------

## Version

**Current Version**: 1.0.0  
**Python Compatibility**: 3.8+  
**Platform**: Windows (tested), Linux/Mac (should work)

## Status

Production-ready tool.  
Designed for automated FreeDView version comparison and regression testing.  
Features comprehensive error handling, logging, and progress tracking.

## Related Tools

A complementary C++/Qt UI application is available for visualizing and analyzing the comparison results generated by this tool. The UI tool provides an interactive interface for browsing diff images, alpha masks, and XML reports.

## License

**Copyright (c) [Year] - All Rights Reserved**

This software and associated documentation files (the "Software") are proprietary and confidential.

**RESTRICTIONS:**
- The Software may NOT be copied, reproduced, or distributed in any form
- The Software may NOT be used, modified, or reverse-engineered without explicit written permission
- The Software may NOT be shared with third parties

**NO WARRANTY:**
The Software is provided "AS IS" without warranty of any kind, express or implied.

All rights reserved. Unauthorized copying, use, or distribution of this Software is strictly prohibited.
