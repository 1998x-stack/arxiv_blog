import sys,os
sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/' + '..'))

import unittest
import os
import pickle
import sqlite3
import zlib
from unittest.mock import patch, MagicMock, mock_open
from io import BytesIO
from util.compressed_sqlite_dict_manager import AtomicFileWriter, CompressedSqliteDictManager, FeatureStore  # Adjust import based on file structure


DATA_DIR = os.path.join(
    os.path.abspath(os.path.dirname(__file__) + '/' + '..'), 'data'
    )

# Test for AtomicFileWriter
class TestAtomicFileWriter(unittest.TestCase):

    @patch('os.rename')
    @patch('tempfile.mkstemp')
    @patch('builtins.open', new_callable=mock_open)
    def test_safe_pickle_dump(self, mock_open_file, mock_mkstemp, mock_rename):
        """
        Test the safe_pickle_dump method to ensure that data is atomically written to a file.
        """
        # Mock the tempfile creation and os.rename behavior
        mock_mkstemp.return_value = (1234, f'{DATA_DIR}/temp_file')

        # Initialize AtomicFileWriter
        atomic_writer = AtomicFileWriter('test_dir')
        data_to_pickle = {'key': 'value'}

        # Run the safe_pickle_dump method
        atomic_writer.safe_pickle_dump(data_to_pickle, 'final_file')

        # Verify the file open call and os.rename call
        mock_open_file.assert_called_once_with(f'{DATA_DIR}/temp_file', 'wb')
        mock_rename.assert_called_once_with(f'{DATA_DIR}/temp_file', 'final_file')

        # Check that the pickle dump happened with the correct data
        mock_open_file().write.assert_called()  # Ensure something was written

# Test for CompressedSqliteDictManager
class TestCompressedSqliteDictManager(unittest.TestCase):

    @patch('sqlitedict.SqliteDict')
    def test_get_compressed_db(self, mock_sqlitedict):
        """
        Test if the CompressedSqliteDictManager correctly creates a compressed database instance.
        """
        # Initialize the manager and retrieve the DB
        db_manager = CompressedSqliteDictManager('test_db_file')
        compressed_db = db_manager.get_compressed_db('test_table', flag='w')

        # Verify the sqlite dict call with the correct arguments
        mock_sqlitedict.assert_called_once_with('test_db_file', tablename='test_table', flag='w', autocommit=True)

# Test for FeatureStore
class TestFeatureStore(unittest.TestCase):

    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists', return_value=True)
    def test_load_features(self, mock_exists, mock_open_file):
        """
        Test the load_features method to ensure it correctly loads features from a pickle file.
        """
        # Mock the pickle load behavior
        mock_open_file.return_value = BytesIO(pickle.dumps({'key': 'value'}))

        # Initialize the FeatureStore
        feature_store = FeatureStore('test_features_file')

        # Run load_features
        loaded_features = feature_store.load_features()

        # Check that os.path.exists was called and the file was opened
        mock_exists.assert_called_once_with('test_features_file')
        mock_open_file.assert_called_once_with('test_features_file', 'rb')

        # Verify that the loaded data is correct
        self.assertEqual(loaded_features, {'key': 'value'})

    @patch('os.path.exists', return_value=False)
    def test_load_features_file_not_found(self, mock_exists):
        """
        Test the load_features method when the feature file does not exist.
        It should raise a FileNotFoundError.
        """
        # Initialize the FeatureStore
        feature_store = FeatureStore('test_features_file')

        # Expect FileNotFoundError
        with self.assertRaises(FileNotFoundError):
            feature_store.load_features()

    @patch('builtins.open', new_callable=mock_open)
    @patch('tempfile.mkstemp', return_value=(1234, f'{DATA_DIR}/temp_file'))
    def test_save_features(self, mock_mkstemp, mock_open_file):
        """
        Test the save_features method to ensure it correctly saves features to a pickle file.
        """
        # Initialize FeatureStore and the data to be saved
        feature_store = FeatureStore('test_features_file')
        data_to_save = {'key': 'value'}

        # Run save_features
        feature_store.save_features(data_to_save)

        # Verify that the file was opened in write mode (mock_open)
        mock_open_file.assert_called_once_with(f'{DATA_DIR}/temp_file', 'wb')

        # Check that pickle dump was called to serialize the data
        mock_open_file().write.assert_called()  # Ensure something was written

if __name__ == '__main__':
    unittest.main()