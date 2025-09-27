import os


def create_folders(parent_folder, folder_list):
    """Create multiple folders inside a parent folder if they do not exist.

    Args:
        parent_folder (str): The path to the parent folder.
        folder_list (list): A list of folder names to create inside the parent folder.
    """
    if not os.path.exists(parent_folder):
        os.makedirs(parent_folder)
        print(f"Created parent folder: {parent_folder}")
    for folder_name in folder_list:
        folder_path = os.path.join(parent_folder, folder_name)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            print(f"Created folder: {folder_path}")
        else:
            print(f"Folder already exists: {folder_path}")


def create_folder(parent_folder, folder_name):
    """Create a single folder if it does not exist.
    Args:
        parent_folder (str): The path to the parent folder.
        folder_name (str): A folder name to create inside the parent folder.
    """
    if not os.path.exists(parent_folder):
        os.makedirs(parent_folder)
        print(f"Created parent folder: {parent_folder}")
    folder_path = os.path.join(parent_folder, folder_name)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print(f"Created folder: {folder_path}")
    else:
        print(f"Folder already exists: {folder_path}")
        