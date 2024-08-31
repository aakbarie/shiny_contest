import pandas as pd
from shiny import App, reactive, render, ui
from langchain_community.llms import Ollama
import pygwalker as pyg

# Color palette based on Prometheus
COLORS = {
    "background": "#FBE9D0",
    "primary": "#244855",
    "accent": "#E64833",
    "secondary": "#90AEAD",
    "text": "#874F41",
}

# Initialize Ollama LLM with the deepseek-coder-v2 model
llm = Ollama(model="deepseek-coder-v2")

# Function to generate Shiny for Python app code using LangChain and Ollama
def generate_shiny_app_code(description, data, use_pygwalker):
    prompt = f"""
    Create a fully functional and executable Shiny for Python app using the Shiny framework in Python.
    The generated code should only use the Shiny for Python framework (do not use Streamlit or any other framework).
    Include necessary imports, UI setup, server logic, and a proper execution block. The generated app should be ready to run directly.
    Ensure that all required arguments are provided, such as 'choices' for input fields like input_selectize().
    Description: {description}
    Data columns: {', '.join(data.columns)}
    First few rows of data: {data.head().to_json(orient='records')}
    {'Include PyGWalker for interactive data exploration.' if use_pygwalker else ''}
    Provide only the Python code necessary to run the Shiny for Python app.
    """
    response = llm.invoke(prompt)
    return response

# Function to extract only the Python code from the generated response
def extract_python_code(response):
    code_start = response.find("```python")
    code_end = response.rfind("```")
    if code_start != -1 and code_end != -1:
        code = response[code_start + len("```python"):code_end].strip()
    else:
        code = response.strip()  # Default to entire response if no code fences found
    return code

# Main app UI with corrected styling and spinner integration
app_ui = ui.page_fluid(
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
        .file-input {{
            background-color: {COLORS['primary']};
            color: {COLORS['background']};
        }}
        .text-area {{
            color: {COLORS['text']};
        }}
        .verbatim-output {{
            background-color: {COLORS['background']};
            color: {COLORS['text']};
            padding: 10px;
            border: 1px solid {COLORS['secondary']};
            border-radius: 5px;
        }}
        .spinner-container {{
            display: none;
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 1000;
            text-align: center;
        }}
        .spinner-text {{
            margin-top: 10px;
            color: {COLORS['text']};
            font-weight: bold;
        }}
        .description-box {{
            background-color: {COLORS['background']};
            color: {COLORS['text']};
            padding: 10px;
            border: 1px solid {COLORS['secondary']};
            border-radius: 5px;
            margin-top: 10px;
        }}
        """
    ),
    ui.tags.div(
        ui.input_file("file1", "Choose CSV File", accept=[".csv"]),
        class_="file-input"
    ),
    ui.tags.div(
        ui.input_text_area("description", "Describe the dashboard you want:"),
        class_="text-area"
    ),
    ui.input_checkbox("use_pygwalker", "Include PyGWalker for interactive exploration", value=True),
    ui.input_action_button("generate", "Generate Dashboard", class_="btn"),
    ui.tags.div(
        ui.output_text("app_description"),
        class_="description-box"  # Add description box class for styling
    ),
    ui.tags.div(
        ui.output_text_verbatim("generated_code"),
        class_="verbatim-output"
    ),
    ui.output_ui("dynamic_app"),
    ui.tags.div(
        ui.tags.div(
            class_="spinner-border text-primary",
            role="status"
        ),
        ui.tags.div(
            "Scanning subspace for chronitron particles",
            class_="spinner-text"
        ),
        id="spinner-container",
        class_="spinner-container"
    ),
    ui.download_button("download_app", "Download Generated Shiny App"),
    ui.tags.script(
        """
        Shiny.addCustomMessageHandler("show_spinner", function(message) {
            let spinner = document.getElementById("spinner-container");
            if (message.show) {
                spinner.style.display = "block";
            } else {
                spinner.style.display = "none";
            }
        });
        """
    )
)

# Server logic
def server(input, output, session):
    data = reactive.Value(None)
    loading = reactive.Value(False)
    generated_file_path = reactive.Value(None)
    full_response = reactive.Value("")  # Store the full response for display

    # Wrap the spinner control functions in async def and use await
    @reactive.Effect
    @reactive.event(input.generate)
    async def show_spinner():
        loading.set(True)
        await session.send_custom_message("show_spinner", {"show": True})

    @output
    @render.text
    @reactive.event(input.generate)
    async def generated_code():
        if input.file1() is None:
            return "Please upload a CSV file first."
        try:
            file_info = input.file1()[0]
            data.set(pd.read_csv(file_info["datapath"]))
            response = generate_shiny_app_code(input.description(), data(), input.use_pygwalker())
            full_response.set(response)  # Store the full response
            code = extract_python_code(response)  # Extract the Python code for download
            file_name = file_info["name"].rsplit('.', 1)[0] + "_app.py"
            generated_file_path.set(file_name)
            with open(file_name, 'w') as file:
                file.write(code)
            return response  # Display the full response, including explanations
        finally:
            loading.set(False)
            await session.send_custom_message("show_spinner", {"show": False})

    @output
    @render.text
    def app_description():
        if data() is None:
            return "No data loaded."
        desc = f"""
        **Data Description:**
        - Columns: {', '.join(data().columns)}
        - Number of rows: {len(data())}
        
        **App Description:**
        - App based on the uploaded data and user-provided description.
        - Features interactive data visualization with PyGWalker included: {'Yes' if input.use_pygwalker() else 'No'}.
        """
        return desc

    @output
    @render.ui
    @reactive.event(input.generate)
    def dynamic_app():
        if data() is None:
            return ui.p("Please upload a CSV file and generate the dashboard.")

        code = extract_python_code(full_response())  # Use only the code part for execution

        local_vars = {
            'pd': pd,
            'ui': ui,
            'render': render,
            'reactive': reactive,
            'pyg': pyg
        }
        exec(code, globals(), local_vars)

        if 'app_ui' in local_vars and 'server' in local_vars:
            return App(local_vars['app_ui'], local_vars['server'])
        else:
            return ui.p("Failed to generate a valid Shiny app.")

    @output
    @render.download()
    def download_app():
        if generated_file_path.get() is None:
            return None
        # Download only the pure Python code extracted from the response
        return generated_file_path.get()

# Create and run the app
app = App(app_ui, server)

if __name__ == "__main__":
    print("Starting the Shiny app...")
    app.run(host="0.0.0.0", port=8050)
