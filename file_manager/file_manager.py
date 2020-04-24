import gzip
import os

import xmltodict
from lxml import etree
import pyarrow.parquet as pq
import pandas as pd
import pyarrow as pa
import csv
import json


class FileIO:
    def __init__(self, file_path, dirname, operator_cls, *args, compression_format=None, buffering=100, mode='r', encoding=None, **kwargs):
        self.file_path = file_path
        self.dirname = dirname
        self.compression_format = compression_format
        self.buffering = buffering
        self.mode = mode
        self.encoding = encoding
        self.args = args
        self.kwargs = kwargs
        self.operator_cls = operator_cls
        self.file_handler = self.open()
        self.operator = self.get_operator()

    class Reader:
        def __init__(self, file_handler):
            self.file_handler = file_handler

        def read(self):
            while True:
                line = self.file_handler.readline()
                if not line:
                    raise StopIteration
                yield line

    class Writer:
        def __init__(self, file_handler):
            self.file_handler = file_handler

        def write(self, data):
            self.file_handler.write(data)

    def open(self):
        file_opener = FileManager.file_opener(self.file_path)

        if file_opener in FileManager.FILE_OPENERS_ACCEPTING_EXTERNAL_BUFFER_SIZE:
            return file_opener(self.file_path, mode=self.mode, buffering=self.buffering, encoding=self.encoding)

        return file_opener(self.file_path, mode=self.mode, encoding=self.encoding)

    def close(self):
        self.file_handler.close()

    def read(self):
        return self.operator.read()

    def write(self, data):
        return self.operator.write(data)

    def get_operator(self):
        return self.operator_cls(self.file_handler)


class XMLFileIO(FileIO):

    def __init__(self, file_path, dirname, operator_cls, split_tag, *args, compression_format=None, mode='r', **kwargs):
        self.split_tag = split_tag
        super().__init__(
            file_path, dirname, operator_cls, *args, compression_format=compression_format, mode=mode, **kwargs
        )

    class Reader:
        def __init__(self, file_handler, split_tag):
            self.file_handler = file_handler
            self.split_tag = split_tag

        def read(self):
            context = etree.iterparse(self.file_handler, tag=self.split_tag)

            for event, elem in context:
                xml_chunk_str = etree.tostring(elem)
                converted_dict = xmltodict.parse(xml_chunk_str, dict_constructor=dict)
                elem.clear()
                yield converted_dict

    def get_operator(self):
        return self.operator_cls(self.file_handler, self.split_tag)


class ParquetFileIO(FileIO):

    def __init__(self, file_path, dirname, operator_cls, *args, compression_format=None, mode='r', root_path=None, filesystem=None, partition_cols=[], **kwargs):
        self.root_path = root_path
        self.filesystem = filesystem
        self.root_path = dirname + '/' + self.root_path + '/' if not self.filesystem else self.root_path
        self.compression_format = compression_format
        self.partition_cols = partition_cols
        super().__init__(file_path, dirname, operator_cls, *args, compression_format=compression_format, mode=mode, **kwargs)

    class Writer:
        def __init__(self, file_path, buffer_capacity=10000, root_path=None, partition_cols=[], filesystem=None, **kwargs):
            self.file_path = file_path
            self.root_path = root_path
            self.partition_cols = partition_cols
            self.buffer_capacity = buffer_capacity
            self.buffer = list()
            self.kwargs = kwargs
            self.filesystem = filesystem

        def write(self, data):
            self.buffer.append(data)
            if len(self.buffer) == self.buffer_capacity:
                self.commit()

        def commit(self):
            buffer_df = pd.DataFrame(self.buffer)
            table = pa.Table.from_pandas(df=buffer_df, preserve_index=False)
            pq.write_to_dataset(table, root_path=self.root_path, partition_cols=self.partition_cols, filesystem=self.filesystem)
            self.buffer = []

    def open(self):
        pass

    def get_operator(self):
        return self.operator_cls(
            self.file_path, *self.args, root_path=self.root_path, partition_cols=self.partition_cols, filesystem=self.filesystem,
            **self.kwargs
        )

    def close(self):
        if self.mode.startswith('w') and self.operator.buffer:
            self.operator.commit()


class CSVFileIO(FileIO):

    class Reader:
        def __init__(self, file_handler):
            self.file_handler = file_handler

        def read(self):
            reader = csv.DictReader(self.file_handler)

            for row in reader:
                yield row


class JSONFileIO(FileIO):

    class Reader:
        def __init__(self, file_handler):
            self.file_handler = file_handler

        def read(self):
            while True:
                line = self.file_handler.readline()
                if not line:
                    raise StopIteration
                yield json.loads(line)


class FileManager:
    BUFFER_SIZE = 50

    SUPPORTED_FILE_EXTENSIONS = {
        "xml": XMLFileIO,
        "parq": ParquetFileIO,
        "csv": CSVFileIO,
        "json": JSONFileIO
    }

    SUPPORTED_FILE_COMPRESSION_FORMATS = {
        "gz": gzip.open

    }

    FILE_OPENERS_ACCEPTING_EXTERNAL_BUFFER_SIZE = [open]

    def __init__(self, filename, dirname='', *args, mode='r', **kwargs):
        self.dirname = dirname
        self.mode = mode
        self.filename = filename
        self.args = args
        self.kwargs = kwargs
        self.filepath = self.get_abs_filepath()

    def get_abs_filepath(self):
        return os.path.join(self.dirname, self.filename)

    def get_file_dir(self):
        return self.filepath.rsplit('/', 1)[0]

    def __enter__(self):
        if self.mode.startswith('w'):
            self.create_dir(self.get_file_dir())

        file_io_cls = self.file_io(self.filename)
        operator_cls = file_io_cls.Reader if self.mode.startswith('r') else file_io_cls.Writer
        self.file_io_obj = file_io_cls(
            self.filepath, self.dirname, operator_cls, *self.args, mode=self.mode, **self.kwargs
        )
        return self.file_io_obj

    @classmethod
    def file_io(cls, filename):
        file_extensions = filename.split('.')

        if len(file_extensions) > 2:
            return cls.SUPPORTED_FILE_EXTENSIONS.get(file_extensions[-2], FileIO)

        return cls.SUPPORTED_FILE_EXTENSIONS.get(file_extensions[-1], FileIO)

    @classmethod
    def file_opener(cls, filename):
        file_extensions = filename.split('.')

        if len(file_extensions) > 2:
            return cls.SUPPORTED_FILE_COMPRESSION_FORMATS[file_extensions[-1]]

        return open

    @staticmethod
    def create_dir(path):
        if not os.path.isdir(path):
            os.makedirs(path)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.file_io_obj.close()
