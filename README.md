# OCI Sentinel

![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)
![License](https://img.shields.io/badge/License-GPLv3-green.svg)

**OCI Sentinel** is a free, open-source Windows desktop application developed by **Oakshift Software** on behalf of the **Orbital Conservation Institute (OCI)**.

The application provides live visualisation, tracking and long-term analysis of all publicly tracked orbital debris and artificial objects published through **CelesTrak**, allowing researchers, students, enthusiasts and conservation advocates to better understand the ever-changing environment surrounding Earth.

Unlike many web-based trackers, Sentinel can optionally maintain a local historical archive of tracking information, enabling long-term trajectory analysis, trend detection and predictive modelling entirely from your own machine.

---

## Features

### Live Orbital Tracking

- Download the latest public orbital datasets directly from CelesTrak
- Display all tracked satellites and orbital debris
- Automatic catalogue updates
- Filter by object type
- Search by NORAD Catalogue Number
- Search by object name
- Display orbital parameters
- Display object metadata
- Live position updates

---

### Interactive Orbit Visualisation

- 2D Earth projection
- 3D orbital visualisation *(planned)*
- Colour-coded object types
- Individual orbit paths
- Multiple map projections
- Zoom and pan controls
- Orbit highlighting
- Future path projection

---

### Historical Data Collection

Sentinel can optionally maintain a local SQLite database containing downloaded tracking data.

This allows users to build their own historical archive without relying on third-party services.

Examples include:

- Historical TLE records
- Position history
- Velocity history
- Orbital element changes
- Decay progression
- Altitude changes
- Inclination changes

All historical data remains entirely local to the user's computer.

---

### Trajectory Prediction

Using locally collected historical datasets, Sentinel can estimate future orbital behaviour including:

- Predicted orbital path
- Orbital decay trends
- Altitude changes
- Future position estimation
- Long-term orbital evolution
- Object lifetime estimates

Predictions are intended for educational and research purposes and should not be considered mission-critical navigation data.

---

### Conservation Analytics

As an OCI project, Sentinel includes conservation-focused tools not commonly found in traditional satellite tracking software.

Examples include:

- Orbital congestion statistics
- Debris density by altitude
- Orbital shell utilisation
- Growth trends
- Fragmentation history
- Re-entry statistics
- Orbital Cleanliness Index (OCI)

---

### Local Database

Sentinel stores information using SQLite.

The local database may contain:

```
Objects
TLE History
Position History
Orbital Parameters
Velocity Samples
Predicted Trajectories
Collision Assessments
Settings
Logs
```

Users maintain complete control over all locally stored information.

---

## Settings

Sentinel includes a dedicated Settings window allowing users to configure local data collection.

Available options include:

### Data Collection

- Enable local tracking archive
- Disable local tracking archive
- Store TLE history
- Store position history
- Store velocity history
- Store prediction cache

### Database Management

- View database size
- Clear historical tracking data
- Vacuum database
- Export database
- Import existing database

### Network

- Automatic CelesTrak updates
- Update frequency
- Manual update
- Offline mode

### Visualisation

- Light/Dark themes
- Map projection
- Object colours
- Orbit trail length
- Refresh rate

---

## Privacy

OCI Sentinel is designed with privacy in mind.

The application:

- does not require an account
- does not upload collected data
- stores historical information locally only
- does not perform telemetry
- allows users to completely disable local storage

Users remain in full control of all collected data.

---

## Planned Features

- Collision probability estimation
- Close approach alerts
- Atmospheric drag estimation
- Launch history viewer
- Fragmentation event timeline
- Country statistics
- Object age visualisation
- Orbit comparison tools
- Heatmaps
- Earth night/day visualisation
- Space weather integration
- Plugin system
- API for third-party tools

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.13+ |
| GUI | PySide6 |
| Database | SQLite |
| Mapping | Cartopy / PyQtGraph |
| Orbit Calculations | Skyfield |
| TLE Propagation | sgp4 |
| Charts | Matplotlib |
| HTTP | Requests |
| Packaging | PyInstaller |
| Installer | Inno Setup |

---

## Data Sources

Sentinel uses publicly available orbital element data provided by:

- CelesTrak
- Space-Track (future optional support)
- Orbital Conservation Institute datasets

Sentinel does **not** modify official orbital element datasets.

---

## Project Goals

The Orbital Conservation Institute believes that improving public understanding of Earth's orbital environment is essential to ensuring the long-term sustainability of space activities.

Sentinel has been created to:

- improve public awareness of orbital debris
- encourage responsible satellite operations
- provide educational resources
- support research into orbital sustainability
- promote evidence-based conservation initiatives

---

## License

OCI Sentinel is released as free and open-source software.

See the LICENSE file for additional information.

---

## About

**OCI Sentinel**

Developed by **Oakshift Software**

On behalf of the **Orbital Conservation Institute**

*"Monitor. Understand. Protect Earth's Orbital Environment."*
