"""
This is an example app for performing document query retrieval.  It exposes two basic endpoints:
- a `documents` endpoint for CRUD operations on documents.  This is where you can upload
    documents to the database for later retrieval.  Those documents can be text, chats, chunked PDFs, etc.

- a `retrieval` endpoint for performing query retrieval.  This endpoint takes a query and returns
    a list of documents that are relevant to the query.  The documents are ranked by relevance.
    This endpoint returns an HTML page with the results.

This app is built on top of the aimbase library, which is a library for building
AI microservices.  It is built on top of FastAPI, SQLAlchemy, and Minio.  It is
designed to be a lightweight, easy-to-use library for building AI microservices
that can be deployed anywhere (on-prem, cloud, etc.).  It is particularly 
useful for building AI microservices with use on proprietary data, as it
provides a simple way to store data in a database and models in your own Minio
object store.  

This app is also built on top of the instarest library, which is a library for
building RESTful APIs.  It is built on top of FastAPI and SQLAlchemy.  It is
designed to be a lightweight, easy-to-use library for building RESTful APIs.
"""
## ************ ENV VAR INIT BEFORE IMPORTS ************ ##
# Make sure to set ENVIRONMENT, ENV_VAR_FOLDER, and SECRETS in your environment,
# outside of any .env file.  This is to ensure that the correct environment
# variables are loaded before the app is initialized.
# Default values are: ENVIRONMENT=local, ENV_VAR_FOLDER=./env_vars, SECRETS=False if not set here
import os

os.environ["ENVIRONMENT"] = "local"
os.environ["ENV_VAR_FOLDER"] = os.path.join(
    os.path.abspath(os.path.dirname(__file__)), "env_vars"
)
os.environ["SECRETS"] = "True" # must be true to use OpenAI API key locally
## ************ ENV VAR INIT BEFORE IMPORTS ************ ##

from hybrid_rerank_retrieval import (
    DocumentModel,
    CRUDDocument,
    RetrievalService,
    all_mini_service,
    marco_service,
    QueryRetrievalRouterBase,
    OpenAIRetrieveSummarizeService,
)

# TODO: import to __init__.py for aimbase and update imports here
from aimbase.initializer import AimbaseInitializer
from aimbase.dependencies import get_minio
from instarest import AppBase, DeclarativeBase, SchemaBase, Initializer, RESTRouter

Initializer(DeclarativeBase).execute()
AimbaseInitializer().execute()

# built pydantic data transfer schemas automagically
document_crud_schemas = SchemaBase(DocumentModel)

# build db service automagically
document_crud = CRUDDocument(DocumentModel)

## ************ DEV INITIALIZATION ONLY (if desired to simulate
#  no internet connection) ************ ##
all_mini_service.dev_init()
marco_service.dev_init()
## ************ DEV INITIALIZATION ONLY ************ ##

# build document REST router automagically
document_router = RESTRouter(
    schema_base=document_crud_schemas,
    crud_base=document_crud,
    prefix="/documents",
    allow_delete=False,
)

# build retrieval service automagically
retrieval_service = RetrievalService(
    sentence_inference_service=all_mini_service,
    cross_encoder_inference_service=marco_service,
    document_crud=document_crud,
    s3=get_minio(),
)

# build retrieval router automagically
retrieval_router = QueryRetrievalRouterBase(
    retrieval_service=retrieval_service,
    prefix="/retrieval",
    description="Query Retrieval",
)

# build summary retrieval service automagically
summary_retrieval_service = OpenAIRetrieveSummarizeService(
    sentence_inference_service=all_mini_service,
    cross_encoder_inference_service=marco_service,
    document_crud=document_crud,
    s3=get_minio(),
)

# build summary retrieval router automagically
summary_retrieval_router = QueryRetrievalRouterBase(
    retrieval_service=summary_retrieval_service,
    prefix="/summary_retrieval",
    description="Query Retrieval and Summary",
)

# setup base up from routers
app_base = AppBase(
    crud_routers=[document_router, retrieval_router, summary_retrieval_router],
    app_name="Chainbase Hybrid Rerank Retrieval Example App",
)

# automagic and version app
auto_app = app_base.get_autowired_app()

# core underlying app
app = app_base.get_core_app()
