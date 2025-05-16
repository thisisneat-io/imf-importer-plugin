from pathlib import Path

from cognite.neat.core.plugins.data_model.importers import DataModelImporter
from ._imf2data_model import IMFImporter


__all__ = ["IMFDataModelImporter"]

class IMFDataModelImporter(DataModelImporter):
    def configure(self, source: str, *, language:str = "en") -> IMFImporter:
        """
        Extracts the rules from the IMF RDF file.

        Args:
            filepath (str): Path to the IMF RDF file.

        Returns:
            Configured IMFImporter instance.
        """

        return IMFImporter.from_file(filepath=Path(source), language=language)