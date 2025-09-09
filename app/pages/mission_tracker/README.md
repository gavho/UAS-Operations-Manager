# flight-tracker
Python based flight tracker desktop app that links to sqlite database.
UI built with PyQT5

Current:
- Manipulate DB file
  - Live edit existing DB table
  - Visual Feedback for Change Detection
    - Unsaved Records (Highlighted Yellow and Starred)
- Mission Editor Form
  - Create new records (Updates Mission ID Automatically)
  - Select & Edit/update existing records
  - Integrates with SQL DB Schema
    - Required Fields are marked
- Toolbar
  - Refresh
  - Save Edits
  - Delete Selected Row(s)
  - Create new row
  - Undo
  - Redo
  - Toggle Mission Editor)

WIP:

Future Updates:
- Overhaul UI
  - GRYFN Colorscheme
  - Font Change
  - GRYFN Logos/Branding
- Equipment Inventory Integration?
  - Create window for creating/managing platforms and sensors. Can be used as domains for mission logging.
- Calibration Tracking
  - Geometric
  - Radio
- GIS Integrations?
  - METAR/Weather API
    - User Selects Time, Date, Location (Station?)
    - Autofill weather values in new mission form from METAR
      - Wind Speed
      - Cloud Coverage

