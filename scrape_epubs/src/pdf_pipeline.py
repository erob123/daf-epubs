import os
import requests
import traceback
from codecs import decode
from unstructured.partition.pdf import partition_pdf as unstructured_partition_pdf
from unstructured.cleaners.core import clean, clean_ordered_bullets, clean_prefix
from unstructured.documents.elements import Title
from unstructured.chunking.title import chunk_by_title
from aimbase.db.vector import SourceModel, DocumentModel, AllMiniVectorStore
from aimbase.crud.vector import CRUDSource
from aimbase.crud.sentence_transformers_vector import (
    CRUDSentenceTransformersVectorStore,
)
from aimbase.services.sentence_transformers_inference import (
    SentenceTransformersInferenceService,
)
from aimbase.dependencies import get_minio
from aimbase.crud.base import CRUDBaseAIModel
from aimbase.db.base import BaseAIModel
from instarest import get_db, SchemaBase

# Create a cache/docs directory if it doesn't exist
os.makedirs("cache/docs", exist_ok=True)

def download_and_partition_pdf(pdf_url):
    # Define the local path where you want to save the PDF file
    local_pdf_path = os.path.join("cache/docs", os.path.basename(pdf_url))

    # Set the maximum number of retry attempts
    max_retries = 5

    # Set the timeout for each retry (20 seconds)
    timeout_seconds = 20

    for attempt in range(max_retries):
        try:
            response = requests.get(pdf_url, timeout=timeout_seconds)

            if response.status_code == 200:
                with open(local_pdf_path, "wb") as pdf_file:
                    pdf_file.write(response.content)
                break  # Break the loop if the request is successful
            else:
                print(f"Failed to download PDF from {pdf_url} (Attempt {attempt + 1}/{max_retries})")
        except requests.exceptions.RequestException as e:
            # Handle connection or timeout errors
            print(f"An error occurred during the request (Attempt {attempt + 1}/{max_retries}): {e}")

    # If all retries fail
    if attempt == max_retries - 1:
        print(f"Max retries reached. Could not download PDF from {pdf_url}")
        return []

    chunks = pdf_pipeline(local_pdf_path)

    # Delete the downloaded PDF file when done
    os.remove(local_pdf_path)

    return chunks


def clean_text(text: str) -> str:
    text = clean(
        text,
        extra_whitespace=True,
        dashes=True,
        bullets=True,
        trailing_punctuation=True,
        lowercase=True,
    )

    try:
        if len(text) > 0:
            text = clean_ordered_bullets(text)

        if len(text) > 0:
            text = clean_prefix(text, r"afh 10 222(.+)", ignore_case=True)

        if len(text) > 0:
            text = clean_prefix(text, r"(\d+)", ignore_case=True)

        if len(text) > 0:
            text = clean(text, extra_whitespace=True)
    except Exception as e:
        print("An exception occurred:", e)
        traceback.print_exc()

    text = text.replace("\x00", "")

    return text


def pdf_pipeline(local_pdf_path):
    # Use unstructured.partition.pdf to partition the PDF document
    elements = unstructured_partition_pdf(
        local_pdf_path,
    )
    for element in elements:
        element.apply(clean_text)

    elements = [x for x in elements if x.text != ""]

    chunks = chunk_by_title(elements)

    return chunks

def save_json_chunk_data_to_db(json_source_list):
    # Iterate through the list of dictionaries and process each document
    crud_source_model = CRUDSource(SourceModel)
    crud_vector_store = CRUDSentenceTransformersVectorStore(AllMiniVectorStore)
    db = next(get_db())

    document_schemas = SchemaBase(
        DocumentModel, optional_fields=["source"]
    )  # defined by sqlalchemy relationship, just need id
    DocumentCreateSchema = document_schemas.EntityCreate

    embedding_service = SentenceTransformersInferenceService(
        model_name="all-MiniLM-L6-v2",
        db=db,
        crud=CRUDBaseAIModel(BaseAIModel),
        s3=get_minio(),
        prioritize_internet_download=False,
    )

    embedding_service.initialize()

    try:
        for source_info in json_source_list:
            document_url = source_info.get("DocumentUrl")
            if document_url:
                chunks = download_and_partition_pdf(document_url)

            if document_url is None or len(chunks) == 0:
                continue

            # get the source id from db
            title = decode(
                f"{source_info.get('Number', '')}: {source_info.get('Title', '')}",
                "unicode_escape",
            )

            source_obj_list = crud_source_model.get_by_source_metadata(
                db, titles=[title]
            )
            if len(source_obj_list) == 1:
                source_obj_id = source_obj_list[0].id
            else:
                print(
                    f"Warning: {len(source_obj_list)} sources found in DB for {title}"
                )

            # prep the chunks to embed and save in db / vector store
            document_schema_list = [
                DocumentCreateSchema(page_content=chunk.text, source_id=source_obj_id)
                for chunk in chunks
            ]

            # save
            crud_vector_store.create_and_calculate_multi(
                db,
                docs_in_list=document_schema_list,
                embedding_service=embedding_service,
            )

            print(f"{title} completed successfully")

    finally:
        db.close()

    # TODO: delete all embeddings and docs by source id (to filter sources by date to see if any updated)
        # store log
        # save page numbers and metadata for unstructured object
        # save published date for source and if parsed successfully
        # move from json load to scrape load
        # cloud run persistent compute
        # load params first not on demand