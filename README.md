# Flight Operations Manager

All-in-one application for managing flight operations, fleet management, and sensor tracking with database integration.

## Features

- **Flight Tracker** - Manage flight missions with automated Mission ID grouping
- **Fleet Management** - Track and manage fleet assets
- **Sensor Management** - Monitor and configure sensor systems
- **Database Integration** - SQLite with SpatiaLite support for geospatial data
- **Processing Tracker** - Track data processing status and metadata

## Project Structure

```
.
├── app/                    # Main application package
│   ├── database/          # Database models and management
│   ├── dialogs/           # Custom dialog windows
│   ├── logic/             # Business logic and services
│   ├── pages/             # UI pages/modules
│   ├── app.py             # Application entry point
│   └── main_window.py     # Main window implementation
├── backups/               # Automated database backups
├── lib/                   # Third-party dependencies (GDAL, SpatiaLite)
├── resources/             # Application resources (images, etc.)
├── scripts/               # Utility and migration scripts
├── flightlog.db           # Main application database
├── main.py                # Launcher script
└── README.md              # This file
```

## Getting Started

1. Install Python 3.8+ and required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   python main.py
   ```

## Database Management

- The application uses SQLite with SpatiaLite extension for geospatial features
- Automatic backups are stored in the `backups/` directory
- Database schema migrations are handled automatically

## Recent Updates

- **09/2025**: Added automated Mission ID grouping and Processing Tracker
- **08/2025**: Implemented database editor and core UI framework

## License

Proprietary software. All rights reserved.
