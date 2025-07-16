from typing import cast, Any

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.plugins.sparql import prepareQuery
from rdflib.query import ResultRow

from cognite.neat.core._issues._base import IssueList
from cognite.neat.core._issues.errors._general import NeatValueError
from cognite.neat.core._issues.warnings._resources import (
    ResourceRedefinedWarning,
    ResourceRetrievalWarning,
)

from ._compliance import (
    make_concept_compliant,
    make_property_compliant
)

CONCEPTS_QUERY = """
    SELECT ?concept ?name ?description ?implements ?instance_source
    WHERE {{
        VALUES ?implements {{ imf:Block imf:Terminal }}
        ?concept rdfs:subClassOf ?implements .

        OPTIONAL {{?concept rdfs:label|skos:prefLabel ?name }}.
        OPTIONAL {{?concept rdfs:comment|skos:definition ?description}}.

        BIND(?concept AS ?instance_source)

        # FILTERS
        FILTER (!isBlank(?concept))
        FILTER (!bound(?name) || LANG(?name) = "" || LANGMATCHES(LANG(?name), "{language}"))
        FILTER (!bound(?description) || LANG(?description) = "" || LANGMATCHES(LANG(?description), "{language}"))
    }}"""

PROPERTIES_QUERY = """
    SELECT ?concept ?property_ ?name ?description ?value_type ?instance_source ?min_count ?max_count ?default
    WHERE
    {{
        VALUES ?subClass {{ imf:Block imf:Terminal }}
        ?concept rdfs:subClassOf ?subClass ;
            sh:property ?propertyShape .
            ?propertyShape sh:path ?property_ .

        OPTIONAL {{ ?property_ skos:prefLabel ?name . }}
        OPTIONAL {{ ?property_ skos:definition ?description . }}
        OPTIONAL {{ ?property_ rdfs:range ?range . }}

        OPTIONAL {{ ?propertyShape sh:minCount ?min_count . }}
        OPTIONAL {{ ?propertyShape sh:maxCount ?max_count . }}
        OPTIONAL {{ ?propertyShape sh:nodeKind ?nodeKind . }}
        OPTIONAL {{ ?propertyShape sh:hasValue ?default . }}

        BIND(?property_ AS ?instance_source)
        BIND(IF(BOUND(?range), ?range, xsd:string) AS ?value_type)
        BIND(IF(BOUND(?default) && !BOUND(?min_count), 1, 0) AS ?min_count)
        BIND(IF(BOUND(?default) && !BOUND(?max_count), 1, ?undefined) AS ?max_count)

        FILTER(?property_ != imf:hasTerminal && ?property_ != imf:hasPart)

        FILTER (!isBlank(?property_))
        FILTER (!bound(?concept) || !isBlank(?concept))
        FILTER (!bound(?name) || LANG(?name) = "" || LANGMATCHES(LANG(?name), "{language}"))
        FILTER (!bound(?description) || LANG(?description) = "" || LANGMATCHES(LANG(?description), "{language}"))
    }}"""


def parse_concepts(graph: Graph, language: str, issue_list: IssueList) -> tuple[dict, IssueList]:
    """Parse concepts from graph

    Args:
        graph: Graph containing concept definitions
        language: Language to use for parsing, by default "en"

    Returns:
        Dataframe containing imf types
    """

    concepts: dict[str, dict] = {}

    query = prepareQuery(CONCEPTS_QUERY.format(language=language), initNs={k: v for k, v in graph.namespaces()})
    expected_keys = [str(v) for v in query.algebra._vars]

    for raw in graph.query(query):

        res: dict = _convert_rdflib_content(cast(ResultRow, raw).asdict())
        res = {key: res.get(key, None) for key in expected_keys}

        compliant_res = make_concept_compliant(res)
        concept_id = compliant_res["concept"]

        # Safeguarding against incomplete semantic definitions
        if compliant_res["implements"] and isinstance(compliant_res["implements"], BNode):
            issue_list.append(
                ResourceRetrievalWarning(
                    concept_id,
                    "implements",
                    error=("Unable to determine concept that is being implemented"),
                )
            )
            continue

        if concept_id not in concepts:
            concepts[concept_id] = compliant_res
        else:
            # Handling implements
            if concepts[concept_id]["implements"] and isinstance(concepts[concept_id]["implements"], list):
                if compliant_res["implements"] not in concepts[concept_id]["implements"]:
                    concepts[concept_id]["implements"].append(compliant_res["implements"])

            elif concepts[concept_id]["implements"] and isinstance(concepts[concept_id]["implements"], str):
                concepts[concept_id]["implements"] = [concepts[concept_id]["implements"]]

                if compliant_res["implements"] not in concepts[concept_id]["implements"]:
                    concepts[concept_id]["implements"].append(compliant_res["implements"])
            elif compliant_res["implements"]:
                concepts[concept_id]["implements"] = compliant_res["implements"]

            handle_meta("concept", concepts, concept_id, compliant_res, "name", issue_list)
            handle_meta("concept", concepts, concept_id, compliant_res, "description", issue_list)

    if not concepts:
        issue_list.append(NeatValueError("Unable to parse concepts"))

    return concepts, issue_list


