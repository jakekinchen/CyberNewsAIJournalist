import os
import inspect
from gpt_utils import query_gpt, model_optimizer, tokenizer
import sys
import traceback
import linecache
import logging

MAX_TOKENS = 8096

# Set up logging
logging.basicConfig(filename='error_log.txt', level=logging.DEBUG, format='%(message)s')

def query_code_gpt(code, model='gpt-4'):
    model = model_optimizer(code, model)
    system_prompt = "You are a brilliant coder. You value: - Conciseness - DRY principle - Self-documenting code over comments - Modularity - Deduplicated code - Fewer lines of code over readability - Abstracting things away to functions for reusability - Logical thinking - Displaying a lot of output as you go through the code so the user can see what's happening to the data - Always prefer importing and using modern libraries to reduce the amount of redundant boilerplate code you have to use. Explain what coding principles are being violated and then show off some fancy coding that would impress a human coder. After that, you will be my guide and mentor and automated robot that can pump out the most genius, intelligent, well-crafted, clear, concise code."
    user_prompt = f"Now analyze this code and tell me what you think of it. What are the pros and cons of this code? What are the best practices that are being violated? What are the issues that are being caused? Think critically and step by step. Code: {code}"
    return query_gpt(user_prompt, system_prompt, model=model)

def inspect_all_methods(ignore_methods=[]):
    # Set the directory to search for Python files
    directory = "scripts"

    # Get the name of the current module
    current_module = inspect.getmodulename(inspect.stack()[-1][1])

    # Loop through all files in the directory
    for filename in os.listdir(directory):
        # Check if the file is a Python file
        if filename.endswith(".py"):
            # Print the filename
            print(f"\n{filename}\n{'-' * len(filename)}")

            # Import the module
            module_name = filename[:-3]  # Remove the ".py" extension
            module = __import__(module_name)

            # Check if the module is not the current module
            if module_name != current_module[:-3]:
                # Get all the members of the module
                members = inspect.getmembers(module)

                # Filter out the functions and sort them by their line number in the source file
                functions = [(name, member) for name, member in members if inspect.isfunction(member) and name not in ignore_methods]
                functions.sort(key=lambda x: inspect.getsourcelines(x[1])[1])

                # Loop through the functions and print the signature
                for name, member in functions:
                    print(f"{name}{inspect.signature(member)}")

def capture_traceback_and_variables(exc_traceback):
    frames = traceback.extract_tb(exc_traceback)
    captured_info = []

    for i, frame in enumerate(frames):
        filename, lineno, name, _ = frame

        # Filter out frames not from your code directory
        if "your_code_directory" in filename:
            line = linecache.getline(filename, lineno).strip()
            
            # Fetch local variables from the frame
            frame_info = sys._getframe(i + 1)
            local_vars = frame_info.f_locals

            # Process variable values
            processed_vars = {}
            for var_name, var_value in local_vars.items():
                if isinstance(var_value, str) and len(var_value) > 50:
                    var_value = var_value[:50] + "..." + var_value[-20:]
                processed_vars[var_name] = var_value

            captured_info.append((filename, lineno, line, processed_vars))

    return captured_info

def handle_exception(exc_type, exc_value, exc_traceback):
    # Capture extended traceback info
    capture_traceback_and_variables(exc_traceback)
    # Then call the default handler
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

# Set the custom exception handler
sys.excepthook = handle_exception