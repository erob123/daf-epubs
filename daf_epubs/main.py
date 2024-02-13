import os

os.environ["ENVIRONMENT"] = "production"
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAI
from langchain.chains import LLMMathChain
from langchain.agents import initialize_agent, Tool, AgentType
from langchain.tools import BaseTool
import chainlit as cl
from chainlit.sync import run_sync
from typing import TYPE_CHECKING
from chainlit.server import app as chainlit_app
from api.base import auto_app
from pydantic import BaseModel
from datetime import datetime
from instarest import get_db

from aimbase.services.cross_encoder_inference import CrossEncoderInferenceService
from aimbase.services.sentence_transformers_inference import (
    SentenceTransformersInferenceService,
)

from aimbase.crud.base import CRUDBaseAIModel
from aimbase.db.base import BaseAIModel
from aimbase.dependencies import get_minio

from aimbase.crud.sentence_transformers_vector import (
    CRUDSentenceTransformersVectorStore,
)
from aimbase.crud.vector import CRUDSource
from aimbase.db.vector import AllMiniVectorStore, SourceModel, DocumentModel
from fastapi.encoders import jsonable_encoder

if TYPE_CHECKING:
    from langchain.agents.agent import AgentExecutor

# loads the GOOGLE_API_KEY env var for local dev
if not os.environ.get('GOOGLE_API_KEY'):
    try:
        load_dotenv(
            dotenv_path=os.path.join(os.environ["ENV_VAR_FOLDER"], "secrets-extra.env")
        )
    except KeyError as e:
        load_dotenv(dotenv_path=os.path.join("./env_vars", "secrets-extra.env"))

# if not deploying api separately behind a proxy (e.g., here, attached to chainlit),
# mount under /api prefix before version, i.e., /api/v1
# if behind a proxy, use the env var DOCS_UI_ROOT_PATH from instarest instead
chainlit_app.mount("/api", auto_app)


class HumanInputChainlit(BaseTool):
    """Tool that adds the capability to ask user for input."""

    name = "human"
    description = (
        "You can ask a human for guidance when you think you "
        "got stuck or you are not sure what to do next. "
        "The input should be a query for the human."
    )

    def _run(
        self,
        query: str,
        run_manager=None,
    ) -> str:
        """Use the Human input tool."""

        res = run_sync(cl.AskUserMessage(content=query).send())
        return res["content"]

    async def _arun(
        self,
        query: str,
        run_manager=None,
    ) -> str:
        """Use the Human input tool."""
        res = await cl.AskUserMessage(content=query).send()
        return res["content"]


class EpubsRetrievalChainlit(BaseTool):
    """Tool that adds the capability search DAF Epubs."""

    name = "EpubsRetrieval"
    description = (
        "Useful for when you need to retrieve source information "
        "from an Air Force (AF or USAF), Space Force (SF or USSF), or Department of the Air Force (DAF) "
        "official document (ePubs), such as policy, Air Force flying rules, "
        "Space Force satellite operator regulations, etc."
    )

    # Handle kwargs and have an auto response if query not defined
    def _run(self, query: str = None, run_manager=None, **kwargs) -> str:
        if query is None or type(query) is not str:
            not_allowed = " ,".join(kwargs.keys())
            statement = """
            {
              "action": "EpubsRetrieval",
              "action_input": {
                "query": "<define query here>"
              }
            }

            any other keys are not allowed 
            """

            return (
                "These keys are not allowed: "
                + not_allowed
                + "\nFormat like this instead: \n"
                + statement
            )

        ranked_neighbors = self.retrieve(query)
        cl.user_session.set("ranked_neighbors", ranked_neighbors)
        return jsonable_encoder(
            [item.document.page_content + "\n" for item in ranked_neighbors]
        )

    # Handle kwargs and have an auto response if query not defined
    async def _arun(self, query: str = None, run_manager=None, **kwargs) -> str:
        if query is None or type(query) is not str:
            not_allowed = " ,".join(kwargs.keys())
            statement = """
            {
              "action": "EpubsRetrieval",
              "action_input": {
                "query": "<define query here>"
              }
            }

            any other keys are not allowed 
            """

            return (
                "These keys are not allowed: "
                + not_allowed
                + "\nFormat like this instead: \n"
                + statement
            )

        ranked_neighbors = self.retrieve(query)
        cl.user_session.set("ranked_neighbors", ranked_neighbors)
        return jsonable_encoder(
            [item.document.page_content + "\n" for item in ranked_neighbors]
        )

    def retrieve(self, query: str):
        class KnnInput(BaseModel):
            query: str
            k: int = 10  # number of nearest neighbors to return
            titles: list[str] | None = None
            downloaded_datetime_start: datetime | None = None
            downloaded_datetime_end: datetime | None = None
            similarity_measure: str = "max_inner_product"

        class RankedNeighbor(BaseModel):
            document: object
            score: float

        request: KnnInput = KnnInput(query=query)

        # kNN SEARCH and rerank
        db = next(get_db())
        try:
            embedding_service = SentenceTransformersInferenceService(
                model_name="all-MiniLM-L6-v2",
                db=db,
                crud=CRUDBaseAIModel(BaseAIModel),
                s3=get_minio(),
                prioritize_internet_download=False,
            )

            embedding_service.initialize()

            cross_encoder_service = CrossEncoderInferenceService(
                model_name="cross-encoder/ms-marco-TinyBERT-L-6",
                db=db,
                crud=CRUDBaseAIModel(BaseAIModel),
                s3=get_minio(),
                prioritize_internet_download=False,
            )

            cross_encoder_service.initialize()

            # Calculate embedding for the query
            query_embedding = embedding_service.model.encode(request.query)

            crud_base = CRUDSentenceTransformersVectorStore(AllMiniVectorStore)
            # Perform kNN search
            retrieved_embeddings_db = (
                crud_base.get_by_source_metadata_and_nearest_neighbors(
                    db,
                    titles=request.titles,
                    downloaded_datetime_start=request.downloaded_datetime_start,
                    downloaded_datetime_end=request.downloaded_datetime_end,
                    vector_query=query_embedding,
                    k=request.k,
                    similarity_measure=request.similarity_measure,
                )
            )

            # Step 1: If no documents are retrieved, return empty list
            if len(retrieved_embeddings_db) == 0:
                return []

            # Step 2: Score the documents via cross encoder
            cross_encoder_inputs = [
                [request.query, emb.document.page_content]
                for emb in retrieved_embeddings_db
            ]

            scores = cross_encoder_service.model.predict(
                cross_encoder_inputs
            ).tolist()  # need to convert numpy objs to list to be json serializable

            # Step 3: Sort the scores in decreasing order
            unsorted_neighbors = []
            for emb, score in zip(retrieved_embeddings_db, scores):

                # access the source to force loading data via sqlalchemy
                _ = emb.document.source

                # append data to list
                unsorted_neighbors.append(
                    RankedNeighbor(document=emb.document, score=score)
                )

            reranked_neighbors = sorted(
                unsorted_neighbors, key=lambda item: item.score, reverse=True
            )
            return reranked_neighbors
        except Exception as e:
            raise e
        finally:
            db.close()


