from pathlib import Path

from cognite.neat.plugins.data_model.importers import DataModelImporterPlugin
from ._imf2data_model import IMFImporter


__all__ = ["IMFDataModelImporterPlugin"]


class IMFDataModelImporterPlugin(DataModelImporterPlugin):

    def configure(self, io: Path, *, language: str = "en") -> IMFImporter:
        """
        Configures the IMFImporter with the provided RDF file.

        Args:
            io (Path): Path to the IMF RDF file.

        Returns:
            Configured IMFImporter to be passed to the NeatSession for data model import.
        """

        return IMFImporter.from_file(filepath=io, language=language)
