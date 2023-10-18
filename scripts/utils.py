import os
import inspect

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