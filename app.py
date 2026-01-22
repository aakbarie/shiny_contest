"""
Shiny App Generator - Production Version

A secure Shiny for Python application that generates fully functional Shiny apps
based on user-provided descriptions and CSV data using LangChain + Ollama.

Features:
- Secure file upload with validation
- Input sanitization and validation
- Code security analysis
- Structured logging and monitoring
- Health check endpoint
- Configuration management
"""

import logging
import time
from pathlib import Path
from typing import Optional

import pandas as pd
from shiny import App, reactive, render, ui
from langchain_community.llms import Ollama

# Import configuration
from config import config

# Import utilities
from utils import (
    FileValidator,
    InputValidator,
    ValidationError,
    CodeSecurityValidator,
    SecurityError,
    secure_temp_file,
    get_safe_filename,
    setup_logging,
    LogContext,
    set_request_id,
)
from utils.monitoring import health_checker, metrics_collector

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Log startup
logger.info("=" * 80)
logger.info("Shiny App Generator Starting")
logger.info(f"Configuration: {config.get_summary()}")
logger.info("=" * 80)

# Define color palette
COLORS = {
    "background": "#FBE9D0",
    "primary": "#244855",
    "accent": "#E64833",
    "secondary": "#90AEAD",
    "text": "#874F41",
}

# Initialize Ollama LLM
try:
    llm = Ollama(
        model=config.llm_model,
        base_url=config.ollama_base_url
    )
    logger.info(f"Initialized Ollama LLM: {config.llm_model}")
except Exception as e:
    logger.error(f"Failed to initialize Ollama LLM: {e}")
    llm = None


def generate_shiny_app_code(
    description: str,
    data: pd.DataFrame,
    use_pygwalker: bool
) -> str:
    """
    Generate Shiny for Python app code using LangChain and Ollama.

    Args:
        description: User's description of desired dashboard
        data: DataFrame with user data
        use_pygwalker: Whether to include PyGWalker

    Returns:
        Generated Python code

    Raises:
        RuntimeError: If LLM is not initialized or generation fails
    """
    if llm is None:
        raise RuntimeError("LLM is not initialized")

    prompt = f"""
    Create a fully functional and executable Shiny for Python app using the Shiny framework in Python.
    The generated code should include all necessary imports, UI setup, server logic, and a proper execution block.
    Ensure to use correct imports such as pandas, plotly.express for plotting, and explicit imports for Shiny components.
    Use 'from shiny import App, reactive, render, ui' instead of wildcard imports.
    Avoid using unnecessary or incorrect imports such as mimetypes or render from pygwalker if not used.
    The app should display the data in a table, provide summary statistics, and generate a bar plot for missing data analysis.
    Include the basic structure:
    - Import necessary libraries.
    - Define the UI layout.
    - Implement the server logic with reactive elements.
    - Ensure proper activation of the Shiny app using an if __name__ == "__main__" block.
    Description: {description}
    Data columns: {', '.join(data.columns)}
    First few rows of data: {data.head().to_json(orient='records')}
    {'Include PyGWalker for interactive data exploration using pyg.walk() with the provided DataFrame.' if use_pygwalker else ''}
    Provide only the Python code necessary to run the Shiny for Python app.
    """

    logger.debug("Sending prompt to LLM")
    response = llm.invoke(prompt)
    logger.debug(f"Received response from LLM (length: {len(response)})")

    return response


def extract_and_clean_python_code(response: str) -> str:
    """
    Extract and clean Python code from the generated response.

    Args:
        response: LLM response containing Python code

    Returns:
        Cleaned Python code
    """
    # Extract code between code fences
    code_start = response.find("```python")
    code_end = response.rfind("```")

    if code_start != -1 and code_end != -1:
        code = response[code_start + len("```python"):code_end].strip()
    else:
        code = response.strip()

    # Remove comment-only lines (but keep docstrings)
    lines = code.splitlines()
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # Keep line if it's not a comment, or if it's inside quotes (docstring)
        if not stripped.startswith("#"):
            cleaned_lines.append(line)

    cleaned_code = "\n".join(cleaned_lines)
    logger.debug(f"Cleaned code (length: {len(cleaned_code)})")

    return cleaned_code


