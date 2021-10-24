KEY_ATTRIBUTE = 'Name'


import requests
import re
import logging
import json


class Insight:
    def __init__(self, jira_url, login, password):
        if re.match("^.*://", jira_url):
            self.jira_url = jira_url.rstrip("/")
        else:
            self.jira_url = "http://{}".format(jira_url.rstrip("/"))
        self.insight_api_url = f"{jira_url}/rest/insight/1.0"
        self._schemaslist = None
        self.headers = {"Accept": "application/json", "Authorization": "Basic"}
        self.auth = (login, password)
        self.session = requests.Session()
        self.object_schemas = {}

    def __str__(self):
        return f"Insight: {self.jira_url}"

    @property
    def schemaslist(self):
        if self._schemaslist is None:
            self._schemaslist = self.get_schemas()
        return self._schemaslist

    def get_schemas(self):
        api_path = "/objectschema/list"
        logging.info("Загружаю объект схемы")
        object_schemas_json_request = self.do_api_request(api_path)
        result = object_schemas_json_request.get("objectschemas", {})
        logging.info(f"Найдено {len(result)} схем")
        return result

    def do_api_request(self, path, method="get", json=None, params=None):
        if method == "get":
            request = requests.get(
                self.insight_api_url + path,
                headers=self.headers, auth=self.auth, params=params)
            request.raise_for_status()
            return request.json()
        if method == "post":
            request = requests.post(
                self.insight_api_url + path,
                headers=self.headers, auth=self.auth, json=json, params=params
            )
            request.raise_for_status()
            return request.json()
        if method == "put":
            request = requests.put(
                self.insight_api_url + path,
                headers=self.headers, auth=self.auth, json=json, params=params
            )
            request.raise_for_status()
            return request.json()
        if method == "head":
            request = requests.head(
                self.insight_api_url + path,
                headers=self.headers, auth=self.auth, params=params
            )
            request.raise_for_status()
            return request.json()
        raise NotImplementedError


class InsightSchema:
    def __init__(self, insight, schemaname):
        self.insight = insight
        self.schema = [
            i for i in insight.schemaslist if i['name'] == schemaname][0]
        self.name = self.schema.get("name", None)
        self.id = self.schema.get("id", None)
        self.key = self.schema.get("objectSchemaKey", None)
        self.description = self.schema.get("description", None)
        self._object_types = None
        self._object_type_attributes = None
        self.insight.object_schemas[self.id] = self

    def __str__(self):
        return f"InsightObjectSchema: {self.name} ({self.key})"

    @property
    def object_types(self):
        if self._object_types is None:
            self._object_types = self.get_object_types()
        return self._object_types

    def get_object_types(self):
        object_types_json = self.insight.do_api_request(
            f"/objectschema/{self.id}/objecttypes/flat"
        )
        object_types = {}
        for object_type in object_types_json:
            object_types[object_type["id"]] = InsightObjectType(
                self.insight, object_type["id"], object_type
            )
        return object_types

    @property
    def object_type_attributes(self):
        if self._object_type_attributes is None:
            self._object_type_attributes = self.get_object_type_attributes()
        return self._object_type_attributes

    def get_object_type_attributes(self):
        object_type_attributes_json = self.insight.do_api_request(
            f"/objectschema/{self.id}/attributes"
        )
        object_type_attributes = {}
        for object_type_attribute_json in object_type_attributes_json:
            object_type_attributes[
                object_type_attribute_json["id"]
            ] = InsightObjectTypeAttribute(self, object_type_attribute_json)
        return object_type_attributes

    def object_exists(self, object_id):
        return (
            self.insight.do_api_request(
                f"/object/{object_id}", "head").status_code
            == 200
        )

    def search_iql(self, iql=None):
        api_path = "/iql/objects"
        params = {
            "objectSchemaId": self.id,
            "resultPerPage": 10000,
            "includeTypeAttributes": "true",
        }
        if iql is not None:
            params["iql"] = iql
        search_request = self.insight.do_api_request(api_path, params=params)
        search_results = search_request
        objects_json: list = search_results["objectEntries"]
        if not objects_json:
            raise StopIteration

        if search_results["pageSize"] > 1:
            for page_number in range(2, search_results["pageSize"] + 1):
                params["page"] = page_number
                logging.info(
                    f'Reading page {page_number}'
                    f'of {search_results["pageSize"]}'
                )
                page = self.insight.do_api_request(api_path, params=params)
                objects_json += page["objectEntries"]
        result = {}
        for json_object in objects_json:
            object_to_add = InsightObject(
                self.insight, json_object["id"], json_object)

            result[object_to_add.id] = object_to_add
            # yield  object_to_add
        return result

    def get_object_type(self, object_type):
        return [type for type in self.object_types.values() if type.name == object_type][0]

