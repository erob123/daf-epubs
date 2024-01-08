# Use the official Python Alpine image as the base image
FROM python:3.11.7-alpine3.19

# Set environment variables for non-secret configuration
ENV APP_HOME /app
ENV POETRY_HOME /poetry
ENV PATH $POETRY_HOME/bin:$PATH

# Install Poetry
RUN pip install poetry
RUN mkdir $POETRY_HOME

# Create a non-root user and group
RUN addgroup -S myappgroup && adduser -S myappuser -G myappgroup

# Set the working directory to /app and change ownership to the non-root user
WORKDIR $APP_HOME
RUN chown myappuser:myappgroup $APP_HOME

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
CMD ["poetry", "run", "uvicorn", "main:auto_app", "--host", "0.0.0.0", "--port", "8000"]
