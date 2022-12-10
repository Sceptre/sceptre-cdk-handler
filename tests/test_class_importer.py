from pathlib import Path
from unittest import TestCase

from sceptre.exceptions import SceptreException

from template_handler.class_importer import ClassImporter


class TestClassImporter(TestCase):
    def test_import_class__imports_class_from_referenced_file(self):
        filepath = Path(__file__).parent / 'assets' / 'file_to_import.py'
        class_name = "MyFancyClassToImport"
        importer = ClassImporter()
        result = importer.import_class(filepath, class_name)
        self.assertEqual(
            'Success!',
            result.attribute
        )

    def test_import_class__named_class_isnt_on_module__raises_sceptre_exception(self):
        filepath = Path(__file__).parent / 'assets' / 'file_to_import.py'
        importer = ClassImporter()
        with self.assertRaises(SceptreException):
            importer.import_class(filepath, "CantFindMe")