def build_agent():
    # math_llm = ChatGoogleGenerativeAI(model="gemini-pro", temperature=0)
    agent_llm = GoogleGenerativeAI(model="gemini-pro", temperature=0)
    # llm_math_chain = LLMMathChain.from_llm(llm=math_llm, verbose=True)

    tools = [
        # HumanInputChainlit(),
        EpubsRetrievalChainlit()
        # Tool(
        #     name="Calculator",
        #     func=llm_math_chain.run,
        #     description="useful for when you need to answer questions about math",
        #     coroutine=llm_math_chain.arun,
        # ),
    ]
    agent = initialize_agent(
        tools, agent_llm, agent=AgentType.CHAT_ZERO_SHOT_REACT_DESCRIPTION, verbose=True
    )

    return agent


@cl.on_chat_start
def start():
    cl.user_session.set("agent", build_agent())


@cl.on_message
async def main(message: cl.Message):
    agent = cl.user_session.get("agent")  # type: AgentExecutor
    answer = await agent.arun(
        message.content, callbacks=[cl.AsyncLangchainCallbackHandler()]
    )

    text_elements = []  # type: List[cl.Text]
    ranked_neighbors = cl.user_session.get("ranked_neighbors")
    if ranked_neighbors:

        # class SourceModel(DeclarativeBase):
        #     title = Column(String())
        #     description = Column(String())
        #     downloaded_datetime = Column(DateTime)
        #     private_url = Column(String())
        #     public_url = Column(String())
        #     embedding = Column(Vector(384))

        # class DocumentModel(DeclarativeBase):
        #     page_content = Column(String())
        #     source_id = Column(UUID, ForeignKey("sourcemodel.id"), nullable=True)
        #     source = relationship("SourceModel")

        for ranked_neighbor in ranked_neighbors:
            source_name = ranked_neighbor.document.source.title
            # Create the text element referenced in the message
            content = (
                "Relevance Score: "
                + str(ranked_neighbor.score)
                + "\n\nURL: "
                + ranked_neighbor.document.source.public_url
                + "\n\nContent: "
                + ranked_neighbor.document.page_content
            )
            text_elements.append(cl.Text(content=content, name=source_name))
        source_names = ["\n- " + text_el.name for text_el in text_elements]

        if source_names:
            answer += f"\nSources: {''.join(source_names)}"
        else:
            answer += "\nNo sources found"

    await cl.Message(content=answer, elements=text_elements).send()


# use chainlit and langchain for this with the underlying tool to pull from daf-epubs
# attach prefix_api to the chainlit fastapi app and adjust dockerfile
# smaller cross encoder
# add "secrets-extra.env" to readme
# add page numbers and prompt to build source links with page numbers
# limit knn k value and overall rate limit
# ploty cluster explorer?
