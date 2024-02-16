from parent_dir.inner_dir.class_dir import file_to_import_with_full_path
from . import file_to_import_with_relative_import


class MyFancyClassToImport:
    full_path_import = file_to_import_with_full_path.ATTRIBUTE_VALUE
    relative_path_import = file_to_import_with_relative_import.ATTRIBUTE_VALUE
    attribute = "Success!"