def parse_properties(graph: Graph, language: str, issue_list: IssueList) -> tuple[dict, IssueList]:
    """Parse properties from graph

    Args:
        graph: Graph containing owl classes
        language: Language to use for parsing, by default "en"

    Returns:
        Dataframe containing owl classes
    """

    properties: dict[str, dict] = {}

    query = prepareQuery(PROPERTIES_QUERY.format(language=language), initNs={k: v for k, v in graph.namespaces()})
    expected_keys = [str(v) for v in query.algebra._vars]

    for raw in graph.query(query):
        res: dict = _convert_rdflib_content(cast(ResultRow, raw).asdict())
        res = {key: res.get(key, None) for key in expected_keys}

        converted_res = make_property_compliant(res)
        property_id = converted_res["property_"]

        # Safeguarding against incomplete semantic definitions
        if not converted_res["concept"] or isinstance(converted_res["concept"], BNode):
            issue_list.append(
                ResourceRetrievalWarning(
                    property_id,
                    "property",
                    error=("Unable to determine to what concept property is being defined"),
                )
            )
            continue

        # Safeguarding against incomplete semantic definitions
        if not converted_res["value_type"] or isinstance(converted_res["value_type"], BNode):
            issue_list.append(
                ResourceRetrievalWarning(
                    property_id,
                    "property",
                    error=("Unable to determine value type of property"),
                )
            )
            continue

        id_ = f"{converted_res['concept']}.{converted_res['property_']}"

        if id_ not in properties:
            properties[id_] = converted_res
            properties[id_]["value_type"] = [properties[id_]["value_type"]]
        else:
            handle_meta("property", properties, id_, converted_res, "name", issue_list)
            handle_meta(
                "property",
                properties,
                id_,
                converted_res,
                "description",
                issue_list,
            )

            # Handling multi-value types
            if converted_res["value_type"] not in properties[id_]["value_type"]:
                properties[id_]["value_type"].append(converted_res["value_type"])

    for prop in properties.values():
        prop["value_type"] = ", ".join(prop["value_type"])

    if not properties:
        issue_list.append(NeatValueError("Unable to parse properties"))

    return properties, issue_list

def handle_meta(
    resource_type: str,
    resources: dict[str, dict],
    resource_id: str,
    res: dict,
    feature: str,
    issue_list: IssueList,
) -> None:
    if not resources[resource_id][feature] and res[feature]:
        resources[resource_id][feature] = res[feature]

    # RAISE warning only if the feature is being redefined
    elif resources[resource_id][feature] and res[feature]:
        issue_list.append(
            ResourceRedefinedWarning(
                identifier=resource_id,
                resource_type=resource_type,
                feature=feature,
                current_value=resources[resource_id][feature],
                new_value=res[feature],
            )
        )

def _convert_rdflib_content(content: Literal | URIRef | dict | list) -> Any:
    if isinstance(content, Literal) or isinstance(content, URIRef):
        return content.toPython()
    elif isinstance(content, dict):
        return {key: _convert_rdflib_content(value) for key, value in content.items()}
    elif isinstance(content, list):
        return [_convert_rdflib_content(item) for item in content]
    else:
        return content