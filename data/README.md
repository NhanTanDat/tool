# Data Folder
This directory stores runtime/generated data files instead of scattering them across source folders.

## Files
- `list_name.txt` : Extracted instance/name list from Premiere project parsing.
- `dl_links.txt`  : Generated YouTube (or other) download links corresponding to names.
- `timeline_export.json` / `timeline_export.csv` : Timeline clip metadata exports from Premiere ExtendScript.
- `ytDownVer.json` : (Optional) Version / config info for download tool.
- `dlg_control_identifiers.txt`, `menu_identifiers.txt` : UI automation identifier captures.

## Conventions
- All tools should reference data here using a resolved absolute path. Example snippet (already applied in code):
  ```python
  ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
  DATA_DIR = os.path.join(ROOT_DIR, 'data')
  os.makedirs(DATA_DIR, exist_ok=True)
  list_name_path = os.path.join(DATA_DIR, 'list_name.txt')
  ```
- When packaging with PyInstaller, ensure `data/` is included (add to spec as a datas tuple if not already).

## Cleanup
- Temporary or large debug dumps (e.g. exported Premiere XML) can be placed here but are not required.
