from datetime import datetime
from codecs import decode
from aimbase.db.vector import SourceModel
from aimbase.crud.vector import CRUDSource 
from instarest import SchemaBase, get_db

source_model_schemas = SchemaBase(
    SourceModel,
    optional_fields=[
        "description",
        "downloaded_datetime",
        "private_url",
        "public_url",
        "embedding",
    ],
)

SourceCreateSchema = source_model_schemas.EntityCreate

crud_source_model = CRUDSource(SourceModel)

def map_json_to_model(json_data):
    # Concatenate Number and Title for the title field
    title = decode(
        f"{json_data.get('Number', '')}: {json_data.get('Title', '')}",
        "unicode_escape",
    )

    # Concatenate other fields into the description
    description_fields = ["PubID", "Prescribe", "LastAction", "ReplacementID",
                          "Format", "ProductType", "RescindOrg", "RescindDsnPhone",
                          "RescindCommPhone", "RescindLevel", "FormatLetter", "FormatClass"]
    description = ". ".join(f"{field}: {json_data.get(field, '')}" for field in description_fields)

    return SourceCreateSchema(
        title=title,
        description=description,
        downloaded_datetime=datetime.now(),
        private_url=json_data.get("DocumentPath", ""),
        public_url=json_data.get("DocumentUrl", "")
    )

def save_json_source_data_to_db(json_list):
    db = next(get_db())
    try:
        schema_objects = [map_json_to_model(json_data) for json_data in json_list]
        crud_source_model.create_all_using_id(db, obj_in_list=schema_objects)
    finally:
        db.close()