class InsightObjectType:
    def __init__(self, insight, object_type_id, object_type_json=None):
        self.insight = insight
        self.id = object_type_id
        logging.info(f"Загружаю Insight тип объекта с ID {self.id}")
        if not object_type_json:
            object_type_json = self.insight.do_api_request(
                f"/objecttype/{self.id}")
        self.name = object_type_json.get("name", None)
        self.object_schema_id = object_type_json.get("objectSchemaId", None)
        self.schema = [
            schema for schema in self.insight.object_schemas.items()][0][1]
        self._object_type_attributes = None
        self._objects = None

    def __str__(self):
        return f"InsightObjectType: {self.name}"

    def create_object(self, attributes: dict):
        attributes_json = []
        for attribute_id, value in attributes.items():
            entry = {
                "objectTypeAttributeId": attribute_id,
                "objectAttributeValues": [{"value": value}],
            }
            attributes_json.append(entry)
        request_body = {"objectTypeId": self.id, "attributes": attributes_json}
        response = self.insight.do_api_request(
            "/object/create", method="post", json=request_body
        )
        object_id = response["id"]
        created_object = InsightObject(self.insight, object_id)
        self._objects = None
        return created_object

    @property
    def objects(self):
        if self._objects is None:
            self._objects = self.get_objects()
        return self._objects

    def get_objects(self):
        iql = f'objectType = "{self.name}"'
        logging.info(f"Ищем все объекты в разделе - {self.name}")
        return self.schema.search_iql(iql)

    @property
    def object_type_attributes(self):
        if self._object_type_attributes is None:
            self._object_type_attributes = self.get_object_type_attributes()
        return self._object_type_attributes

    def get_object_type_attributes(self):
        object_type_attributes_json = self.insight.do_api_request(
            f"/objecttype/{self.id}/attributes"
        )
        object_type_attributes = {}
        for object_type_attribute_json in object_type_attributes_json:
            object_type_attributes[
                object_type_attribute_json["id"]
            ] = InsightObjectTypeAttribute(self, object_type_attribute_json)
        return object_type_attributes

    def get_id_object_type_attribute(self, name):
        check = [
            key for key, value in self.object_type_attributes.items() if value.name == name
        ]
        if check:
            return check[0]

    def get_object(self, name):
        check = [
            object for object in self.objects.values() if object.name == name
        ]
        if check:
            return check[0]


class InsightObjectTypeAttribute:
    def __init__(self, object_schema, object_type_attribute_json):
        self.insight = object_schema.insight
        self.object_schema = object_schema

        self.id = object_type_attribute_json["id"]
        self.name = object_type_attribute_json["name"]
        self.description = object_type_attribute_json.get("description", None)

        self.ATTRIBUTE_TYPES = {
            0: {
                0: "Text",
                1: "Integer",
                2: "Boolean",
                3: "Double",
                4: "Date",
                5: "Time",
                6: "Date Time",
                7: "URL",
                8: "Email",
                9: "Textarea",
                10: "Select",
                11: "IP Address",
            },
            1: "Object",
            2: "User",
            3: "Confluence",
            4: "Group",
            5: "Version",
            6: "Project",
            7: "Status",
        }

        attribute_type_id = object_type_attribute_json["type"]
        default_type_id = object_type_attribute_json.get(
            "defaultType", {}).get(
            "id", None
        )
        if attribute_type_id == 0:
            self.attribute_type = self.ATTRIBUTE_TYPES[0][default_type_id]
        else:
            self.attribute_type = self.ATTRIBUTE_TYPES[attribute_type_id]

        if self.attribute_type == "Object":
            self.referenceObjectTypeId  = object_type_attribute_json[
                'referenceObjectTypeId']

    def __str__(self):
        return f"InsightObjectTypeAttribute: {self.name}"


