# Running Unit Tests

## Prerequisites
- Python 3.x
- Required packages: numpy, opencv-python, scikit-image

## Running Tests

### Run all tests:
```bash
python -m unittest discover tests
```

### Run specific test file:
```bash
python -m unittest tests.test_render_compare
python -m unittest tests.test_get_data_ini
python -m unittest tests.test_json_localizer
```

### Run with verbose output:
```bash
python -m unittest discover tests -v
```

## Test Structure

- `tests/test_render_compare.py` - Tests for image comparison functions
- `tests/test_get_data_ini.py` - Tests for INI file reading
- `tests/test_json_localizer.py` - Tests for JSON localization logic

## Adding New Tests

When adding new functionality, add corresponding tests in the `tests/` directory following the naming convention `test_<module_name>.py`.

## Multi-threading Support

The tool supports parallel processing via multi-threading in Phase 2 (rendering) and Phase 3 (comparison). The `max_workers` parameter controls the number of parallel threads (default: 4). This is an internal implementation detail and doesn't require changes to existing unit tests, as the classes maintain backward compatibility with default parameters.