# Main app UI
app_ui = ui.page_fluid(
    # Custom CSS
    ui.tags.style(
        f"""
        body {{
            background-color: {COLORS['background']};
            color: {COLORS['text']};
        }}
        .btn {{
            background-color: {COLORS['primary']};
            color: {COLORS['background']};
        }}
        .btn:hover {{
            background-color: {COLORS['accent']};
        }}
        .card {{
            border-color: {COLORS['secondary']};
        }}
        .verbatim-output {{
            background-color: {COLORS['background']};
            color: {COLORS['text']};
            padding: 10px;
            border: 1px solid {COLORS['secondary']};
            border-radius: 5px;
            max-height: 400px;
            overflow-y: auto;
        }}
        .error-message {{
            color: {COLORS['accent']};
            font-weight: bold;
            padding: 10px;
            border: 1px solid {COLORS['accent']};
            border-radius: 5px;
            background-color: #ffe6e6;
        }}
        .success-message {{
            color: #2d5016;
            font-weight: bold;
            padding: 10px;
            border: 1px solid #2d5016;
            border-radius: 5px;
            background-color: #e6ffe6;
        }}
        .info-box {{
            background-color: {COLORS['background']};
            color: {COLORS['text']};
            padding: 10px;
            border: 1px solid {COLORS['secondary']};
            border-radius: 5px;
            margin-top: 10px;
        }}
        """
    ),

    # Header
    ui.h2("Shiny App Generator", style=f"color: {COLORS['primary']};"),
    ui.p(
        "Generate custom Shiny applications from your CSV data and description.",
        style="margin-bottom: 20px;"
    ),

    # Main layout
    ui.row(
        # Left column - Input controls
        ui.column(
            4,
            ui.input_file(
                "file1",
                "Choose CSV File",
                accept=[".csv"],
                placeholder="Upload a CSV file"
            ),
            ui.input_text_area(
                "description",
                "Describe the dashboard you want:",
                placeholder="e.g., Create a dashboard showing sales trends with interactive charts",
                rows=5
            ),
            ui.input_checkbox(
                "use_pygwalker",
                "Include PyGWalker for interactive exploration",
                value=config.pygwalker_default
            ),
            ui.input_action_button(
                "generate",
                "Generate Dashboard",
                style=f"background-color: {COLORS['accent']}; color: white; width: 100%; margin-top: 10px;"
            ),
            ui.output_ui("health_status"),
        ),

        # Right column - Output display
        ui.column(
            8,
            ui.output_ui("status_message"),
            ui.output_ui("data_info"),
            ui.output_text_verbatim("generated_code"),
            ui.output_ui("download_section"),
        )
    ),

    # Footer
    ui.hr(),
    ui.p(
        f"Environment: {config.environment} | "
        f"Max file size: {config.max_file_size_mb}MB | "
        f"Model: {config.llm_model}",
        style="font-size: 0.8em; color: #666; text-align: center;"
    ),
)


