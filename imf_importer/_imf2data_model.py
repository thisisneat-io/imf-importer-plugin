from datetime import datetime
from pathlib import Path

from cognite.client import data_modeling as dm
from rdflib import Graph
from typing_extensions import Self

from cognite.neat.core._constants import get_default_prefixes_and_namespaces
from cognite.neat.core._data_model._shared import ImportedDataModel
from cognite.neat.core._data_model.importers._base import BaseImporter
from cognite.neat.core._data_model.models._base_verified import RoleTypes
from cognite.neat.core._data_model.models.conceptual import (
    UnverifiedConceptualDataModel,
)
from cognite.neat.core._data_model.models.data_types import AnyURI
from cognite.neat.core._data_model.models.entities import UnknownEntity
from cognite.neat.core._issues import IssueList, MultiValueError
from cognite.neat.core._issues.errors import FileReadError
from cognite.neat.core._issues.errors._general import NeatValueError

from ._parsing import (
    parse_concepts,
    parse_properties,
)

DEFAULT_NON_EXISTING_NODE_TYPE = AnyURI()
DEFAULT_IMF_DATA_MODEL_ID = ("imf_space", "IMFDataModel", "v1")

class IMFImporter(BaseImporter[UnverifiedConceptualDataModel]):
    """Convert IMF Types provided as SHACL shapes to unverified data model."""

    def __init__(
        self,
        issue_list: IssueList,
        graph: Graph,
        data_model_id: dm.DataModelId | tuple[str, str, str],
        non_existing_node_type: UnknownEntity | AnyURI,
        language: str,
    ) -> None:
        self.issue_list = issue_list
        self.graph = graph
        self.data_model_id = dm.DataModelId.load(data_model_id)
        if self.data_model_id.version is None:
            raise NeatValueError("Version is required when setting a Data Model ID")

        self.non_existing_node_type = non_existing_node_type
        self.language = language

    @property
    def description(self) -> str:
        return f"IMF Types importer as unverified conceptual data model"

    @classmethod
    def from_file(
        cls,
        filepath: Path,
        language: str,
        data_model_id: (dm.DataModelId | tuple[str, str, str]) = DEFAULT_IMF_DATA_MODEL_ID,
        non_existing_node_type: UnknownEntity | AnyURI = DEFAULT_NON_EXISTING_NODE_TYPE,
    ) -> Self:
        issue_list = IssueList(title=f"{cls.__name__} issues")

        graph = Graph()
        try:
            graph.parse(filepath)
        except Exception as e:
            issue_list.append(FileReadError(filepath, str(e)))

        # bind key namespaces
        for prefix, namespace in get_default_prefixes_and_namespaces().items():
            graph.bind(prefix, namespace)

        return cls(
            issue_list,
            graph,
            data_model_id=data_model_id,
            non_existing_node_type=non_existing_node_type,
            language=language,
        )

    def to_data_model(
        self,
    ) -> ImportedDataModel[UnverifiedConceptualDataModel]:
        """
        Creates `ImportedDataModel` object from the data for target role.
        """
        if self.issue_list.has_errors:
            # In case there were errors during the import, the to_data_model method will return None
            self.issue_list.trigger_warnings()
            raise MultiValueError(self.issue_list.errors)

        data_model_dict = self._to_data_model_components()
        data_model = UnverifiedConceptualDataModel.load(data_model_dict)

        self.issue_list.trigger_warnings()

        return ImportedDataModel(data_model, {})

    def _to_data_model_components(
        self,
    ) -> dict:
        concepts, issue_list = parse_concepts(self.graph, self.language, self.issue_list)
        self.issue_list = issue_list
        properties, issue_list = parse_properties(self.graph, self.language, self.issue_list)
        self.issue_list = issue_list

        components = {
            "Metadata": self._metadata,
            "Concepts": list(concepts.values()) if concepts else [],
            "Properties": list(properties.values()) if properties else [],
        }

        return components

    @property
    def _metadata(self) -> dict:
        return {
            "role": RoleTypes.information,
            "space": self.data_model_id.space,
            "external_id": self.data_model_id.external_id,
            "version": self.data_model_id.version,
            "created": datetime.now().replace(microsecond=0),
            "updated": datetime.now().replace(microsecond=0),
            "name": None,
            "description": f"Data model imported using {type(self).__name__}",
            "creator": "Neat",
        }