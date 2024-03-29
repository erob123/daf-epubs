# Use the official Python Alpine image as the base image
FROM python:3.11.7

# Set environment variables for non-secret configuration
ENV APP_HOME /app
ENV POETRY_HOME /poetry
ENV PATH $POETRY_HOME/bin:$PATH
ENV XDG_CACHE_HOME=$APP_HOME/.cache 
ENV POETRY_CACHE_DIR=$XDG_CACHE_HOME/pypoetry

# Install Poetry
RUN pip install poetry
RUN mkdir $POETRY_HOME

# Create a non-root user and group
RUN groupadd myappgroup && useradd -G myappgroup myappuser

# Set the working directory to /app and change ownership to the non-root user
WORKDIR $APP_HOME
RUN chown -R myappuser:myappgroup $APP_HOME

# Copy only the dependencies file to the container
COPY pyproject.toml poetry.lock* $APP_HOME/

# Install project dependencies as the non-root user
USER myappuser
RUN poetry install --no-root

# Switch back to the root user to copy the rest of the application code
USER root

# Copy the rest of the application code to the container
COPY . .

# Default environment variable
ENV ENVIRONMENT=production

# Expose the port the application runs on
EXPOSE 8000

# Command to run the application as the non-root user
USER myappuser

# use one of the below to run depending on configuration (api only vs. chatbot interface and api)
# CMD ["poetry", "run", "uvicorn", "main:prefix_app", "--host", "0.0.0.0", "--port", "8000"]
CMD ["poetry", "run", "chainlit", "run", "main.py", "--host", "0.0.0.0", "--port", "8000"]