class InsightObject:
    def __init__(self, insight, object_id, object_json=None):
        self.insight = insight
        self.id = object_id
        self.object_json = object_json
        if not self.object_json:
            self.object_json = self.insight.do_api_request(
                f"/object/{self.id}")
        self.name = self.object_json["label"]
        self.object_schema = self.insight.object_schemas[
            self.object_json["objectType"]["objectSchemaId"]
        ]
        self.attributes = {}
        for attribute_json in self.object_json["attributes"]:
            attribute_object = InsightObjectAttribute(
                self,
                attribute_json["objectTypeAttributeId"],
                attribute_json["objectAttributeValues"],
            )
            self.attributes[attribute_object.name] = attribute_object

    def update_object(self, attributes: dict):
        attributes_json = []
        for attribute_id, value in attributes.items():
            if isinstance(value, list):
                value_list = [
                    {"value": value_list_item} for value_list_item in value]
            else:
                value_list = [{"value": value}]
            entry = {
                "objectTypeAttributeId": attribute_id,
                "objectAttributeValues": value_list,
            }
            attributes_json.append(entry)
        request_body = {
            "objectTypeId": self.object_json["objectType"]["id"],
            "attributes": attributes_json,
        }
        response = self.insight.do_api_request(
            "/object/{}".format(self.id), method="put", json=request_body
        )
        return response

    def get_jira_issues(self):
        self.JIRA_issues = self.insight.do_api_request(
                f"/object/{self.id}/jiraissues")

    def __str__(self):
        return f"InsightObject: {self.name}"


class InsightObjectAttribute:
    def __init__(self, insight_object, attribute_id, values_json=None):
        self.insight_object = insight_object
        self.id = attribute_id
        self.object_type_attribute = (
            self.insight_object.object_schema.object_type_attributes[
                self.id
                ]
        )
        self.name = self.object_type_attribute.name
        self.values_json = values_json

    @property
    def value(self):
        if self.values_json is None:
            self.values_json = (
                self.insight_object.object_schema.insight.do_api_request(
                    f"/objectattribute/{self.id}")
                )

        if not self.values_json:
            return None

        if self.object_type_attribute.attribute_type in [
                "User", "Object", "Select"
                ]:
            value = []
            for value_json in self.values_json:
                if self.object_type_attribute.attribute_type in [
                        "User", "Select"]:
                    value.append(value_json.get("value", None))
                    continue
                if self.object_type_attribute.attribute_type == "Object":
                    insight_object = InsightObject(
                        self.insight_object.insight,
                        value_json["referencedObject"]["id"],
                    )
                    value.append(insight_object)
                    continue
            return value
        else:
            value_json = self.values_json[0]
            if self.object_type_attribute.attribute_type in [
                "Text",
                "URL",
                "Email",
                "Textarea",
                "Date",
                "Date Time",
            ]:
                return value_json.get("value", None)
            if self.object_type_attribute.attribute_type == "Status":
                return value_json.get("status", None)
            if self.object_type_attribute.attribute_type == "Integer":
                return int(value_json.get("value", None))
            if self.object_type_attribute.attribute_type == "Double":
                return float(value_json.get("value", None))
            if self.object_type_attribute.attribute_type == "Boolean":
                return value_json.get("value", "false") == "true"

    def __str__(self):
        return f"InsightObjectAttribute: {self.name}, Value: {self.value}"