# Server logic
def server(input, output, session):
    """Main server logic for the Shiny app."""

    # Reactive values
    data = reactive.Value(None)
    generated_code = reactive.Value("")
    generated_file_path = reactive.Value(None)
    error_message = reactive.Value("")
    success_message = reactive.Value("")

    # Initialize validators
    file_validator = FileValidator()
    input_validator = InputValidator()
    code_validator = CodeSecurityValidator()

    @output
    @render.ui
    def health_status():
        """Display health status."""
        health = health_checker.get_health_status()
        status_color = (
            "#2d5016" if health["status"] == "healthy"
            else COLORS["accent"]
        )

        return ui.div(
            ui.h6(
                f"Status: {health['status'].upper()}",
                style=f"color: {status_color};"
            ),
            ui.p(
                f"Uptime: {health['uptime']}",
                style="font-size: 0.8em; margin: 0;"
            ),
            ui.p(
                f"Ollama: {health['components']['ollama']['status']}",
                style="font-size: 0.8em; margin: 0;"
            ),
            class_="info-box"
        )

    @output
    @render.ui
    def status_message():
        """Display status/error/success messages."""
        if error_message():
            return ui.div(error_message(), class_="error-message")
        elif success_message():
            return ui.div(success_message(), class_="success-message")
        return ui.div()

    @output
    @render.ui
    def data_info():
        """Display information about loaded data."""
        if data() is None:
            return ui.div()

        df = data()
        return ui.div(
            ui.h5("Data Information", style=f"color: {COLORS['primary']};"),
            ui.p(f"Rows: {len(df):,}"),
            ui.p(f"Columns: {len(df.columns)}"),
            ui.p(f"Column names: {', '.join(df.columns)}"),
            class_="info-box"
        )

    @reactive.Effect
    @reactive.event(input.generate)
    async def generate_code():
        """Generate Shiny app code from user input."""
        # Clear previous messages
        error_message.set("")
        success_message.set("")
        generated_code.set("")

        # Generate request ID for tracking
        with LogContext() as req_id:
            logger.info(f"Starting code generation (request_id: {req_id})")
            metrics_collector.record_generation_request()

            start_time = time.time()

            try:
                # Validate file upload
                if input.file1() is None:
                    raise ValidationError("Please upload a CSV file first")

                file_info = input.file1()[0]
                logger.info(f"Processing file: {file_info['name']}")

                # Validate file
                file_validator.validate_upload(file_info)

                # Validate and load CSV
                df = file_validator.validate_csv_content(file_info["datapath"])
                data.set(df)
                logger.info(f"Loaded CSV: {len(df)} rows, {len(df.columns)} columns")

                # Validate description
                description = input_validator.validate_description(
                    input.description()
                )
                logger.info(f"Description validated (length: {len(description)})")

                # Validate checkbox
                use_pygwalker = input_validator.validate_checkbox(
                    input.use_pygwalker()
                )

                # Generate code
                logger.info("Generating code with LLM")
                response = generate_shiny_app_code(description, df, use_pygwalker)

                # Extract and clean code
                code = extract_and_clean_python_code(response)

                # Validate code security
                logger.info("Validating code security")
                is_safe, issues = code_validator.validate_code(code)

                if not is_safe:
                    logger.warning(f"Code validation failed: {issues}")
                    metrics_collector.record_validation_failure()
                    raise SecurityError(
                        f"Generated code contains security issues:\n" +
                        "\n".join(f"- {issue}" for issue in issues[:5])
                    )

                # Save generated code
                safe_filename = get_safe_filename(
                    file_info["name"],
                    prefix="generated"
                )
                output_path = config.generated_dir / safe_filename

                with open(output_path, 'w') as f:
                    f.write(code)

                generated_code.set(code)
                generated_file_path.set(output_path)

                duration = time.time() - start_time
                metrics_collector.record_generation_success(duration)

                success_message.set(
                    f"✓ Dashboard code generated successfully in {duration:.1f}s! "
                    f"Download the code below."
                )
                logger.info(f"Code generation successful (duration: {duration:.1f}s)")

            except ValidationError as e:
                error_message.set(f"Validation Error: {str(e)}")
                logger.warning(f"Validation error: {e}")
                metrics_collector.record_validation_failure()

            except SecurityError as e:
                error_message.set(f"Security Error: {str(e)}")
                logger.error(f"Security error: {e}")
                metrics_collector.record_generation_failure()

            except Exception as e:
                error_message.set(
                    f"An unexpected error occurred: {str(e)}\n"
                    f"Please check your input and try again."
                )
                logger.error(f"Generation error: {e}", exc_info=True)
                metrics_collector.record_generation_failure()

    @output
    @render.text
    def generated_code():
        """Display generated code."""
        return generated_code() or "Generated code will appear here..."

    @output
    @render.ui
    def download_section():
        """Display download button when code is generated."""
        if generated_file_path():
            return ui.div(
                ui.download_button(
                    "download_app",
                    "Download Generated App",
                    style=f"background-color: {COLORS['primary']}; color: white;"
                ),
                class_="info-box"
            )
        return ui.div()

    @output
    @render.download(filename=lambda: generated_file_path().name if generated_file_path() else "app.py")
    def download_app():
        """Handle app download."""
        if generated_file_path() and generated_file_path().exists():
            logger.info(f"Downloading: {generated_file_path()}")
            return str(generated_file_path())
        return None


# Create app instance
app = App(app_ui, server)


# Health check endpoint (for monitoring)
@ui.page("/health", title="Health Check")
def health_page():
    """Health check endpoint for monitoring."""
    health = health_checker.get_health_status()
    metrics = metrics_collector.get_metrics()

    return ui.page_fluid(
        ui.h3("Health Check"),
        ui.pre(
            f"Status: {health['status']}\n"
            f"Uptime: {health['uptime']}\n"
            f"Environment: {health['config']['environment']}\n"
            f"LLM Model: {health['config']['llm_model']}\n\n"
            f"Metrics:\n"
            f"- Total Requests: {metrics['generation_requests']}\n"
            f"- Successful: {metrics['generation_success']}\n"
            f"- Failed: {metrics['generation_failures']}\n"
            f"- Success Rate: {metrics['success_rate']}%\n"
            f"- Avg Generation Time: {metrics['average_generation_time']}s\n"
        )
    )


if __name__ == "__main__":
    logger.info(f"Starting Shiny app on {config.app_host}:{config.app_port}")
    app.run(host=config.app_host, port=config.app_port)
