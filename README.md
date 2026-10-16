Eco Infra Studio | AI-Assisted Sustainable Infrastructure Design

An AI-assisted infrastructure design platform that helps users plan sustainable buildings by analyzing environmental conditions, energy efficiency, construction materials, and local building constraints.

Project Overview

I developed Eco Infra Studio to explore how artificial intelligence and environmental data could improve infrastructure planning.

Instead of designing a building based only on appearance or cost, the platform allows users to explore how different design decisions affect energy consumption, environmental impact, and overall feasibility.

The application brings together environmental analysis, design optimization, and automated 3D modeling.

Key Features

1. AI-Assisted Infrastructure Design

Generates and compares building configurations based on user preferences.

Considers location, budget, building dimensions, construction materials, and available green space.

Ranks potential designs using estimated energy performance and environmental impact.

2. Environmental Impact Analysis

Retrieves climate and air-quality information using Open-Meteo APIs.

Uses OpenStreetMap data to analyze nearby parks and green spaces.

Compares estimated energy usage and carbon impact across different building designs.

Explores opportunities to reduce environmental impact through material selection and design choices.

3. Building Constraints and Feasibility

Evaluates designs against modeled zoning and building constraints.

Considers building height, setbacks, site coverage, and open-space requirements.

Filters configurations that do not meet the application's feasibility rules.

4. Automated 3D Modeling

Integrates Blender to generate 3D representations of proposed buildings.

Produces editable building models for further development.

Supports 3D visualization and STL export for physical prototyping or 3D printing.

5. Interactive Design Interface

Provides a guided interface for entering project requirements.

Displays environmental comparisons and design results.

Allows users to review generated building configurations.

Technologies Used

Frontend

Angular

TypeScript

Bootstrap

Three.js

Backend and Analysis

Python

FastAPI

scikit-learn

Environmental and geospatial data APIs

3D Modeling

Blender

GLB and STL model export

Data Sources

Open-Meteo

OpenStreetMap

NYC PLUTO property data

NYC Local Law 84 energy benchmarking data