class Mixer:
    def __init__(self, datasource, target):
        if not isinstance(datasource, DataSource):
            raise ValueError (f'Incorect value {datasource}')
        if not isinstance(target, InsightSchema):
            raise ValueError (f'Incorect value {target}')
        self.datasource = datasource
        self.target = target
        self.schema = datasource.object_type.schema
        self.object_type = datasource.object_type
        self.object_type_attributes = datasource.object_type.object_type_attributes.items()
        self.update_objects = {}
        self.create_objects = {}
        self.object_types = {}
        self._unique_src_attrs = set(
            [attribute for record in datasource.source for attribute in record])
        self.attributes_id = {attr_name: [
            value.id for id, value 
            in self.object_type_attributes
            if value.name == attr_name][0] for attr_name
            in self._unique_src_attrs}
        self.references_attributes = {
            value.name: value.referenceObjectTypeId for _, value in self.object_type_attributes
            if hasattr(value, 'referenceObjectTypeId')
        }

    def __str__(self):
        return f"Mixer: {self.datasource} с {self.target}"

    def get_schema_object_type_attributes(self, object_type):
        return object_type.object_type_attributes.items()
            # self.datasource.object_type.object_type_attributes.items()

    def get_existing_names(self, objects='update'):
        # Имена объектов в схеме:
        schema_objects = set([object.name for object  in self.datasource.object_type.objects.values()])
        # Имена Объектов в исходнике:
        source_objects = set([
        value for record in self.datasource.source for attribute, value in record.items()
        if attribute.lower() == 'name'
        ])
        if objects=='update':
            return source_objects.intersection(schema_objects)
        if objects == 'cretae':
            return source_objects.difference(schema_objects)
        if objects =='disable':
            return schema_objects.difference(source_objects)

    def get_schema_object_attribute(self, id_object_type, object_name, attribute='objectKey'):
        # Функция для поиска атрибута, по умолчанию ищет objectKey. Можно искать id по имени.
        objects = self.target.object_types[id_object_type].objects
        check = [
        object.object_json[attribute]
        for object in objects.values() if object.name == object_name]
        if check:
            return check[0]

    def make_dicts_for_update_schema_objects(self):
        names_objects_for_update = self.get_existing_names()
        result = {}
        for name in names_objects_for_update:
            # Ищем id объекта
            id = self.get_schema_object_attribute(self.object_type.id, name, 'id')
            result[id] = {}
            for attr_name, attr_value in self.datasource.objects[name].items():
                attribute_id = self.attributes_id[attr_name]
                if attr_name in self.references_attributes:
                    reference_id = self.references_attributes[attr_name]
                    reference_obj_type = self.schema.object_types[reference_id]
                    if not isinstance(attr_value, list):
                        if reference_obj_type.get_object(attr_value) is None:
                            name_id = reference_obj_type.get_id_object_type_attribute('Name')
                            reference_obj_type.create_object({name_id: attr_value})
                            continue
                        else:
                            value = self.get_schema_object_attribute(reference_id, attr_value)
                    else:
                        value = []
                        for object in attr_value:
                            if reference_obj_type.get_object(object) is None:
                                name_id = reference_obj_type.get_id_object_type_attribute('Name')
                                reference_obj_type.create_object({name_id: attr_value})
                                continue
                            else:
                                obj_key = self.get_schema_object_attribute(reference_id, object)
                                value.append(obj_key)
                else:
                    value = attr_value
                result[id][attribute_id]=value
        self.update_objects.update(result)
        return result

# TODO: Удалить дублирование схожего кода в функциях
    def make_dicts_for_create_schema_objects(self):
        names_objects_for_update = self.get_existing_names('create')
        result = {}
        for name in names_objects_for_update:
            # result[id] = {}
            for attr_name, attr_value in self.datasource.objects[name].items():
                attribute_id = self.attributes_id[attr_name]
                if attr_name in self.references_attributes:
                    reference_id = self.references_attributes[attr_name]
                    reference_obj_type = self.schema.object_types[reference_id]
                    if not isinstance(attr_value, list):
                        if reference_obj_type.get_object(attr_value) is None:
                            name_id = reference_obj_type.get_id_object_type_attribute('KEY_ATTRIBUTE')
                            self.reference_obj_type.create_object({name_id: attr_value})
                            continue
                        else:
                            value = self.get_schema_object_attribute(reference_id, attr_value)
                    else:
                        value = []
                        for object in attr_value:
                            if reference_obj_type.get_object(object) is None:
                                name_id = reference_obj_type.get_id_object_type_attribute('KEY_ATTRIBUTE')
                                self.reference_obj_type.create_object({name_id: attr_value})
                                continue
                            else:
                                obj_key = self.get_schema_object_attribute(reference_id, object)
                                value.append(obj_key)
                else:
                    value = attr_value
                result[attribute_id]=value
        self.update_objects.update(result)
        return result


class DataSource:
    def __init__(
        self, source: list, object_type: InsightObjectType, key=KEY_ATTRIBUTE
        ):
        self.source = source
        self.object_type = object_type
        self.objects = {}
        for object in source:
            self.objects[object[key]] = object

    def __str__(self):
        return f"DataSource: {self.source}"

if __name__ == '__main__':
    print('Script Done')
