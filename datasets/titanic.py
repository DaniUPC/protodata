from protodata.serialization_ops import SerializeSettings
from protodata.reading_ops import DataSettings
from protodata.utils import create_dir
from protodata.data_ops import NumericColumn, split_data, feature_normalize, \
    map_feature_type, float64_feature, int64_feature

import tensorflow as tf
import numpy as np

import tarfile
import tempfile
import shutil
import os
import logging
from six.moves import urllib


DATA_FILE_NAME = 'titanic.dat'
DATA_URL = 'ftp://ftp.cs.toronto.edu/pub/neuron/delve/data/tarfiles/titanic.tar.gz'  # noqa
logger = logging.getLogger(__name__)


class TitanicSerialize(SerializeSettings):

    def __init__(self, data_path):
        """ See base class """
        super(TitanicSerialize, self).__init__(data_path)
        create_dir(data_path)
        # On-demand download if it does not exist
        if not is_downloaded(data_path):
            logger.info('Downloading Titanic dataset ...')
            download(DATA_URL, get_data_path(data_path))

    def read(self):
        self.data = np.loadtxt(get_data_path(self.data_path), dtype=int)
        self.features = self.data[:, :-1]
        self.labels = self.data[:, -1]

    def get_validation_indices(self, train_ratio, val_ratio):
        """ Separates data into training, validation and test and normalizes
        the columns by using z-scores """

        train, val, test = split_data(self.features.shape[0],
                                      train_ratio,
                                      val_ratio)

        # Store normalization info
        self.feature_norm = self._normalize_features(train, val)

        return train, val, test

    def _normalize_features(self, train_idx, val_idx):
        training = np.concatenate([train_idx, val_idx])
        mean_c, std_c, min_c, max_c = \
            feature_normalize(self.features[training, :])

        self.features = (self.features - mean_c) / std_c

        # Store normalization info
        return {'mean': mean_c, 'std': std_c, 'min': min_c, 'max_c': max_c}

    def get_options(self):
        options = {'feature_normalization': self.feature_norm}
        return options

    def define_columns(self):
        cols = []

        # Columns
        for i in range(self.features.shape[1]):
            current_col = NumericColumn(
                name=str(i), type=map_feature_type(np.dtype('float'))
            )
            cols.append(current_col)

        # Label
        cols.append(NumericColumn(
                name='class', type=map_feature_type(np.dtype('int'))
        ))

        return cols

    def build_examples(self, index):
        row = self.features[index, :]
        feature_dict = {}
        for i in range(self.features.shape[1]):
            feature_dict.update(
                {str(i): float64_feature(row[i])}
            )

        feature_dict.update({'class': int64_feature(int(self.labels[index]))})

        return [tf.train.Example(features=tf.train.Features(feature=feature_dict))]  # noqa


class TitanicSettings(DataSettings):

    def __init__(self, dataset_location, image_specs=None,
                 embedding_dimensions=32, quantizer=None):
        super(TitanicSettings, self).__init__(
            dataset_location=dataset_location,
            image_specs=image_specs,
            embedding_dimensions=embedding_dimensions,
            quantizer=quantizer)

    def tag(self):
        return 'titanic'

    def size_per_instance(self):
        return 0.5

    def target_class(self):
        return 'class'

    def _target_type(self):
        return tf.int32

    def _get_num_classes(self):
        return 2

    def select_wide_cols(self):
        return [v.to_column() for k, v in self.columns.items()]

    def select_deep_cols(self):
        return RuntimeError('No embeddings in this dataset')


def is_downloaded(folder):
    """ Returns whether data has been downloaded """
    return os.path.isfile(get_data_path(folder))


def get_data_path(folder):
    return os.path.join(folder, DATA_FILE_NAME)


def download(url, dst):
    """ Downloads the data file into the given path """
    # Download tar file into temp folder
    tmp_folder = tempfile.mkdtemp()
    gzip_path = os.path.join(tmp_folder, 'titanic.tar.gz')
    dst_path = os.path.join(tmp_folder, 'unzipped')
    urllib.request.urlretrieve(url, gzip_path)

    # Unzip file into tmp folder
    dst_path = os.path.join(tmp_folder, 'unzipped')
    with tarfile.open(gzip_path) as tar:
        tar.extractall(path=dst_path)

    # Copy dataset file into destination
    root_folder = os.path.join(dst_path, 'titanic')
    data_file = os.path.join(
        root_folder, os.path.join('Source', 'titanic.dat')
    )

    shutil.copyfile(data_file, dst)
    
    shutil.rmtree(tmp_folder)
