"""
Unit tests for renderCompare module.
"""
import unittest
import numpy as np
import cv2
import tempfile
import os
from pathlib import Path

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from renderCompare import mean_squared_error


class TestRenderCompare(unittest.TestCase):
    """Test cases for renderCompare module."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary test images
        self.temp_dir = tempfile.mkdtemp()
        self.test_image1_path = os.path.join(self.temp_dir, 'test1.jpg')
        self.test_image2_path = os.path.join(self.temp_dir, 'test2.jpg')
        
        # Create simple test images (100x100, grayscale)
        test_image1 = np.ones((100, 100), dtype=np.uint8) * 128
        test_image2 = np.ones((100, 100), dtype=np.uint8) * 130
        
        cv2.imwrite(self.test_image1_path, test_image1)
        cv2.imwrite(self.test_image2_path, test_image2)

    def tearDown(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_mean_squared_error_identical_images(self):
        """Test MSE with identical images."""
        image = np.ones((100, 100), dtype=np.uint8) * 128
        mse = mean_squared_error(image, image)
        self.assertEqual(mse, 0.0, "MSE should be 0 for identical images")

    def test_mean_squared_error_different_images(self):
        """Test MSE with different images."""
        image1 = np.ones((100, 100), dtype=np.uint8) * 128
        image2 = np.ones((100, 100), dtype=np.uint8) * 130
        mse = mean_squared_error(image1, image2)
        self.assertGreater(mse, 0.0, "MSE should be greater than 0 for different images")

    def test_mean_squared_error_different_sizes(self):
        """Test MSE raises error for different sized images."""
        image1 = np.ones((100, 100), dtype=np.uint8)
        image2 = np.ones((200, 200), dtype=np.uint8)
        # Note: This will raise an error, but the function doesn't check for it
        # We could add validation to the function
        with self.assertRaises((ValueError, IndexError)):
            mean_squared_error(image1, image2)

    def test_mean_squared_error_float_conversion(self):
        """Test MSE handles float conversion correctly."""
        image1 = np.ones((10, 10), dtype=np.uint8) * 100
        image2 = np.ones((10, 10), dtype=np.uint8) * 110
        mse = mean_squared_error(image1, image2)
        self.assertIsInstance(mse, float)
        self.assertGreater(mse, 0)


if __name__ == '__main__':
    unittest.main()

