# Shiny for Python App Generator

This repository contains a Shiny for Python app that generates fully functional Shiny apps based on user-provided descriptions and CSV data. The app uses the `LangChain` library with the `Ollama` model (`deepseek-coder-v2`) to dynamically generate code, which is then executed to provide interactive dashboards and data visualizations.

## Features

- **Dynamic Shiny App Generation**: Generates Shiny apps based on the user's description and uploaded data.
- **Interactive Data Visualization**: Supports interactive exploration using PyGWalker.
- **Customizable Layout**: Includes a user-friendly interface for customizing the generated app's layout and features.
- **Easy Deployment**: Automatically runs the generated app in a new terminal environment.

## Requirements

- Python 3.8+
- Conda (for environment management)
- Required Python packages (see `requirements.txt`)

## Installation

1. **Clone the repository**:
    ```bash
    git clone https://github.com/your-username/shiny-python-app-generator.git
    cd shiny-python-app-generator
    ```

2. **Create and activate the Conda environment**:
    ```bash
    conda create --name shiny_app_env python=3.8
    conda activate shiny_app_env
    ```

3. **Install the required dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1. **Run the Shiny app**:
    ```bash
    python app.py
    ```

2. **Upload a CSV file**:
   - Use the file input in the app to upload a CSV file containing your data.

3. **Describe the Dashboard**:
   - Provide a description of the dashboard you want to generate.

4. **Generate the Dashboard**:
   - Click the "Generate Dashboard" button to generate and display the Shiny app code. The app will automatically run in a new terminal.

5. **Download the Generated App**:
   - You can download the generated Shiny app code for further use or deployment.

## File Structure

- `app.py`: Main application file that runs the Shiny for Python app generator.
- `requirements.txt`: Lists all the Python dependencies required for the project.
- `generated_app.py`: The dynamically generated Shiny app code file (created at runtime).
- `README.md`: This file, providing an overview and usage instructions.

## Troubleshooting

- **Environment Activation Issues**: Ensure the correct path to the Conda `conda.sh` file if experiencing activation errors.
- **Path Errors**: If the app fails to run due to path issues, ensure paths are correctly quoted or escaped in the code execution commands.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

1. Fork the repository.
2. Create a new branch (`git checkout -b feature-branch`).
3. Make your changes and commit them (`git commit -m 'Add feature'`).
4. Push to the branch (`git push origin feature-branch`).
5. Open a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgements

- [Shiny for Python](https://shiny.rstudio.com/py/) for providing the framework for interactive web apps.
- [LangChain](https://langchain.com/) for the natural language model integration.
- [Ollama](https://ollama.com/) for providing the deepseek-coder-v2 model used in the app generation.

## Contact

For any questions or feedback, please contact [your-email@example.com].

