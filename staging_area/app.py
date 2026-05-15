import pandas as pd
from shiny import App, reactive, render, ui
from langchain_community.llms import Ollama
import tempfile
import os

# Define color palette based on Prometheus
COLORS = {
    "background": "#FBE9D0",
    "primary": "#244855",
    "accent": "#E64833",
    "secondary": "#90AEAD",
    "text": "#874F41",
}

# Initialize Ollama LLM with the deepseek-coder-v2 model
llm = Ollama(model="deepseek-coder-v2")

def generate_tableau_like_streamlit_code(description, data, use_pygwalker):
    prompt = f"""
    Create a Streamlit app that resembles a Tableau dashboard. The app should be fully functional, interactive, and visually appealing. Use the following structure and guidelines:

    1. Imports:
       import streamlit as st
       import pandas as pd
       import plotly.express as px
       import plotly.graph_objects as go
       from plotly.subplots import make_subplots
       import pygwalker as pyg (if use_pygwalker is True)

    2. Page Configuration:
       - Set a wide layout and a meaningful title

    3. Data Loading:
       - Use st.file_uploader for CSV files
       - Include sample data if no file is uploaded

    4. Sidebar:
       - Add filters for key variables using st.sidebar
       - Include a date range selector if applicable

    5. Main Dashboard:
       - Create a multi-column layout using st.columns
       - Include the following elements:
         a. Key Performance Indicators (KPIs) at the top
         b. Time series chart (if time data is available)
         c. Bar chart for categorical comparisons
         d. Scatter plot for correlation analysis
         e. Pie or donut chart for composition analysis
         f. Heatmap for multi-variable comparison
       - Make charts interactive with click events and cross-filtering

    6. Advanced Features:
       - Implement drill-down functionality
       - Add tooltips with detailed information
       - Create a dynamic title that updates based on selections

    7. Styling:
       - Use a cohesive color scheme
       - Add descriptive titles and labels to all charts
       - Ensure consistent formatting of numbers and dates

    8. Performance Optimization:
       - Use st.cache for data loading and processing
       - Implement efficient filtering mechanisms

    9. Error Handling:
       - Include try-except blocks for robust error management

    10. PyGWalker Integration (if use_pygwalker is True):
        - Add a separate tab or section for PyGWalker exploration

    Description: {description}
    Data columns: {', '.join(data.columns)}
    First few rows of data: {data.head().to_json(orient='records')}
    Use PyGWalker: {'Yes' if use_pygwalker else 'No'}

    Provide only the Python code necessary to run this Tableau-like Streamlit dashboard.
    """
    response = llm.invoke(prompt)
    return response

def extract_and_clean_python_code(response):
    code_start = response.find("```python")
    code_end = response.rfind("```")
    if code_start != -1 and code_end != -1:
        code = response[code_start + len("```python"):code_end].strip()
    else:
        code = response.strip()
    cleaned_code = "\n".join(line for line in code.splitlines() if not line.strip().startswith("#"))
    return cleaned_code

def post_process_code(code):
    # Ensure correct PyGWalker usage
    code = code.replace("pygwalker.walk(", "pyg.walk(")
    
    # Add custom CSS for Tableau-like styling
    custom_css = """
    <style>
    .stApp {
        background-color: #F0F2F6;
    }
    .stPlotlyChart {
        background-color: white;
        border-radius: 5px;
        box-shadow: 0 2px 5px 0 rgba(0,0,0,0.16);
    }
    .st-emotion-cache-1gulkj5 {
        background-color: #F0F2F6;
    }
    </style>
    """
    # Embed CSS directly using st.markdown without being part of file handling
    code = f"st.markdown('''{custom_css}''', unsafe_allow_html=True)\n" + code
    
    return code

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
    ui.row(
        ui.column(
            4,
            ui.input_file("file1", "Choose CSV File", accept=[".csv"]),
            ui.input_text_area("description", "Describe the SpectraCore dashboard you want:"),
            ui.input_checkbox("use_pygwalker", "Include PyGWalker for interactive exploration", value=True),
            ui.input_action_button("generate", "Generate SpectraCore Dashboard", style=f"background-color: {COLORS['accent']}; color: {COLORS['background']};"),
        ),
        ui.column(
            8,
            ui.tags.div(ui.output_text("app_description"), class_="description-box"),
            ui.tags.div(ui.output_text_verbatim("generated_code"), class_="verbatim-output"),
            ui.output_ui("dynamic_app"),
            ui.tags.div(
                ui.tags.div(class_="spinner-border text-primary", role="status"),
                ui.tags.div("SpectraCore is generating your Tableau-like dashboard...", class_="spinner-text"),
                id="spinner-container",
                class_="spinner-container"
            ),
            ui.download_button("download_app", "Download SpectraCore Streamlit App"),
        )
    ),
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

def server(input, output, session):
    data = reactive.Value(None)
    loading = reactive.Value(False)
    generated_code = reactive.Value("")
    generated_file_path = reactive.Value(None)

    @reactive.Effect
    @reactive.event(input.generate)
    async def show_spinner():
        loading.set(True)
        await session.send_custom_message("show_spinner", {"show": True})

    @output
    @render.text
    @reactive.event(input.generate)
    async def generated_code_view():
        if input.file1() is None:
            return "Please upload a CSV file first."
        try:
            file_info = input.file1()[0]
            data.set(pd.read_csv(file_info["datapath"]))
            response = generate_tableau_like_streamlit_code(input.description(), data(), input.use_pygwalker())
            code = extract_and_clean_python_code(response)
            processed_code = post_process_code(code)
            generated_code.set(processed_code)

            # Save the generated code to a temporary file for download
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".py")
            temp_file.write(processed_code.encode())
            temp_file.close()
            generated_file_path.set(temp_file.name)

            return processed_code
        except Exception as e:
            return f"An error occurred: {str(e)}"
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
        
        **SpectraCore App Description:**
        - Tableau-like Streamlit dashboard based on the uploaded data and user-provided description.
        - Features interactive data visualization with PyGWalker included: {'Yes' if input.use_pygwalker() else 'No'}.
        """
        return desc

    @output
    @render.ui
    @reactive.event(input.generate)
    async def dynamic_app():
        if data() is None:
            return ui.p("Please upload a CSV file and generate the SpectraCore dashboard.")
        return ui.pre(generated_code.get())

    @output
    @render.download(filename=lambda: os.path.basename(generated_file_path.get()))
    def download_app():
        if generated_file_path.get() is None:
            return None
        with open(generated_file_path.get(), 'r') as file:
            return file.read()

app = App(app_ui, server)

if __name__ == "__main__":
    print("Starting SpectraCore...")
    app.run(host="0.0.0.0", port=8050)
